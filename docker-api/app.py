import json
import logging
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Annotated, Any

import yaml
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from opendataloader_pdf.cli_options_generated import CLI_OPTIONS
from opendataloader_pdf.convert_generated import convert

CONFIG_PATH_ENV = "APP_CONFIG"
DEFAULT_CONFIG_PATH = "/app/docker-api/config.yaml"


def load_config() -> dict[str, Any]:
    config_path = Path(os.getenv(CONFIG_PATH_ENV, DEFAULT_CONFIG_PATH))
    if not config_path.exists():
        raise RuntimeError(f"Configuration file not found: {config_path}")

    raw = config_path.read_text(encoding="utf-8")
    if config_path.suffix.lower() in (".yaml", ".yml"):
        config = yaml.safe_load(raw)
    elif config_path.suffix.lower() == ".json":
        config = json.loads(raw)
    else:
        raise RuntimeError("Configuration file must be .yaml/.yml or .json")

    if not isinstance(config, dict):
        raise RuntimeError("Configuration root must be an object")

    return config


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_option_value(option: dict[str, Any], value: Any) -> Any:
    option_type = option.get("type")
    if option_type == "boolean":
        return parse_bool(value)

    if value is None:
        return None

    if option_type == "string":
        return str(value)

    return value


def build_option_map() -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for option in CLI_OPTIONS:
        mapping[option["name"]] = option
        mapping[option["python_name"]] = option
    return mapping


def infer_format_from_accept(accept_header: str, config: dict[str, Any]) -> str:
    accepted_media = config["api"]["accepted_media_types"]
    if not accept_header:
        return config["runtime"]["default_format"]

    for token in [p.strip() for p in accept_header.split(",") if p.strip()]:
        media_type = token.split(";", 1)[0].strip().lower()
        if media_type in accepted_media:
            return accepted_media[media_type]
        if media_type == "*/*":
            return config["runtime"]["default_format"]

    return config["runtime"]["default_format"]


def collect_outputs(output_dir: Path) -> list[Path]:
    return sorted([p for p in output_dir.rglob("*") if p.is_file()])


def first_format_extension(target_format: str) -> str:
    if target_format == "markdown":
        return ".md"
    if target_format == "text":
        return ".txt"
    if target_format == "html":
        return ".html"
    if target_format == "json":
        return ".json"
    if target_format == "pdf":
        return ".pdf"
    return ""


def is_valid_pdf_stream(raw: bytes) -> bool:
    """Basic PDF stream sanity check to catch truncated uploads early."""
    if len(raw) < 8:
        return False

    # Most PDFs start with %PDF- and end with %%EOF near the tail.
    if not raw.startswith(b"%PDF-"):
        return False

    return b"%%EOF" in raw[-2048:]


CONFIG = load_config()
OPTION_MAP = build_option_map()
Path(CONFIG["runtime"]["work_dir"]).mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=getattr(logging, CONFIG["logging"]["level"].upper(), logging.INFO))
logger = logging.getLogger("opendataloader_pdf_api")

app = FastAPI(title="OpenDataLoader PDF REST API", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/options")
def options() -> list[dict[str, Any]]:
    return CLI_OPTIONS


@app.post("/convert")
async def convert_pdf(
    request: Request,
    files: Annotated[list[UploadFile], File(...)],
) -> Response:
    runtime_cfg = CONFIG["runtime"]
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="At least one PDF file is required")

    total_size = 0
    for file in files:
        filename = file.filename or ""
        if not filename.lower().endswith(".pdf"):
            detail = f"Only PDF files are supported: {filename or '<unknown>'}"
            raise HTTPException(status_code=400, detail=detail)

    form = await request.form()
    raw_options = form.get("options")

    options_payload: dict[str, Any] = {}
    if raw_options:
        try:
            parsed_options = json.loads(str(raw_options))
            if not isinstance(parsed_options, dict):
                raise ValueError("options must be a JSON object")
            options_payload = parsed_options
        except Exception as error:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid options payload: {error}",
            ) from error

    converted_options: dict[str, Any] = {}
    for key, value in form.items():
        if key in {"files", "options"}:
            continue
        if key not in OPTION_MAP:
            continue
        option = OPTION_MAP[key]
        converted_options[option["python_name"]] = parse_option_value(option, value)

    for key, value in options_payload.items():
        if key not in OPTION_MAP:
            raise HTTPException(status_code=400, detail=f"Unsupported option: {key}")
        option = OPTION_MAP[key]
        converted_options[option["python_name"]] = parse_option_value(option, value)

    requested_format = converted_options.get("format")
    if not requested_format and runtime_cfg["infer_format_from_accept"]:
        requested_format = infer_format_from_accept(request.headers.get("accept", ""), CONFIG)
        if requested_format and requested_format != "zip":
            converted_options["format"] = requested_format

    if isinstance(converted_options.get("content_safety_off"), list):
        converted_options["content_safety_off"] = ",".join(converted_options["content_safety_off"])

    with tempfile.TemporaryDirectory(
        prefix="odl_in_", dir=runtime_cfg["work_dir"]
    ) as input_tmp:
        with tempfile.TemporaryDirectory(
            prefix="odl_out_", dir=runtime_cfg["work_dir"]
        ) as output_tmp:
            input_dir = Path(input_tmp)
            output_dir = Path(output_tmp)

            input_paths: list[str] = []
            for upload in files:
                await upload.seek(0)
                raw = await upload.read()
                total_size += len(raw)
                if total_size > int(runtime_cfg["max_upload_mb"]) * 1024 * 1024:
                    raise HTTPException(
                        status_code=413,
                        detail="Upload exceeds max_upload_mb limit",
                    )

                upload_name = upload.filename or "upload.pdf"
                if not is_valid_pdf_stream(raw):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Invalid or truncated PDF stream received for "
                            f"'{upload_name}'. Ensure multipart upload sends raw binary bytes."
                        ),
                    )

                target = input_dir / Path(upload_name).name
                target.write_bytes(raw)
                input_paths.append(str(target))

            try:
                convert(input_path=input_paths, output_dir=str(output_dir), **converted_options)
            except subprocess.CalledProcessError as error:
                raw_output = ""
                if isinstance(error.output, bytes):
                    raw_output = error.output.decode("utf-8", errors="replace")
                elif isinstance(error.output, str):
                    raw_output = error.output

                if "End of file is reached" in raw_output or "Invalid PDF" in raw_output:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "PDF parser rejected the uploaded stream as incomplete or invalid. "
                            "Retry with a binary multipart upload and verify file integrity."
                        ),
                    ) from error

                logger.exception("Conversion failed")
                raise HTTPException(
                    status_code=500,
                    detail=f"Conversion failed: {error}",
                ) from error
            except Exception as error:
                logger.exception("Conversion failed")
                raise HTTPException(
                    status_code=500,
                    detail=f"Conversion failed: {error}",
                ) from error

            outputs = collect_outputs(output_dir)
            if not outputs:
                raise HTTPException(status_code=500, detail="No output files were produced")

            accept = request.headers.get("accept", "")
            inferred_from_accept = infer_format_from_accept(accept, CONFIG)
            wants_zip = inferred_from_accept == "zip"

            target_format = converted_options.get("format")
            if isinstance(target_format, str) and "," in target_format:
                wants_zip = True

            if len(files) > 1:
                wants_zip = True

            if wants_zip:
                zip_buffer = tempfile.SpooledTemporaryFile(max_size=20 * 1024 * 1024)
                with zipfile.ZipFile(
                    zip_buffer,
                    mode="w",
                    compression=zipfile.ZIP_DEFLATED,
                ) as archive:
                    for output_path in outputs:
                        archive.write(output_path, output_path.relative_to(output_dir))
                zip_buffer.seek(0)
                return StreamingResponse(
                    zip_buffer,
                    media_type=runtime_cfg["zip_media_type"],
                    headers={
                        "Content-Disposition": (
                            "attachment; filename=opendataloader-output.zip"
                        )
                    },
                )

            if isinstance(target_format, str):
                expected_ext = first_format_extension(target_format)
                if expected_ext:
                    filtered = [p for p in outputs if p.suffix.lower() == expected_ext]
                    if filtered:
                        outputs = filtered

            if len(outputs) == 1:
                output = outputs[0]
                media_type = CONFIG["api"]["direct_media_types"].get(
                    inferred_from_accept,
                    CONFIG["api"]["direct_media_types"].get(
                        runtime_cfg["default_response"],
                        "application/octet-stream",
                    ),
                )
                return Response(content=output.read_bytes(), media_type=media_type)

            payload = []
            for out in outputs:
                rel_name = str(out.relative_to(output_dir)).replace("\\", "/")
                suffix = out.suffix.lower()
                if suffix in {".json", ".txt", ".md", ".html"}:
                    content: Any
                    text = out.read_text(encoding="utf-8", errors="replace")
                    if suffix == ".json":
                        try:
                            content = json.loads(text)
                        except Exception:
                            content = text
                    else:
                        content = text
                else:
                    content = None

                payload.append(
                    {
                        "name": rel_name,
                        "size": out.stat().st_size,
                        "content": content,
                    }
                )

            return JSONResponse(content={"outputs": payload, "count": len(payload)})

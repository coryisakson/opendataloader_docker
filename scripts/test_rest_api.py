import json
import sys
from pathlib import Path

import requests

BASE_URL = "http://localhost:8080"
SAMPLES_DIR = Path(__file__).resolve().parents[1] / "samples" / "pdf"
PDF1 = SAMPLES_DIR / "lorem.pdf"
PDF2 = SAMPLES_DIR / "1901.03003.pdf"


def assert_ok(response, context):
    if response.status_code >= 400:
        raise RuntimeError(f"{context} failed: {response.status_code} {response.text}")


def test_health():
    response = requests.get(f"{BASE_URL}/health", timeout=30)
    assert_ok(response, "health")
    payload = response.json()
    assert payload.get("status") == "ok", "health status must be ok"


def test_options():
    response = requests.get(f"{BASE_URL}/options", timeout=30)
    assert_ok(response, "options")
    options = response.json()
    names = {o["name"] for o in options}
    assert "format" in names, "format option must exist"
    assert "hybrid" in names, "hybrid option must exist"


def test_json_accept_single_file():
    with PDF1.open("rb") as handle:
        files = [("files", (PDF1.name, handle, "application/pdf"))]
        response = requests.post(
            f"{BASE_URL}/convert",
            files=files,
            headers={"Accept": "application/json"},
            timeout=300,
        )

    assert_ok(response, "convert json accept")
    assert "application/json" in response.headers.get("Content-Type", "")
    try:
        payload = response.json()
    except json.JSONDecodeError as error:
        raise RuntimeError("Expected JSON response for application/json Accept") from error

    if isinstance(payload, dict) and "outputs" in payload:
        assert payload["count"] >= 1, "outputs should not be empty"
    else:
        assert isinstance(payload, dict), "expected JSON object payload"


def test_markdown_accept_with_format_option():
    with PDF1.open("rb") as handle:
        files = [("files", (PDF1.name, handle, "application/pdf"))]
        response = requests.post(
            f"{BASE_URL}/convert",
            files=files,
            data={"format": "markdown"},
            headers={"Accept": "text/markdown"},
            timeout=300,
        )

    assert_ok(response, "convert markdown accept")
    content_type = response.headers.get("Content-Type", "")
    assert "text/markdown" in content_type, f"unexpected content type: {content_type}"
    assert len(response.text.strip()) > 0, "markdown output should not be empty"


def test_multi_file_zip_response():
    with PDF1.open("rb") as h1, PDF2.open("rb") as h2:
        files = [
            ("files", (PDF1.name, h1, "application/pdf")),
            ("files", (PDF2.name, h2, "application/pdf")),
        ]
        response = requests.post(
            f"{BASE_URL}/convert",
            files=files,
            headers={"Accept": "application/zip"},
            timeout=300,
        )

    assert_ok(response, "convert zip accept")
    assert "application/zip" in response.headers.get("Content-Type", "")
    assert len(response.content) > 0, "zip payload must not be empty"


def test_options_json_overrides_form():
    options_payload = {"format": "text", "keep-line-breaks": True}
    with PDF1.open("rb") as handle:
        files = [("files", (PDF1.name, handle, "application/pdf"))]
        response = requests.post(
            f"{BASE_URL}/convert",
            files=files,
            data={"options": json.dumps(options_payload)},
            headers={"Accept": "text/plain"},
            timeout=300,
        )

    assert_ok(response, "convert with options json")
    assert "text/plain" in response.headers.get("Content-Type", "")


def main():
    if not PDF1.exists() or not PDF2.exists():
        raise FileNotFoundError("Sample PDFs were not found in samples/pdf")

    tests = [
        test_health,
        test_options,
        test_json_accept_single_file,
        test_markdown_accept_with_format_option,
        test_multi_file_zip_response,
        test_options_json_overrides_form,
    ]

    failed = []
    for test in tests:
        try:
            test()
            print(f"[PASS] {test.__name__}")
        except Exception as error:
            failed.append((test.__name__, str(error)))
            print(f"[FAIL] {test.__name__}: {error}")

    if failed:
        print("\nFailures:")
        for name, message in failed:
            print(f"- {name}: {message}")
        sys.exit(1)

    print("\nAll REST API tests passed.")


if __name__ == "__main__":
    main()

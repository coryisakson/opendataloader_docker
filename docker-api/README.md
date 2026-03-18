# OpenDataLoader PDF Docker REST API

This folder provides a config-driven REST wrapper for `opendataloader-pdf`.

## Features

- Accepts an array of PDF streams via multipart form data (`files` field repeated)
- Supports all `opendataloader-pdf` conversion options as input parameters
- Supports `Accept` header-based output negotiation
- Supports YAML or JSON configuration file
- No customer-specific runtime parameters are hard coded

## Endpoints

- `GET /health`
- `GET /options`
- `POST /convert`

## POST /convert input

- `files`: repeated multipart file fields (PDF streams)
- Option parameters: any option from `GET /options`
- `options`: optional JSON object containing options (`name` or `python_name` keys)

### Examples

Single file, infer output format from `Accept`:

```bash
curl -X POST "http://localhost:8080/convert" \
  -H "Accept: application/json" \
  -F "files=@samples/pdf/lorem.pdf"
```

Explicit option parameter:

```bash
curl -X POST "http://localhost:8080/convert" \
  -H "Accept: text/markdown" \
  -F "files=@samples/pdf/lorem.pdf" \
  -F "format=markdown" \
  -F "keep-line-breaks=true"
```

Options JSON payload:

```bash
curl -X POST "http://localhost:8080/convert" \
  -H "Accept: text/plain" \
  -F "files=@samples/pdf/lorem.pdf" \
  -F 'options={"format":"text","sanitize":true}'
```

Multiple files (zip response):

```bash
curl -X POST "http://localhost:8080/convert" \
  -H "Accept: application/zip" \
  -F "files=@samples/pdf/lorem.pdf" \
  -F "files=@samples/pdf/1901.03003.pdf" \
  --output result.zip
```

## Configuration

Set environment variable `APP_CONFIG` to a YAML or JSON config file.

Default in container:

- `/app/docker-api/config.yaml`

Key sections:

- `server`: host/port
- `runtime`: work directory, upload limits, default format behavior
- `api`: media type mapping and direct response media types
- `logging`: log level

Use `docker-api/config.yaml` as the primary config and `docker-api/config.example.json` as JSON format reference.

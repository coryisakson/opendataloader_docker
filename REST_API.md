# REST API Documentation

This document describes the Dockerized OpenDataLoader PDF REST API provided by this repository.

Base URL (local default):

- `http://localhost:8080`

## Overview

The API wraps the `opendataloader-pdf` package and supports:

- single or multiple PDF uploads (`multipart/form-data`)
- all OpenDataLoader conversion options as request parameters
- `Accept` header content negotiation
- ZIP packaging for multi-file or multi-format responses

## Authentication

No authentication is implemented in this project by default.

## Content Negotiation

When `format` is not explicitly provided, output format can be inferred from the `Accept` header.

Supported `Accept` values:

- `application/json`
- `text/plain`
- `text/markdown`
- `text/html`
- `application/pdf`
- `application/zip`

If no supported value is present, the API falls back to configured defaults.

## Endpoints

## `GET /health`

Health check endpoint.

Response `200`:

```json
{"status":"ok"}
```

## `GET /options`

Returns the full option metadata list supported by the current `opendataloader-pdf` runtime.

Response `200` (example excerpt):

```json
[
  {
    "name": "format",
    "python_name": "format",
    "type": "string",
    "required": false,
    "default": null,
    "description": "Output formats ..."
  }
]
```

Use this endpoint as the authoritative source for supported parameters.

## `POST /convert`

Converts uploaded PDF files to one or more output formats.

Request type:

- `multipart/form-data`

Required form fields:

- `files`: one or more file parts (`application/pdf`)

Optional form fields:

- Any conversion option listed by `GET /options`
- `options`: JSON object containing conversion options (using either `name` or `python_name` keys)

Notes:

- If both direct form fields and `options` JSON contain the same option, `options` JSON wins.
- Multiple file uploads are supported by repeating the `files` part.

### Example: Single file to JSON

```bash
curl -X POST "http://localhost:8080/convert" \
  -H "Accept: application/json" \
  -F "files=@samples/pdf/lorem.pdf"
```

### Example: Explicit markdown format

```bash
curl -X POST "http://localhost:8080/convert" \
  -H "Accept: text/markdown" \
  -F "files=@samples/pdf/lorem.pdf" \
  -F "format=markdown"
```

### Example: Options JSON payload

```bash
curl -X POST "http://localhost:8080/convert" \
  -H "Accept: text/plain" \
  -F "files=@samples/pdf/lorem.pdf" \
  -F 'options={"format":"text","keep-line-breaks":true,"sanitize":true}'
```

### Example: Multiple files as ZIP

```bash
curl -X POST "http://localhost:8080/convert" \
  -H "Accept: application/zip" \
  -F "files=@samples/pdf/lorem.pdf" \
  -F "files=@samples/pdf/1901.03003.pdf" \
  --output output.zip
```

## Response Behavior

`POST /convert` returns one of these forms:

- `application/zip`:
  - returned when multiple files are uploaded
  - or when `Accept: application/zip`
  - or when `format` includes multiple values (for example `json,markdown`)
- Direct file response (single output):
  - media type based on negotiated result (`application/json`, `text/markdown`, `text/plain`, `text/html`, `application/pdf`)
- JSON envelope:
  - when multiple outputs remain after filtering and response is not zipped
  - payload shape:

```json
{
  "outputs": [
    {
      "name": "relative/path.ext",
      "size": 1234,
      "content": "...or parsed JSON..."
    }
  ],
  "count": 1
}
```

## Error Handling

Common error responses:

- `400 Bad Request`
  - non-PDF upload extension
  - invalid `options` JSON
  - unsupported option key in `options`
  - invalid/truncated PDF stream
  - parser rejection of incomplete/invalid PDF stream
- `413 Payload Too Large`
  - total uploaded content exceeds configured `max_upload_mb`
- `500 Internal Server Error`
  - conversion failure not mapped to a known client error
  - no output files produced

Error body shape:

```json
{
  "detail": "Error description"
}
```

## Configuration Impact

Runtime behavior is controlled by config (`docker-api/config.yaml` by default):

- `runtime.max_upload_mb`: request upload size limit
- `runtime.infer_format_from_accept`: enable/disable `Accept` inference
- `runtime.default_format`: fallback conversion format
- `runtime.default_response`: fallback response media mapping
- `api.accepted_media_types`: map `Accept` values to formats
- `api.direct_media_types`: map single output formats to response media types

To use a different config file, set environment variable `APP_CONFIG`.

## Testing and Examples

- Request examples: `docker-api/opendataloader-api-examples.http`
- Automated tests: `scripts/test_rest_api.py`

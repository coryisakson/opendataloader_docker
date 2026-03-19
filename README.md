# OpenDataLoader Docker API

This repository provides a Dockerized REST API wrapper around the `opendataloader-pdf` Python package.

The API accepts one or more PDF streams and returns extracted output in multiple formats using content negotiation (`Accept` header) and/or explicit conversion options.

## What OpenDataLoader Does

OpenDataLoader extracts structured content from PDFs for downstream use cases like search, indexing, RAG, and document automation. It can produce formats such as JSON, Markdown, HTML, text, and annotated PDF output through conversion options.

For full product details, capabilities, and documentation, see the official site:

- https://opendataloader.org/

## Prerequisites

- Docker Desktop (or Docker Engine + Compose)
- Python 3.10+ (only needed to run local test script)

## Run the Container

From the repository root:

```bash
docker compose up -d --build
```

Check service health:

```bash
curl http://localhost:8080/health
```

Expected response:

```json
{"status":"ok"}
```

## Test the Container

### Option 1: Run automated API tests

```bash
python scripts/test_rest_api.py
```

This validates:

- `/health` and `/options`
- Single-file conversion with JSON and Markdown responses
- Multi-file ZIP response
- JSON options payload handling

### Option 2: Use REST Client examples

Open:

- `docker-api/opendataloader-api-examples.http`

Run requests directly from VS Code REST Client to test common scenarios.

## Stop the Container

```bash
docker compose down
```

## Configuration

The container reads configuration from:

- `/app/docker-api/config.yaml`

Override with environment variable:

- `APP_CONFIG`

For JSON format reference, see:

- `docker-api/config.example.json`

## Notes

- The API validates uploaded PDF streams and returns clear `400` errors for invalid/truncated uploads.
- The implementation installs and uses `opendataloader-pdf` from PyPI inside the container.

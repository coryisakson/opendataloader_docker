FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_CONFIG=/app/docker-api/config.yaml

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY docker-api /app/docker-api

RUN pip install --no-cache-dir -r /app/docker-api/requirements.txt

EXPOSE 8080

CMD ["python", "/app/docker-api/run_server.py"]

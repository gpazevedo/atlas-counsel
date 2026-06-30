# ATLAS Counsel runtime — FastAPI service + MCP server in one image.
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[service]"

# Durable checkpoint location on a writable volume.
RUN mkdir -p /data
ENV COUNSEL_CHECKPOINT_DB=/data/checkpoints.db

EXPOSE 8000
# Default: HTTP API. Override CMD to run the MCP stdio server instead.
CMD ["uvicorn", "atlas_counsel.service.api:app", "--host", "0.0.0.0", "--port", "8000"]

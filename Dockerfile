# ATLAS Counsel runtime — FastAPI + MCP server in one image.
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[service,qdrant]"

# Per-tenant SQLite checkpoints live here (EFS volume in production).
RUN mkdir -p /data
ENV CHECKPOINT_DIR=/data

EXPOSE 8000
# HTTP + MCP on the same port (MCP mounted at /mcp).
CMD ["uvicorn", "atlas_counsel.service.api:app", "--host", "0.0.0.0", "--port", "8000"]

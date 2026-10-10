FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/
WORKDIR /workspace
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY tests ./tests
COPY templates ./templates
RUN uv sync --frozen --group dev --no-editable
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR=/tmp/uv-cache
USER 1000:1000
ENTRYPOINT ["uv", "run", "--frozen", "--no-sync", "pytest", "-x", "-p", "no:cacheprovider", "-m", "gke", "tests/integration", "-q"]

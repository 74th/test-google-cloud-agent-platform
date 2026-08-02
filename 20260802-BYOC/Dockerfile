FROM python:3.12-slim
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY pyproject.toml ./
COPY byoc_runtime ./byoc_runtime
RUN pip install --no-cache-dir .
USER appuser
EXPOSE 8080
CMD ["uvicorn", "byoc_runtime.app:app", "--host", "0.0.0.0", "--port", "8080"]

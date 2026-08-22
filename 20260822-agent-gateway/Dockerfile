FROM python:3.12-slim

ARG AGENT_GATEWAY_ROOT_CERTIFICATES=""
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    GRPC_DEFAULT_SSL_ROOTS_FILE_PATH=/etc/ssl/certs/ca-certificates.crt \
    NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt \
    AGENT_GATEWAY_ROOT_CERT_302034098528=/etc/ssl/certs/ca-certificates.crt
WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && if [ -n "$AGENT_GATEWAY_ROOT_CERTIFICATES" ]; then \
         printf '%s\n' "$AGENT_GATEWAY_ROOT_CERTIFICATES" > /usr/local/share/ca-certificates/agent-gateway.crt; \
         update-ca-certificates; \
       fi
COPY pyproject.toml README.md ./
COPY agent_service ./agent_service
RUN pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 agent
USER agent

EXPOSE 8080
CMD ["uvicorn", "agent_service.app:app", "--host", "0.0.0.0", "--port", "8080"]

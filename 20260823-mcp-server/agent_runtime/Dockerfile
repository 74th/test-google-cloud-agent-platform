FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    GRPC_DEFAULT_SSL_ROOTS_FILE_PATH=/etc/ssl/certs/ca-certificates.crt \
    NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt \
    PORT=8080

WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates openssl \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=secret,id=agent-gateway-ca,dst=/run/secrets/agent-gateway-ca \
    test -s /run/secrets/agent-gateway-ca \
    && cp /run/secrets/agent-gateway-ca /usr/local/share/ca-certificates/agent-gateway.crt \
    && chmod 0644 /usr/local/share/ca-certificates/agent-gateway.crt \
    && openssl x509 -in /usr/local/share/ca-certificates/agent-gateway.crt -noout \
    && update-ca-certificates

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir \
      "claude-agent-sdk==0.1.9" \
      "fastapi==0.115.14" \
      "google-auth==2.47.0" \
      "google-cloud-aiplatform==1.144.0" \
      "httpx==0.28.1" \
      "uvicorn[standard]==0.35.0"

COPY agent_service ./agent_service
COPY toolspec.json ./toolspec.json

RUN useradd --create-home --uid 1000 agent && chown -R agent:agent /app
USER 1000

EXPOSE 8080
CMD ["uvicorn", "agent_service.app:app", "--host", "0.0.0.0", "--port", "8080"]

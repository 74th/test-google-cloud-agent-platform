FROM node:22.16.0-bookworm-slim

ARG CLAUDE_CODE_VERSION=2.1.227

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:${PATH}"

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl python3 python3-venv \
    && npm install --global "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && python3 -m venv /opt/venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --requirement /tmp/requirements.txt \
    && rm /tmp/requirements.txt

WORKDIR /app
COPY claude_agent_sdk.py test_bq.py ./

# The process stays idle so each validation can be a fresh kubectl exec.
CMD ["python", "-c", "import time; time.sleep(2147483647)"]

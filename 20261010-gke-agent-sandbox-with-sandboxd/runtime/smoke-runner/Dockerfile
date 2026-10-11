FROM python:3.12-slim-bookworm
RUN useradd --system --uid 1000 --no-create-home runner
RUN mkdir -p /opt/runtime/gke_session_sandbox
COPY src/gke_session_sandbox/smoke_runner.py /opt/runtime/gke_session_sandbox/smoke_runner.py
COPY src/gke_session_sandbox/_sandboxd_proto /opt/runtime/gke_session_sandbox/_sandboxd_proto
RUN printf '%s\n' '"""Minimal runtime package for network validation."""' > /opt/runtime/gke_session_sandbox/__init__.py
RUN pip install --no-cache-dir 'grpcio>=1.84,<2' 'protobuf>=7.35.1,<8'
ENV PYTHONPATH=/opt/runtime PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 1000:1000
ENTRYPOINT ["python3", "-m", "gke_session_sandbox.smoke_runner"]

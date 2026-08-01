FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY agent_service ./agent_service
COPY workspace/.claude/skills/bus-schedule/SKILL.md ./workspace/.claude/skills/bus-schedule/SKILL.md
RUN pip install --no-cache-dir .

EXPOSE 8080
CMD ["uvicorn", "agent_service.app:app", "--host", "0.0.0.0", "--port", "8080"]

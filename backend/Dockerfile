# AgentAudit backend — explicit runtime for container deploys.
# Pins Python 3.12 because the pinned dependency set (pydantic-core 2.x,
# asyncpg 0.30) ships prebuilt manylinux wheels only up to cp313; newer
# default Pythons would force source builds without a toolchain.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dependency layer first so it caches independently of source changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# PORT is injected by the platform; fall back to 8000 for local runs.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

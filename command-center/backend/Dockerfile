FROM python:3.12-slim

WORKDIR /app

# Install system deps for cryptography + curl (healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install backend dependencies
COPY command-center/backend/requirements.txt /app/command-center/backend/
RUN pip install --no-cache-dir -r /app/command-center/backend/requirements.txt

# Copy full repo (needed for skills, config, scripts, lib)
COPY . /app

WORKDIR /app/command-center/backend

EXPOSE 8100

ENV CC_REPO_ROOT=/app

# Structured JSON logging in container
ENV LOG_FORMAT=json
ENV LOG_LEVEL=INFO

# Liveness + readiness probes
# /api/health → always 200 (liveness)
# /api/health/ready → 200 once state aggregator has scanned at least once (readiness)
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8100/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]

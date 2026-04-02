FROM python:3.12-slim

WORKDIR /app

# Install backend dependencies
COPY command-center/backend/requirements.txt /app/command-center/backend/
RUN pip install --no-cache-dir -r /app/command-center/backend/requirements.txt

# Copy full repo (needed for skills, config, scripts, lib)
COPY . /app

WORKDIR /app/command-center/backend

EXPOSE 8100

ENV CC_REPO_ROOT=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]

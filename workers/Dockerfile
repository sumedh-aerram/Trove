FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY workers/requirements.txt /app/workers/requirements.txt
RUN pip install --no-cache-dir -r /app/workers/requirements.txt \
    && pip install --no-cache-dir pydantic==2.10.4 pydantic-settings==2.7.1

COPY workers /app/workers
COPY apps/api /app/apps/api
COPY packages /app/packages

ENV PYTHONPATH=/app/workers:/app/apps/api
WORKDIR /app/workers

CMD ["python", "run_daemon.py"]

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 5 -r requirements.txt

# Copy application source
COPY . .

# Railway injects $PORT at runtime; default to 8080 for local Docker
ENV PORT=8080
EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; import os; r = httpx.get(f'http://localhost:{os.environ.get(\"PORT\", 8080)}/health'); assert r.status_code == 200"

CMD python -m uvicorn api_server:app --host 0.0.0.0 --port $PORT

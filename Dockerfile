# --- Stage 1: Build dependencies ---
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build deps for numpy/faiss
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY config.py .
COPY retriever.py .
COPY llm.py .
COPY prompt.py .
COPY main.py .
COPY catalog_prepared.json .

# Cloud Run sets PORT env var (default 8080)
ENV PORT=8080

# Start with uvicorn — no reload in production
CMD exec uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1

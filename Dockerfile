# =============================================================================
# Sean Lead Agent — Production Dockerfile
# Single-stage Python build with pre-built React dashboard
# =============================================================================

FROM python:3.11-slim

# Security: run as non-root
RUN groupadd -r agent && useradd -r -g agent agent

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Copy pre-built dashboard assets
COPY dashboard/dist ./dashboard/dist

# Switch to non-root user
USER agent

# Railway injects PORT env var
ENV PORT=8000
EXPOSE ${PORT}

CMD ["python", "-c", "import os; import uvicorn; uvicorn.run('app.main:app', host='0.0.0.0', port=int(os.environ.get('PORT', '8000')))"]

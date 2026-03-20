# =============================================================================
# Sean Lead Agent — Multi-stage Production Dockerfile
# Builds React dashboard + Python FastAPI backend
# =============================================================================

# --- Stage 1: Build the React dashboard ---
FROM node:20-slim AS frontend-build

WORKDIR /app/dashboard
COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm ci --production=false
COPY dashboard/ ./
RUN npm run build

# --- Stage 2: Python production image ---
FROM python:3.11-slim

# Security: run as non-root
RUN groupadd -r agent && useradd -r -g agent agent

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/ 2>/dev/null || true
COPY alembic.ini ./alembic.ini 2>/dev/null || true

# Copy built dashboard from Stage 1
COPY --from=frontend-build /app/dashboard/dist ./dashboard/dist

# Switch to non-root user
USER agent

# Railway injects PORT env var
ENV PORT=8000
EXPOSE ${PORT}

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

# ==============================================================================
# HostCart Multi-Media Platform - Multi-Stage Container Image
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Frontend SPA Builder
# ------------------------------------------------------------------------------
FROM node:22-alpine AS frontend-builder

WORKDIR /build/frontend

# Install dependencies using clean package definitions
COPY frontend/package*.json ./
RUN npm install

# Copy frontend source and build static distribution
COPY frontend/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Python Application Runtime
# ------------------------------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app

# Ensure Python outputs are sent straight to terminal without buffering
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install Python backend dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and configuration defaults
COPY src/ ./src/
COPY config/ ./config/

# Copy compiled frontend SPA from Stage 1 builder
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

# Expose FastAPI application port
EXPOSE 8000

# Declare persistent mount points for SQLite database and configuration
VOLUME ["/app/data", "/app/config"]

# Start production ASGI web server
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

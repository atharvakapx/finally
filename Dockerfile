# Stage 1: Build Next.js static export
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + static frontend
FROM python:3.12-slim AS app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ ./

# Copy frontend static export into backend static dir
COPY --from=frontend-builder /app/frontend/out /app/backend/static

WORKDIR /app

# Tell FastAPI where to find the static files
ENV STATIC_DIR=/app/backend/static

EXPOSE 8000

CMD ["uv", "run", "--project", "/app/backend", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

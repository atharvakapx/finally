# syntax=docker/dockerfile:1.7

# ---------------------------------------------------------------------------
# Stage 1: Build the Next.js frontend as a static export.
# ---------------------------------------------------------------------------
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Install deps first for better layer caching.
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# Copy the rest of the frontend source and build the static export.
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: Python backend (FastAPI + uv) that also serves the static frontend.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

# Install uv globally.
RUN pip install --no-cache-dir uv

WORKDIR /app

# Backend deps first for better layer caching.
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./backend/
COPY backend/app/__init__.py ./backend/app/__init__.py

WORKDIR /app/backend
RUN uv sync --frozen --no-dev

# Copy the rest of the backend source.
COPY backend/ ./

# Copy the static frontend build into backend/static (served by FastAPI).
COPY --from=frontend-builder /app/frontend/out/ ./static/

# Bind-mount target for the SQLite database (persisted on the host).
RUN mkdir -p /app/db

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------- Stage 1: Build frontend SPA ----------
FROM node:20-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# ---------- Stage 2: Install Python dependencies ----------
FROM python:3.11-slim-bookworm AS python-deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# ---------- Stage 3: Runtime ----------
FROM python:3.11-slim-bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python packages and binaries from deps stage
COPY --from=python-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-deps /usr/local/bin /usr/local/bin

# Built frontend SPA
COPY --from=frontend-build /app/dist ./frontend/dist

# Application source
COPY src/ ./src/
COPY api/ ./api/
COPY scripts/ ./scripts/
COPY pyproject.toml .

# Install the project package (src/) in non-editable mode
RUN pip install --no-cache-dir --no-deps .

# Pre-warm pybaseball's Chadwick register cache so the first pipeline run
# doesn't stall downloading the ZIP from GitHub at container startup.
RUN python -c "from pybaseball.playerid_lookup import chadwick_register; chadwick_register()"

EXPOSE 8000

CMD ["gunicorn", "api.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]

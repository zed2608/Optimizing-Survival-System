# One container: the API (FastAPI) AND the built dashboard on the same address. Public sandbox mode is ON (see pipeline/public_mode.py).
# Build:  docker build -t optimizing-survival .      Run:  docker run -p 8001:8001 optimizing-survival   then open http://localhost:8001
# The host sets PORT (Render: 10000); the default here is 8001.

# ---- 1. build the dashboard (same-origin: VITE_API_BASE empty) ----
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
ENV VITE_API_BASE=
RUN npm run build

# ---- 2. the service ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 \
    OS_PUBLIC_MODE=1 OS_STATE_DIR=/tmp/os_sandbox_state OS_STATIC_DIR=/app/frontend/dist
WORKDIR /app
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY api_v2.py .
COPY pipeline/ pipeline/
COPY fieldpack/ fieldpack/
COPY data/processed/ data/processed/
COPY data/config/ data/config/
COPY data/BRGY_BOUNDARY.* data/LandUses.* data/
COPY frontend/src/new/fieldStatus.json frontend/src/new/fieldStatus.json
COPY --from=web /web/dist/ frontend/dist/

# the score database (git-ignored, 129 MB) travels as a 9.8 MB gzip in deploy/ and is unpacked here; see deploy/MANIFEST.txt
COPY deploy/ /tmp/deploy/
RUN mkdir -p data/processed/scores data/processed/models \
 && gunzip -c /tmp/deploy/site_scores.db.gz > data/processed/scores/site_scores.db \
 && cp /tmp/deploy/score_run.json data/processed/scores/score_run.json \
 && cp /tmp/deploy/rf_site_suitability_meta.json data/processed/models/rf_site_suitability_meta.json \
 && rm -rf /tmp/deploy \
 && useradd --create-home app && chown -R app /app
USER app

EXPOSE 8001
HEALTHCHECK --interval=60s --timeout=10s --start-period=40s \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/ping'%os.environ.get('PORT','8001'),timeout=8)"
CMD ["sh", "-c", "exec python -m uvicorn api_v2:app --host 0.0.0.0 --port ${PORT:-8001}"]

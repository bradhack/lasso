# Build context: repository root (see azure.yaml).
# Stage 1: build the web app so the API can also serve it from the same origin.
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# Stage 2: API + engine + demo data.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY engine /app/engine
RUN pip install /app/engine
COPY services/api/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
COPY services/api/lasso_api /app/lasso_api
COPY data/demo /app/data/demo
COPY --from=web /web/dist /app/web/dist
ENV LASSO_DATA_DIR=/app/data/demo LASSO_WEB_DIST=/app/web/dist
RUN useradd -m lasso && chown -R lasso /app
USER lasso
EXPOSE 8000
# For Docker and local runs (Azure Container Apps uses its own probes).
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
# The same image runs the Match Feed publisher: override the command with `python -m lasso_api.feed`.
CMD ["uvicorn", "lasso_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

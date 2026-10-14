FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
COPY lasso_agents /app/lasso_agents
RUN useradd -m lasso && chown -R lasso /app
USER lasso
EXPOSE 8100
CMD ["uvicorn", "lasso_agents.server:app", "--host", "0.0.0.0", "--port", "8100", "--proxy-headers", "--forwarded-allow-ips", "*"]

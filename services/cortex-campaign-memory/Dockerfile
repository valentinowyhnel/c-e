FROM python:3.12-slim
WORKDIR /app
COPY services/cortex-campaign-memory/pyproject.toml ./pyproject.toml
COPY services/cortex-campaign-memory/cortex_campaign_memory ./cortex_campaign_memory
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "cortex_campaign_memory.main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY cortex_orchestrator ./cortex_orchestrator
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "cortex_orchestrator.main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY cortex_audit ./cortex_audit
COPY tests ./tests
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "cortex_audit.main:app", "--host", "0.0.0.0", "--port", "8080"]

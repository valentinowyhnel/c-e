FROM python:3.12-slim
WORKDIR /app
COPY services/cortex-insider-decay/pyproject.toml ./pyproject.toml
COPY services/cortex-insider-decay/cortex_insider_decay ./cortex_insider_decay
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "cortex_insider_decay.main:app", "--host", "0.0.0.0", "--port", "8080"]

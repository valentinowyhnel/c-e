FROM python:3.12-slim
WORKDIR /app
COPY services/cortex-admin-anomaly/pyproject.toml ./pyproject.toml
COPY services/cortex-admin-anomaly/cortex_admin_anomaly ./cortex_admin_anomaly
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "cortex_admin_anomaly.main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM python:3.12-slim
WORKDIR /app
COPY services/cortex-trust-engine/pyproject.toml ./pyproject.toml
COPY services/cortex-trust-engine/cortex_trust_engine ./cortex_trust_engine
COPY shared/cortex-core/cortex_core ./cortex_core
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "cortex_trust_engine.main:app", "--host", "0.0.0.0", "--port", "8080"]

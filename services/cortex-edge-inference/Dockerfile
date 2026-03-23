FROM python:3.12-slim
WORKDIR /app
COPY services/cortex-edge-inference/pyproject.toml ./pyproject.toml
COPY services/cortex-edge-inference/cortex_edge_inference ./cortex_edge_inference
COPY shared/cortex-core/cortex_core ./cortex_core
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "cortex_edge_inference.main:app", "--host", "0.0.0.0", "--port", "8080"]

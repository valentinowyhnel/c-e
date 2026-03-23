FROM python:3.12-slim
WORKDIR /app
COPY services/cortex-priority-engine/pyproject.toml ./pyproject.toml
COPY services/cortex-priority-engine/cortex_priority_engine ./cortex_priority_engine
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "cortex_priority_engine.main:app", "--host", "0.0.0.0", "--port", "8080"]

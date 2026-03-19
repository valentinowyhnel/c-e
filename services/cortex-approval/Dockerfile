FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY cortex_approval ./cortex_approval
COPY tests ./tests
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "cortex_approval.main:app", "--host", "0.0.0.0", "--port", "8080"]

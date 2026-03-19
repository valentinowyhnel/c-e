FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY sentinel/ sentinel/
RUN pip install --no-cache-dir .
RUN useradd -m -u 1000 cortex
USER cortex
CMD ["python", "-m", "sentinel.main"]

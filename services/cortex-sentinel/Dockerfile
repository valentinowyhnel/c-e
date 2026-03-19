FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir uv
RUN uv sync --no-dev
COPY sentinel/ sentinel/
RUN useradd -m -u 1000 cortex
USER cortex
CMD ["python", "-m", "sentinel.main"]

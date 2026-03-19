FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY app /app/app
COPY config /app/config
RUN pip install --no-cache-dir .

CMD ["python", "-m", "app.serve"]

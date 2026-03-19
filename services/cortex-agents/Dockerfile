FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY cortex_agents ./cortex_agents
RUN pip install --no-cache-dir .
CMD ["python", "-m", "cortex_agents.runner"]

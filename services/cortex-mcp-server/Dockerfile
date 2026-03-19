FROM python:3.12-slim
WORKDIR /app
COPY services/cortex-mcp-server/pyproject.toml ./pyproject.toml
COPY services/cortex-mcp-server/cortex_mcp_server ./cortex_mcp_server
COPY shared/cortex-core/cortex_core ./cortex_core
COPY services/cortex-policy-engine/cortex_policy_engine ./cortex_policy_engine
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "cortex_mcp_server.main:app", "--host", "0.0.0.0", "--port", "8080"]

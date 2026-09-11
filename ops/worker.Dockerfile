FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY bt ./bt
RUN uv sync --extra stream --no-dev --frozen
ENV PATH="/app/.venv/bin:$PATH"

# Airflow that can run the Borrower Truth nightly job (it calls `uv run ...`).
FROM apache/airflow:2.10.2-python3.12
USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
USER airflow

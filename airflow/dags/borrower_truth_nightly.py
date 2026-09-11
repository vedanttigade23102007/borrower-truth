"""Nightly batch: refresh public data, run the seven checks, publish cases.

Each task retries with backoff; the whole run has a 4-hour SLA so it finishes
before business opens. A failed publish parks the run in the dead-letter folder
(bt.pipeline.publish), never losing results.

In the demo the "public data refresh" reuses the synthetic book; in production
this task calls GLEIF, state UCC and court sources through their adapters.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

REPO = "{{ var.value.get('bt_repo', '/workspaces/borrower-truth') }}"
DATA = "{{ var.value.get('bt_data', 'data/out/demo') }}"

default_args = dict(owner="credit-risk-tech", retries=3, retry_delay=timedelta(minutes=5),
                    retry_exponential_backoff=True, sla=timedelta(hours=4))

with DAG("borrower_truth_nightly", start_date=datetime(2026, 9, 1), schedule="0 1 * * *",
         catchup=False, default_args=default_args, tags=["borrower-truth"]) as dag:
    refresh = BashOperator(
        task_id="refresh_public_data",
        bash_command=f"cd {REPO} && test -f {DATA}/manifest.json || uv run python -m bt.datagen.generate --out {DATA}")
    run = BashOperator(
        task_id="run_seven_checks",
        bash_command=f"cd {REPO} && uv run python -m bt.pipeline.run --data {DATA}",
        execution_timeout=timedelta(hours=3))
    publish = BashOperator(
        task_id="publish_cases",
        bash_command=f"cd {REPO} && uv run python -m bt.pipeline.publish --run {DATA}/run")
    replay = BashOperator(
        task_id="replay_dead_letters",
        bash_command=f"cd {REPO} && uv run python -m bt.pipeline.publish --replay",
        trigger_rule="all_done")
    refresh >> run >> publish >> replay

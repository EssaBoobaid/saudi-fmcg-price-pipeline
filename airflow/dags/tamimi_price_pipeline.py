
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator


def run_tamimi_extraction():
    import sys
    from pathlib import Path

    project_root = Path("/opt/project")

    sys.path.insert(0, str(project_root))

    from src.ingestion.extract_tamimi import extract_tamimi_prices

    extract_tamimi_prices()


with DAG(
    dag_id="tamimi_price_pipeline",
    start_date=datetime(2026, 9, 1),
schedule=timedelta(hours=1),
    catchup=False,
    default_args={
        "retries": 1,
        "retry_delay": timedelta(minutes=1),
    },
    tags=["tamimi", "fmcg", "extraction"],
) as dag:

    extract_tamimi = PythonOperator(
        task_id="extract_tamimi_prices",
        python_callable=run_tamimi_extraction,
    )


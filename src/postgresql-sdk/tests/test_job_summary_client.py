import os
from datetime import datetime, timedelta

import pytest

from ltp_postgresql_sdk import JobSummaryClient
from ltp_postgresql_sdk.models import JobSummary as JobSummaryModel
from ltp_storage.data_schema.job_records import JobSummaryRecord


@pytest.fixture
def client():
    os.environ.setdefault("CLUSTER_ID", "test-cluster")
    client = JobSummaryClient(
        connection_str=os.environ["POSTGRES_CONNECTION_STR"],
        schema=os.environ["POSTGRES_SCHEMA"],
    )
    try:
        yield client
    finally:
        try:
            session = client.get_session()
            session.query(JobSummaryModel).filter(
                JobSummaryModel.job_id.like("test-job-js-%")
            ).delete(synchronize_session=False)
            session.commit()
        except Exception:
            pass
        finally:
            session.close()
            client.close()


def _build_record(job_suffix: str, *, exit_category: str = "Succeeded", react_delta: int = 0):
    now = datetime.utcnow() + timedelta(seconds=react_delta)
    return JobSummaryRecord(
        job_id=f"test-job-js-{job_suffix}",
        job_hash=f"hash-{job_suffix}",
        job_name=f"job-{job_suffix}",
        user_name="tester",
        job_state="Succeeded",
        retry_count=0,
        attempt_id=1,
        retry_details={"attempt": 1},
        virtual_cluster="vc1",
        total_gpu_count=4,
        job_priority="high",
        job_duration_hours=1.5,
        total_gpu_hours=6.0,
        idle_gpu_hours=1.0,
        effective_gpu_hours=5.0,
        submission_time=now - timedelta(hours=2),
        launch_time=now - timedelta(hours=1.5),
        completion_time=now,
        created_datetime=now,
        idle_gpu_percentage=10.0,
        assigned_gpu_utilization=0.7,
        effective_gpu_utilization=0.8,
        exit_reason="Completed",
        exit_category=exit_category,
        time_generated=now,
        endpoint="test-cluster",
    )


def test_insert_record(client):
    record = _build_record("insert")
    record_id = client._insert_record(record)
    assert record_id is not None and isinstance(record_id, int) and record_id > 0


def test_insert_job_summaries_batch(client):
    base_time = datetime.utcnow()
    records = [
        {
            "job_id": f"test-job-js-batch-{i}",
            "time_generated": base_time + timedelta(minutes=i),
            "endpoint": "test-cluster",
            "job_state": "Running",
            "submission_time": base_time - timedelta(hours=1),
        }
        for i in range(3)
    ]

    client.insert_job_summaries_batch(records)

    fetched = client._query_records(job_state="Running")
    assert any(r["job_id"].startswith("test-job-js-batch-") for r in fetched)


def test_query_records(client):
    record = _build_record("query")
    client._insert_record(record)

    results = client._query_records(job_id=record.job_id)
    assert results
    assert results[0]["job_id"] == record.job_id
    assert results[0]["user_name"] == "tester"


def test_get_record(client):
    job_id = "test-job-js-get"
    older = _build_record("get-older")
    newer = _build_record("get-newer", react_delta=5)
    newer.job_id = job_id
    older.job_id = job_id
    newer.job_state = "Failed"
    client._insert_record(older)
    client._insert_record(newer)

    record = client._get_record(job_id)
    assert record is not None
    assert record["job_state"] == "Failed"


def test_query_last_completion_time(client):
    record = _build_record("completion")
    client._insert_record(record)

    last = client.query_last_completion_time(endpoint="test-cluster")
    assert last is not None
    assert abs(last.timestamp() - record.completion_time.timestamp()) < 1


def test_query_unknown_category_records(client):
    within = _build_record("unknown", exit_category="Unknown")
    old = _build_record("older", exit_category="hardware-failure")
    client._insert_record(within)
    client._insert_record(old)

    results = client.query_unknown_category_records(retain_time="30d", endpoint="test-cluster")
    assert results
    job_ids = {r["job_id"] for r in results}
    assert within.job_id in job_ids
    assert old.job_id not in job_ids


def test_query_job_summaries_by_job_ids(client):
    job_id = "test-job-js-list"
    early = _build_record("list-early")
    later = _build_record("list-late", react_delta=10)
    early.job_id = job_id
    later.job_id = job_id
    later.job_state = "Running"

    client._insert_record(early)
    client._insert_record(later)

    results = client.query_job_summaries_by_job_ids([job_id], endpoint="test-cluster")
    assert len(results) == 1
    assert results[0]["job_state"] == "Running"

import os
from datetime import datetime, timedelta
from typing import Optional

import pytest

from ltp_postgresql_sdk import JobReactTimeClient
from ltp_postgresql_sdk.models import JobReactTime as JobReactTimeModel
from ltp_storage.data_schema.job_records import JobReactTimeRecord


@pytest.fixture
def client():
    os.environ.setdefault("CLUSTER_ID", "test-cluster")
    client = JobReactTimeClient(
        connection_str=os.environ["POSTGRES_CONNECTION_STR"],
        schema=os.environ["POSTGRES_SCHEMA"],
    )
    try:
        yield client
    finally:
        try:
            session = client.get_session()
            session.query(JobReactTimeModel).filter(
                JobReactTimeModel.job_id.like("test-job-jrt-%")
            ).delete(synchronize_session=False)
            session.commit()
        except Exception:
            pass
        finally:
            session.close()
            client.close()


def _build_record(suffix: str, *, react_time: Optional[float] = 12.5, delta_minutes: int = 0):
    return JobReactTimeRecord(
        job_id=f"test-job-jrt-{suffix}",
        react_time=react_time,
        job_hash=f"hash-{suffix}",
        time_generated=datetime.utcnow() + timedelta(minutes=delta_minutes),
        endpoint="test-cluster",
    )


def test_insert_record(client):
    record = _build_record("insert")
    record_id = client._insert_record(record)
    assert record_id is not None and isinstance(record_id, int) and record_id > 0


def test_insert_job_react_times_batch(client):
    base_time = datetime.utcnow()
    records = [
        {
            "job_id": f"test-job-jrt-batch-{i}",
            "react_time": 20 + i,
            "job_hash": f"hash-batch-{i}",
            "time_generated": base_time + timedelta(minutes=i),
            "endpoint": "test-cluster",
        }
        for i in range(3)
    ]

    client.insert_job_react_times_batch(records)

    fetched = client._query_records(job_id="test-job-jrt-batch-1")
    assert fetched and fetched[0]["react_time"] == 21


def test_query_records(client):
    record = _build_record("query", react_time=30.0)
    client._insert_record(record)

    results = client._query_records(job_id=record.job_id)
    assert results
    assert results[0]["job_id"] == record.job_id
    assert results[0]["react_time"] == pytest.approx(30.0)


def test_get_record(client):
    job_id = "test-job-jrt-get"
    older = _build_record("get-older", react_time=10.0, delta_minutes=-5)
    newer = _build_record("get-newer", react_time=15.0, delta_minutes=5)
    older.job_id = job_id
    newer.job_id = job_id
    client._insert_record(older)
    client._insert_record(newer)

    record = client._get_record(job_id)
    assert record is not None
    assert record["react_time"] == pytest.approx(15.0)


def test_get_average_react_time(client):
    for value in [12.0, 18.0, 24.0]:
        client._insert_record(_build_record(f"avg-{value}", react_time=value))

    average = client.get_average_react_time()
    assert average is not None
    assert average == pytest.approx((12.0 + 18.0 + 24.0) / 3)


def test_query_unknown_react_records(client):
    within = _build_record("unknown", react_time=None)
    old = _build_record("old", react_time=None, delta_minutes=-60 * 24 * 45)
    old.job_hash = "valid-hash"
    client._insert_record(within)
    client._insert_record(old)

    results = client.query_unknown_react_records(retain_time="40d", endpoint="test-cluster")
    assert results
    job_ids = {r["job_id"] for r in results}
    assert within.job_id in job_ids
    assert old.job_id not in job_ids

import os
from datetime import datetime, timedelta

import pytest

from ltp_postgresql_sdk import AlertClient
from ltp_postgresql_sdk.models import AlertRecord as AlertRecordModel
from ltp_storage.data_schema.alert_records import AlertRecordData


@pytest.fixture
def client():
    os.environ.setdefault("CLUSTER_ID", "test-cluster")
    client = AlertClient(
        connection_str=os.environ["POSTGRES_CONNECTION_STR"],
        schema=os.environ["POSTGRES_SCHEMA"],
    )
    try:
        yield client
    finally:
        try:
            session = client.get_session()
            session.query(AlertRecordModel).filter(
                AlertRecordModel.alertname.like("test-alert-%")
            ).delete(synchronize_session=False)
            session.commit()
        except Exception:
            pass
        finally:
            session.close()
            client.close()


def _build_alert(suffix: str, *, severity: str = "warning", delta_minutes: int = 0):
    timestamp = datetime.utcnow() + timedelta(minutes=delta_minutes)
    return AlertRecordData(
        timestamp=timestamp,
        alertname=f"test-alert-{suffix}",
        severity=severity,
        summary=f"Test alert {suffix}",
        node_name=f"node-{suffix}",
        labels={"job": "example"},
        annotations={"info": "details"},
        endpoint="test-cluster",
    )


def test_insert_alert(client):
    alert = _build_alert("insert")
    alert_id = client.insert_alert(alert)
    assert alert_id is not None and isinstance(alert_id, int) and alert_id > 0


def test_insert_alerts_batch(client):
    alerts = [_build_alert(f"batch-{i}") for i in range(3)]
    ids = client.insert_alerts_batch(alerts)
    assert ids and len(ids) == 3


def test_query_alerts_by_filters(client):
    warning_alert = _build_alert("filter-warning", severity="warning")
    critical_alert = _build_alert("filter-critical", severity="critical", delta_minutes=5)
    client.insert_alerts_batch([warning_alert, critical_alert])

    results = client.query_alerts(severity="critical", node_name=critical_alert.node_name)
    assert results
    assert all(r["severity"] == "critical" for r in results)
    assert results[0]["node_name"] == critical_alert.node_name


def test_query_alerts_by_nodes(client):
    alert1 = _build_alert("nodes-1")
    alert2 = _build_alert("nodes-2")
    alert3 = _build_alert("nodes-3")
    client.insert_alerts_batch([alert1, alert2, alert3])

    results = client.query_alerts(nodes=[alert1.node_name, alert3.node_name])
    node_names = {r["node_name"] for r in results}
    assert alert1.node_name in node_names
    assert alert3.node_name in node_names
    assert alert2.node_name not in node_names

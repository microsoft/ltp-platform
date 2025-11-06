# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for NodeActionClient."""

import pytest
from datetime import datetime
import os

from ltp_postgresql_sdk.features.node_action.client import NodeActionClient
from ltp_postgresql_sdk.models import NodeAction as NodeActionModel
from ltp_storage.data_schema.node_action import NodeAction as NodeActionRecord


@pytest.fixture
def client():
    """Create a test client with cleanup."""
    client = NodeActionClient(
        connection_str=os.environ["POSTGRES_CONNECTION_STR"],
        schema=os.environ["POSTGRES_SCHEMA"]
    )
    try:
        yield client
    finally:
        # Cleanup all test records
        try:
            session = client.get_session()
            session.query(NodeActionModel).filter(
                NodeActionModel.category == "test"
            ).delete(synchronize_session=False)
            session.commit()
        except Exception:
            pass
        finally:
            client.close()


def test_insert_record(client):
    """Test inserting a single action record via _insert_record."""
    record = NodeActionRecord(
        Timestamp=datetime.utcnow(),
        HostName="test-worker-01",
        NodeId="test-node-001",
        Action="test-action",
        Reason="Test reason",
        Detail="Test detail",
        Category="test",
        Endpoint="http://test.example.com"
    )
    
    record_id = client._insert_record(record)
    assert record_id is not None
    assert isinstance(record_id, int)
    assert record_id > 0


def test_query_records(client):
    """Test querying action records via _query_records."""
    # Insert a test record first
    record = NodeActionRecord(
        Timestamp=datetime.utcnow(),
        HostName="test-worker-02",
        NodeId="test-node-002",
        Action="test-query",
        Reason="Test query reason",
        Detail="Test query detail",
        Category="test",
        Endpoint="http://test.example.com"
    )
    client._insert_record(record)
    
    # Query the records
    results = client._query_records(hostname="test-worker-02", limit=10)
    assert len(results) > 0
    assert results[0]["hostname"] == "test-worker-02"


def test_batch_insert(client):
    """Test batch insertion of action records via _insert_records_batch."""
    records = [
        NodeActionRecord(
            Timestamp=datetime.utcnow(),
            HostName=f"test-worker-{i:02d}",
            NodeId=f"test-node-{i:03d}",
            Action="batch-test",
            Reason="Batch test reason",
            Detail=f"Batch test detail {i}",
            Category="test",
            Endpoint="http://test.example.com"
        )
        for i in range(1, 6)
    ]
    
    record_ids = client._insert_records_batch(records)
    assert len(record_ids) == 5
    assert all(isinstance(rid, int) for rid in record_ids)

def test_get_latest_record(client):
    """Test retrieving the latest action for a hostname via _get_latest_record."""
    now = datetime.utcnow()
    older = NodeActionRecord(
        Timestamp=now,
        HostName="test-worker-la",
        NodeId="node-la",
        Action="test-action",
        Reason="older",
        Detail="older",
        Category="test",
        Endpoint="test-endpoint",
    )
    newer = NodeActionRecord(
        Timestamp=now.replace(microsecond=now.microsecond + 1),
        HostName="test-worker-la",
        NodeId="node-la",
        Action="test-action",
        Reason="newer",
        Detail="newer",
        Category="test",
        Endpoint="test-endpoint",
    )
    client._insert_record(older)
    client._insert_record(newer)

    latest = client._get_latest_record(hostname="test-worker-la")
    assert latest is not None
    assert latest["reason"] == "newer"


def test_update_attribute_table(client):
    """Test attribute table population (no exception)."""
    client.update_attribute_table()


def test_get_node_actions(client):
    """Test Kusto-compatible get_node_actions interface."""
    start = datetime.utcnow()
    print(start)
    print(start.isoformat())
    recs = [
        NodeActionRecord(
            Timestamp=start,
            HostName="test-worker-gn",
            NodeId="node-gn",
            Action="available-cordoned",
            Reason="r1",
            Detail="d1",
            Category="test",
            Endpoint="e1",
        ),
        NodeActionRecord(
            Timestamp=start,
            HostName="test-worker-gn",
            NodeId="node-gn",
            Action="cordoned-triaged_platform",
            Reason="r2",
            Detail="d2",
            Category="test",
            Endpoint="e1",
        ),
    ]
    client._insert_records_batch(recs)
    results = client.get_node_actions(
        node="test-worker-gn", start_time=start, end_time=start
    )
    assert isinstance(results, list)
    assert len(results) >= 2


def test_get_latest_node_action(client):
    """Test Kusto-compatible latest node action retrieval."""
    rec = NodeActionRecord(
        Timestamp=datetime.utcnow(),
        HostName="test-worker-glna",
        NodeId="node-glna",
        Action="available-cordoned",
        Reason="cordon",
        Detail="cordon detail",
        Category="test",
        Endpoint="e1",
    )
    client._insert_record(rec)
    latest = client.get_latest_node_action("test-worker-glna")
    assert latest is not None
    assert latest.HostName == "test-worker-glna"


def test_update_node_action(client):
    """Test Kusto-compatible update_node_action insertion path."""
    client.update_node_action(
        node="test-worker-una",
        action="available-cordoned",
        timestamp=datetime.utcnow(),
        reason="cordon",
        detail="by test",
        category="test",
    )
    results = client._query_records(hostname="test-worker-una", action="available-cordoned")
    assert len(results) >= 1


def test_get_last_update_time():
    """Test retrieving last update time filtered by endpoint."""
    import os as _os
    _os.environ["CLUSTER_ID"] = "test-cluster"
    local_client = NodeActionClient(
        connection_str=_os.environ["POSTGRES_CONNECTION_STR"],
        schema=_os.environ["POSTGRES_SCHEMA"],
    )
    try:
        rec = NodeActionRecord(
            Timestamp=datetime.utcnow(),
            HostName="test-worker-glut",
            NodeId="node-glut",
            Action="available-cordoned",
            Reason="cordon",
            Detail="cordon detail",
            Category="test",
            Endpoint="test-cluster",
        )
        local_client._insert_record(rec)
        last = local_client.get_last_update_time()
        assert last is None or isinstance(last, datetime)
    finally:
        # cleanup
        try:
            s = local_client.get_session()
            s.query(NodeActionModel).filter(NodeActionModel.category == "test").delete(synchronize_session=False)
            s.commit()
        except Exception:
            pass
        local_client.close()


def test_find_triaged_failure(client):
    """Test triaged failure detection between cordon and available."""
    from datetime import timedelta
    base = datetime.utcnow()
    hostname = "test-worker-triage"

    # Insert cordon
    rec1 = NodeActionRecord(
        Timestamp=base,
        HostName=hostname,
        NodeId="node-triage",
        Action="available-cordoned",
        Reason="cordon",
        Detail="cordon",
        Category="test",
        Endpoint="e1",
    )
    client._insert_record(rec1)

    # Insert triaged action after cordon
    rec2 = NodeActionRecord(
        Timestamp=base + timedelta(seconds=5),
        HostName=hostname,
        NodeId="node-triage",
        Action="cordoned-triaged_platform",
        Reason="triaged",
        Detail="triaged",
        Category="test",
        Endpoint="e1",
    )
    client._insert_record(rec2)

    # Insert next available after triage
    rec3 = NodeActionRecord(
        Timestamp=base + timedelta(seconds=10),
        HostName=hostname,
        NodeId="node-triage",
        Action="triaged_platform-available",
        Reason="available",
        Detail="available",
        Category="test",
        Endpoint="e1",
    )
    client._insert_record(rec3)

    triaged = client.find_triaged_failure(
        node_name=hostname,
        completed_time_ms=int((base + timedelta(seconds=12)).timestamp() * 1000),
        launched_time_ms=int((base - timedelta(seconds=1)).timestamp() * 1000),
    )
    assert isinstance(triaged, list)
    assert any(getattr(a, "Action", None) == "cordoned-triaged_platform" for a in triaged)


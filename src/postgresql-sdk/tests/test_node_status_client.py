# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for NodeStatusClient."""

import pytest
import os
from datetime import datetime
from ltp_postgresql_sdk import NodeStatusClient
from ltp_postgresql_sdk.models import NodeStatus as NodeStatusModel
from ltp_postgresql_sdk.features.node_status.models import NodeStatusRecord


@pytest.fixture
def client():
    """Create a test client with cleanup."""
    client = NodeStatusClient(
        connection_str=os.environ["POSTGRES_CONNECTION_STR"],
        schema=os.environ["POSTGRES_SCHEMA"]
    )
    try:
        yield client
    finally:
        # Cleanup all test records
        try:
            session = client.get_session()
            session.query(NodeStatusModel).filter(
                NodeStatusModel.category == "test"
            ).delete(synchronize_session=False)
            session.commit()
        except Exception:
            pass
        finally:
            client.close()


def test_insert_status(client):
    """Test inserting a single status record."""
    record = NodeStatusRecord(
        timestamp=datetime.utcnow(),
        hostname="test-worker-01",
        node_id="test-node-001",
        status="healthy",
        reason="Test reason",
        detail="Test detail",
    )
    
    record_id = client.insert_status(record)
    assert record_id is not None
    assert isinstance(record_id, int)
    assert record_id > 0


def test_query_statuses(client):
    """Test querying status records."""
    # Insert a test record first
    record = NodeStatusRecord(
        timestamp=datetime.utcnow(),
        hostname="test-worker-02",
        node_id="test-node-002",
        status="healthy",
        reason="Test query reason",
        detail="Test query detail"
    )
    client.insert_status(record)
    
    # Query the records
    results = client.query_statuses(hostname="test-worker-02", limit=10)
    assert len(results) > 0
    assert results[0]["hostname"] == "test-worker-02"


def test_get_latest_status(client):
    """Test getting the latest status for a node."""
    # Insert a test record
    record = NodeStatusRecord(
        timestamp=datetime.utcnow(),
        hostname="test-worker-03",
        node_id="test-node-003",
        status="healthy",
        reason="Latest test",
        detail="Latest test detail"
    )
    client.insert_status(record)
    
    # Get latest status
    latest = client.get_latest_status(hostname="test-worker-03")
    assert latest is not None
    assert latest["hostname"] == "test-worker-03"
    assert latest["status"] == "healthy"


def test_batch_insert(client):
    """Test batch insertion of status records."""
    records = [
        NodeStatusRecord(
            timestamp=datetime.utcnow(),
            hostname=f"test-worker-{i:02d}",
            node_id=f"test-node-{i:03d}",
            status="healthy",
            reason="Batch test reason",
            detail=f"Batch test detail {i}"
        )
        for i in range(1, 6)
    ]
    
    record_ids = client.insert_statuses_batch(records)
    assert len(record_ids) == 5
    assert all(isinstance(rid, int) for rid in record_ids)



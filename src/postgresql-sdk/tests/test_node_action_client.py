# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for NodeActionClient."""

import pytest
from datetime import datetime
import os
from ltp_postgresql_sdk import NodeActionClient
from ltp_postgresql_sdk.models import NodeAction as NodeActionModel
from ltp_postgresql_sdk.features.node_action.models import NodeActionRecord


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


def test_insert_action(client):
    """Test inserting a single action record."""
    record = NodeActionRecord(
        timestamp=datetime.utcnow(),
        hostname="test-worker-01",
        node_id="test-node-001",
        action="test-action",
        reason="Test reason",
        detail="Test detail",
        category="test",
        endpoint="http://test.example.com"
    )
    
    record_id = client.insert_action(record)
    assert record_id is not None
    assert isinstance(record_id, int)
    assert record_id > 0


def test_query_actions(client):
    """Test querying action records."""
    # Insert a test record first
    record = NodeActionRecord(
        timestamp=datetime.utcnow(),
        hostname="test-worker-02",
        node_id="test-node-002",
        action="test-query",
        reason="Test query reason",
        detail="Test query detail",
        category="test",
        endpoint="http://test.example.com"
    )
    client.insert_action(record)
    
    # Query the records
    results = client.query_actions(hostname="test-worker-02", limit=10)
    assert len(results) > 0
    assert results[0]["hostname"] == "test-worker-02"


def test_batch_insert(client):
    """Test batch insertion of action records."""
    records = [
        NodeActionRecord(
            timestamp=datetime.utcnow(),
            hostname=f"test-worker-{i:02d}",
            node_id=f"test-node-{i:03d}",
            action="batch-test",
            reason="Batch test reason",
            detail=f"Batch test detail {i}",
            category="test",
            endpoint="http://test.example.com"
        )
        for i in range(1, 6)
    ]
    
    record_ids = client.insert_actions_batch(records)
    assert len(record_ids) == 5
    assert all(isinstance(rid, int) for rid in record_ids)


def test_count_actions(client):
    """Test counting action records."""
    count = client.count_actions(category="test")
    assert isinstance(count, int)
    assert count >= 0



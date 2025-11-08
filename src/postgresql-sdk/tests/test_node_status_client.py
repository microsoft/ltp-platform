# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Tests for NodeStatusClient."""

import pytest
import os
from datetime import datetime
from ltp_postgresql_sdk import NodeStatusClient
from ltp_postgresql_sdk.models import NodeStatus as NodeStatusModel
from ltp_storage.data_schema.node_status import NodeStatusRecord


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
        # Cleanup all test records by test hostname prefix
        try:
            session = client.get_session()
            session.query(NodeStatusModel).filter(
                NodeStatusModel.hostname.like("test-%")
            ).delete(synchronize_session=False)
            session.commit()
        except Exception:
            pass
        finally:
            client.close()


def test_insert_record(client):
    """Test inserting a single status record via _insert_record."""
    record = NodeStatusRecord(
        Timestamp=datetime.utcnow(),
        HostName="test-worker-01",
        NodeId="test-node-001",
        Status="available",
        Endpoint="e1",
    )

    record_id = client._insert_record(record)
    assert record_id is not None
    assert isinstance(record_id, int)
    assert record_id > 0


def test_query_records(client):
    """Test querying status records via _query_records."""
    # Insert a test record first
    record = NodeStatusRecord(
        Timestamp=datetime.utcnow(),
        HostName="test-worker-02",
        NodeId="test-node-002",
        Status="cordoned",
        Endpoint="e1",
    )
    client._insert_record(record)
    
    # Query the records
    results = client._query_records(hostname="test-worker-02", limit=10)
    assert len(results) > 0
    assert results[0]["hostname"] == "test-worker-02"


def test_get_latest_record(client):
    """Test getting the latest status for a node via _get_latest_record."""
    # Insert two records
    now = datetime.utcnow()
    older = NodeStatusRecord(
        Timestamp=now,
        HostName="test-worker-03",
        NodeId="test-node-003",
        Status="available",
        Endpoint="e1",
    )
    newer = NodeStatusRecord(
        Timestamp=datetime.utcnow(),
        HostName="test-worker-03",
        NodeId="test-node-003",
        Status="cordoned",
        Endpoint="e1",
    )
    client._insert_record(older)
    client._insert_record(newer)

    latest = client._get_latest_record(hostname="test-worker-03")
    assert latest is not None
    assert latest["hostname"] == "test-worker-03"
    assert latest["status"] == "cordoned"


def test_batch_insert(client):
    """Test batch insertion of status records via _insert_records_batch."""
    records = [
        NodeStatusRecord(
            Timestamp=datetime.utcnow(),
            HostName=f"test-worker-{i:02d}",
            NodeId=f"test-node-{i:03d}",
            Status="available",
            Endpoint="e1",
        )
        for i in range(1, 6)
    ]
    
    record_ids = client._insert_records_batch(records)
    assert len(record_ids) == 5
    assert all(isinstance(rid, int) for rid in record_ids)


def test_update_attribute_table_and_get_status_group(client):
    """Test attribute table population and group retrieval."""
    client.update_attribute_table()
    group = client.get_status_group("cordoned")
    assert group is None or isinstance(group, str)
    if group is not None:
        assert group == "Cordon"


def test_get_transition_action(client):
    """Test transition action label utility."""
    action = client.get_transition_action("available", "cordoned")
    assert action == "available-cordoned"


def test_get_node_status(client):
    """Test getting node status via compatibility interface."""
    # Insert two statuses
    t1 = datetime.utcnow()
    rec1 = NodeStatusRecord(
        Timestamp=t1,
        HostName="test-worker-gns",
        NodeId="node-gns",
        Status="available",
        Endpoint="e1",
    )
    rec2 = NodeStatusRecord(
        Timestamp=datetime.utcnow(),
        HostName="test-worker-gns",
        NodeId="node-gns",
        Status="cordoned",
        Endpoint="e1",
    )
    client._insert_record(rec1)
    client._insert_record(rec2)

    # Latest
    latest = client.get_node_status("test-worker-gns")
    assert latest is not None
    assert latest.HostName == "test-worker-gns"
    assert latest.Status == "cordoned"

    # As of time t1
    at_time = client.get_node_status("test-worker-gns", timestamp=t1)
    assert at_time is not None
    assert at_time.Status == "available"


def test_update_node_status(client):
    """Test updating node status via compatibility interface."""
    new_status = client.update_node_status(
        hostname="test-worker-uns",
        to_status="cordoned",
        timestamp=datetime.utcnow(),
    )
    assert new_status == "cordoned"
    latest = client._get_latest_record(hostname="test-worker-uns")
    assert latest is not None
    assert latest["status"] == "cordoned"


def test_get_nodes_by_status(client):
    """Test retrieving nodes by their latest status."""
    # Insert records for two nodes; latest status cordoned
    recs = [
        NodeStatusRecord(Timestamp=datetime.utcnow(), HostName="test-worker-gbs-1", NodeId="n1", Status="available", Endpoint="e1"),
        NodeStatusRecord(Timestamp=datetime.utcnow(), HostName="test-worker-gbs-1", NodeId="n1", Status="cordoned", Endpoint="e1"),
        NodeStatusRecord(Timestamp=datetime.utcnow(), HostName="test-worker-gbs-2", NodeId="n2", Status="available", Endpoint="e1"),
        NodeStatusRecord(Timestamp=datetime.utcnow(), HostName="test-worker-gbs-2", NodeId="n2", Status="cordoned", Endpoint="e1"),
        NodeStatusRecord(Timestamp=datetime.utcnow(), HostName="test-worker-gbs-3", NodeId="n3", Status="available", Endpoint="e1"),
    ]
    client._insert_records_batch(recs)

    result = client.get_nodes_by_status("cordoned")
    assert isinstance(result, list)
    hosts = {r.HostName for r in result}
    assert "test-worker-gbs-1" in hosts and "test-worker-gbs-2" in hosts



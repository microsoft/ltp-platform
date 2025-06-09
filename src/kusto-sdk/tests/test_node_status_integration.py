import os
import pytest
from datetime import datetime, timedelta
from ltp_kusto_sdk.features.node_status.client import NodeStatusClient
from ltp_kusto_sdk.features.node_status.models import NodeStatus


@pytest.fixture
def node_status_client():
    """Create a NodeStatusClient instance for testing."""
    return NodeStatusClient()


@pytest.fixture
def test_nodes_data():
    """Sample test data for nodes with different statuses."""
    current_time = datetime.utcnow()
    return [{
        "hostname":
        "test-node-1",
        "status_history":
        [(current_time - timedelta(hours=2), NodeStatus.NEW.value),
         (current_time - timedelta(hours=1), NodeStatus.AVAILABLE.value),
         (current_time, NodeStatus.CORDONED.value)]
    }, {
        "hostname":
        "test-node-2",
        "status_history":
        [(current_time - timedelta(hours=2), NodeStatus.NEW.value),
         (current_time - timedelta(hours=1), NodeStatus.CORDONED.value),
         (current_time, NodeStatus.AVAILABLE.value)]
    }, {
        "hostname":
        "test-node-3",
        "status_history":
        [(current_time - timedelta(hours=1), NodeStatus.NEW.value),
         (current_time, NodeStatus.CORDONED.value)]
    }]


@pytest.mark.integration
class TestNodeStatusIntegration:
    """Integration tests for NodeStatus functionality."""

    def test_get_nodes_by_status(self, node_status_client, test_nodes_data):
        """Test getting nodes by their latest status."""
        # Setup: Insert test data
        for node in test_nodes_data:
            for timestamp, status in node["status_history"]:
                node_status_client.update_node_status(
                    hostname=node["hostname"],
                    to_status=status,
                    timestamp=timestamp)

        # Test: Get nodes with current status CORDONED
        cordoned_nodes = node_status_client.get_nodes_by_status(
            NodeStatus.CORDONED.value)

        # Verify: Only nodes with latest status CORDONED are returned
        assert len(cordoned_nodes) == 2
        cordoned_hostnames = {node["HostName"] for node in cordoned_nodes}
        assert "test-node-1" in cordoned_hostnames
        assert "test-node-3" in cordoned_hostnames
        assert "test-node-2" not in cordoned_hostnames  # Should not be included as it's now AVAILABLE

    def test_get_nodes_by_status_with_timestamp(self, node_status_client,
                                                test_nodes_data):
        """Test getting nodes by status at a specific point in time."""
        # Setup: Insert test data
        for node in test_nodes_data:
            for timestamp, status in node["status_history"]:
                node_status_client.update_node_status(
                    hostname=node["hostname"],
                    to_status=status,
                    timestamp=timestamp)

        # Test: Get nodes status one hour ago
        reference_time = datetime.utcnow() - timedelta(hours=1)
        cordoned_nodes = node_status_client.get_nodes_by_status(
            NodeStatus.CORDONED.value, as_of_time=reference_time)

        # Verify: Only node-2 was cordoned at that time
        assert len(cordoned_nodes) == 1
        assert cordoned_nodes[0]["HostName"] == "test-node-2"

    def test_get_nodes_by_status_empty_result(self, node_status_client):
        """Test getting nodes by a status that no node has."""
        # Test: Get nodes with a status that doesn't exist
        nodes = node_status_client.get_nodes_by_status("nonexistent_status")

        # Verify: Should return empty list
        assert isinstance(nodes, list)
        assert len(nodes) == 0

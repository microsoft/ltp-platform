import pytest
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from ltp_kusto_sdk.features.node_action.client import NodeActionClient
from ltp_kusto_sdk.features.node_action.models import NodeAction
from ltp_kusto_sdk.utils.node_util import Node

# Test constants
TEST_CLUSTER = "https://test-cluster.kusto.windows.net"
TEST_DATABASE = "TestDB"
TEST_ACTION_TABLE = "TestNodeActionRecord"
TEST_ATTRIBUTE_TABLE = "TestNodeActionAttributes"
TEST_ENDPOINT = "test-wcu"


@pytest.fixture
def mock_env(monkeypatch):
    """Set up test environment variables"""
    monkeypatch.setenv("CLUSTER_ID", TEST_ENDPOINT)
    monkeypatch.setenv("LTP_KUSTO_CLUSTER_URI", TEST_CLUSTER)
    monkeypatch.setenv("LTP_KUSTO_DATABASE_NAME", TEST_DATABASE)
    monkeypatch.setenv("KUSTO_NODE_ACTION_TABLE_NAME", TEST_ACTION_TABLE)
    monkeypatch.setenv("KUSTO_NODE_ACTION_ATTRIBUTE_TABLE_NAME",
                       TEST_ATTRIBUTE_TABLE)


@pytest.fixture
def mock_kusto_client():
    """Create a mock KustoManageClient"""
    with patch('ltp_kusto_sdk.base.KustoManageClient') as mock:
        client = MagicMock()
        # Setup default return values
        client.execute_query.return_value = []
        client.execute_command.return_value = None
        mock.return_value = client
        yield client


@pytest.fixture
def mock_node():
    """Create a mock Node instance"""
    with patch('ltp_kusto_sdk.features.node_action.client.Node') as mock:
        node = MagicMock()
        # Setup default return values
        node.get_vm_node_id_by_hostname.return_value = "test-node-id"
        mock.return_value = node
        yield node


@pytest.fixture
def client(mock_env, mock_kusto_client, mock_node):
    """Create a NodeActionClient instance with all dependencies mocked"""
    return NodeActionClient()


class TestNodeActionClient:

    def test_initialization(self, client, mock_kusto_client):
        """Test NodeActionClient initialization"""
        assert client.endpoint == TEST_ENDPOINT
        assert client.cluster == TEST_CLUSTER
        assert client.database == TEST_DATABASE
        assert client.table_name == TEST_ACTION_TABLE
        assert client.attribute_table_name == TEST_ATTRIBUTE_TABLE
        mock_kusto_client.assert_not_called(
        )  # Client should be lazy-initialized

    def test_create_table_failure(self, client, mock_kusto_client):
        """Test create_table method failure handling"""
        # Setup mock to raise exception
        mock_kusto_client.execute_command.side_effect = Exception(
            "Database error")

        with pytest.raises(RuntimeError) as exc_info:
            client.create_table()
        assert "Failed to create table" in str(exc_info.value)
        assert mock_kusto_client.execute_command.called

    def test_create_attribute_table(self, client, mock_kusto_client):
        """Test create_attribute_table method"""
        client.create_attribute_table()
        mock_kusto_client.execute_command.assert_called_once()
        create_call = mock_kusto_client.execute_command.call_args[0][0]
        assert TEST_ATTRIBUTE_TABLE in create_call
        assert "Action" in create_call
        assert "Phase" in create_call

    def test_update_node_action(self, client, mock_kusto_client, mock_node):
        """Test update_node_action method"""
        test_node = "test-node-1"
        test_node_id = "node-123"
        timestamp = datetime.utcnow()

        # Setup mock return values
        mock_node.get_vm_node_id_by_hostname.return_value = test_node_id

        # Call method under test
        client.update_node_action(node=test_node,
                                  action="available-cordoned",
                                  timestamp=timestamp.isoformat(),
                                  reason="Test reason",
                                  detail="Test details",
                                  category="Test")

        # Verify Kusto command
        insert_call = mock_kusto_client.execute_command.call_args[0][0]
        assert ".ingest inline into table" in insert_call
        assert TEST_ACTION_TABLE in insert_call
        assert all(field in insert_call for field in [
            test_node, test_node_id, "available-cordoned", "Test reason",
            "Test details", "Test", TEST_ENDPOINT
        ])

    def test_update_node_action_invalid_action(self, client):
        """Test update_node_action method with invalid action"""
        with pytest.raises(RuntimeError) as exc_info:
            client.update_node_action(node="test-node",
                                      action="InvalidAction",
                                      timestamp=datetime.utcnow().isoformat(),
                                      reason="test",
                                      detail="test",
                                      category="test")
        assert "Invalid action" in str(exc_info.value)

    def test_get_latest_node_action(self, client, mock_kusto_client):
        """Test get_latest_node_action method"""
        test_node = "test-node-1"
        timestamp = datetime.utcnow()

        # Setup mock return value
        mock_result = [{
            "Timestamp": timestamp.isoformat(),
            "HostName": test_node,
            "NodeId": "node-123",
            "Action": "available-cordoned",
            "Reason": "Test reason",
            "Detail": "Test details",
            "Category": "Test",
            "Endpoint": TEST_ENDPOINT
        }]
        mock_kusto_client.execute_command.return_value = mock_result

        # Call method under test
        action = client.get_latest_node_action(test_node)

        # Verify result
        assert isinstance(action, NodeAction)
        assert action.HostName == test_node
        assert action.Action == "available-cordoned"
        assert action.Endpoint == TEST_ENDPOINT

    def test_get_latest_node_action_no_actions(self, client,
                                               mock_kusto_client):
        """Test get_latest_node_action method when no actions exist"""
        mock_kusto_client.execute_query.return_value = []

        action = client.get_latest_node_action("test-node")
        assert action is None

    def test_get_node_actions(self, client, mock_kusto_client):
        """Test get_node_actions method with time range"""
        test_node = "test-node-1"
        start_time = datetime.utcnow() - timedelta(hours=1)
        end_time = datetime.utcnow()

        # Setup mock return value
        mock_actions = [{
            "Timestamp": start_time.isoformat(),
            "HostName": test_node,
            "NodeId": "node-123",
            "Action": "available-cordoned",
            "Reason": "Test reason 1",
            "Detail": "Test detail 1",
            "Category": "Test",
            "Endpoint": TEST_ENDPOINT
        }, {
            "Timestamp": end_time.isoformat(),
            "HostName": test_node,
            "NodeId": "node-123",
            "Action": "cordoned-triaged_hardware",
            "Reason": "Test reason 2",
            "Detail": "Test detail 2",
            "Category": "Test",
            "Endpoint": TEST_ENDPOINT
        }]
        mock_kusto_client.execute_command.return_value = mock_actions

        # Call method under test
        actions = client.get_node_actions(node=test_node,
                                          start_time=start_time.isoformat(),
                                          end_time=end_time.isoformat())

        # Verify results
        assert len(actions) == 2
        assert all(isinstance(action, NodeAction) for action in actions)
        assert actions[0].Action == "available-cordoned"
        assert actions[1].Action == "cordoned-triaged_hardware"

    def test_get_node_actions_empty_result(self, client, mock_kusto_client):
        """Test get_node_actions method with no results"""
        mock_kusto_client.execute_command.return_value = []

        actions = client.get_node_actions(
            node="test-node",
            start_time=datetime.utcnow().isoformat(),
            end_time=datetime.utcnow().isoformat())
        assert len(actions) == 0

    def test_get_node_actions_failure(self, client, mock_kusto_client):
        """Test get_node_actions method failure handling"""
        mock_kusto_client.execute_command.side_effect = Exception("Test error")

        with pytest.raises(RuntimeError) as exc_info:
            client.get_node_actions(node="test-node",
                                    start_time=datetime.utcnow().isoformat(),
                                    end_time=datetime.utcnow().isoformat())
        assert "Failed to get node actions" in str(exc_info.value)

    def test_validate_action_format(self, client):
        """Test action format validation"""
        # Valid action formats
        assert client.is_valid_action("available-cordoned")

        # Invalid action formats
        assert not client.is_valid_action("InvalidAction")
        assert not client.is_valid_action("Cordoned")
        assert not client.is_valid_action("available")

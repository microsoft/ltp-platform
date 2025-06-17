import pytest
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from ltp_kusto_sdk.features.node_status.client import NodeStatusClient
from ltp_kusto_sdk.features.node_status.models import NodeStatus, NodeStatusRecord
from ltp_kusto_sdk.utils.node_util import Node
from ltp_kusto_sdk.utils.kusto_client import KustoManageClient

# Test constants
TEST_CLUSTER = "https://test-cluster.kusto.windows.net"
TEST_DATABASE = "TestDB"
TEST_STATUS_TABLE = "TestNodeStatusRecord"
TEST_ATTRIBUTE_TABLE = "TestNodeStatusAttributes"
TEST_ENDPOINT = "test-wcu"


@pytest.fixture(autouse=True)
def mock_kusto_client():
    """Create a mock KustoManageClient that's automatically used"""
    with patch('ltp_kusto_sdk.base.KustoManageClient',
               spec=KustoManageClient) as mock:
        client = MagicMock(spec=KustoManageClient)
        # Setup default return values
        client.execute_command.return_value = None
        client.table_exists.return_value = True  # Prevent table creation on init
        mock.return_value = client
        yield client


@pytest.fixture
def mock_env(monkeypatch):
    """Set up test environment variables"""
    monkeypatch.setenv("CLUSTER_ID", TEST_ENDPOINT)
    monkeypatch.setenv("LTP_KUSTO_CLUSTER_URI", TEST_CLUSTER)
    monkeypatch.setenv("LTP_KUSTO_DATABASE_NAME", TEST_DATABASE)
    monkeypatch.setenv("KUSTO_NODE_STATUS_TABLE_NAME", TEST_STATUS_TABLE)
    monkeypatch.setenv("KUSTO_NODE_STATUS_ATTRIBUTE_TABLE_NAME",
                       TEST_ATTRIBUTE_TABLE)


@pytest.fixture
def mock_node():
    """Create a mock Node instance"""
    with patch('ltp_kusto_sdk.features.node_status.client.Node',
               spec=Node) as mock:
        node = MagicMock(spec=Node)
        # Setup default return values
        node.get_vm_node_id_by_hostname.return_value = "test-node-id"
        mock.return_value = node
        yield node


@pytest.fixture
def sample_node_record():
    """Create a sample NodeStatusRecord instance"""
    return NodeStatusRecord(Timestamp=datetime.utcnow(),
                            HostName="test-node-1",
                            Status=NodeStatus.AVAILABLE.value,
                            NodeId="node-123",
                            Endpoint=TEST_ENDPOINT)


@pytest.fixture
def client(mock_env, mock_kusto_client):
    """Create a NodeStatusClient instance with mocked dependencies"""
    return NodeStatusClient()


class TestNodeStatusClient:

    def test_initialization(self, client, mock_kusto_client):
        """Test NodeStatusClient initialization"""
        assert client.endpoint == TEST_ENDPOINT
        assert client.cluster == TEST_CLUSTER
        assert client.database == TEST_DATABASE
        assert client.table_name == TEST_STATUS_TABLE
        assert client.attribute_table_name == TEST_ATTRIBUTE_TABLE

    def test_create_table(self, client, mock_kusto_client):
        """Test create_table method"""
        client.create_table()
        create_call = mock_kusto_client.execute_command.call_args[0][0]
        assert TEST_STATUS_TABLE in create_call
        assert "Timestamp" in create_call

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
        assert "Status" in create_call
        assert "Group" in create_call

    def test_get_status_group(self, client, mock_kusto_client):
        """Test get_status_group method"""
        # Setup mock return value
        mock_kusto_client.execute_command.return_value = [{
            "Group": "test_group"
        }]

        # Call method under test
        result = client.get_status_group("test_status")

        # Verify query execution
        mock_kusto_client.execute_command.assert_called_once()
        query = mock_kusto_client.execute_command.call_args[0][0]
        assert TEST_ATTRIBUTE_TABLE in query
        assert "test_status" in query

        # Verify result
        assert result == "test_group"

    def test_get_node_status_existing(self, client, mock_kusto_client):
        """Test get_node_status method with existing record"""
        test_node = "test-node"
        timestamp = datetime.utcnow()

        # Setup mock return value
        mock_result = {
            "Timestamp": timestamp,
            "HostName": test_node,
            "Status": NodeStatus.AVAILABLE.value,
            "NodeId": "node-123",
            "Endpoint": TEST_ENDPOINT
        }
        mock_kusto_client.execute_command.return_value = [mock_result]

        # Call method under test
        result = client.get_node_status(test_node, timestamp.timestamp())

        # Verify query execution
        mock_kusto_client.execute_command.assert_called_once()
        query = mock_kusto_client.execute_command.call_args[0][0]
        assert TEST_STATUS_TABLE in query
        assert test_node in query

        # Verify result
        assert isinstance(result, NodeStatusRecord)
        assert result.Status == NodeStatus.AVAILABLE.value
        assert result.HostName == test_node
        assert result.Endpoint == TEST_ENDPOINT

    def test_get_node_status_new(self, client, mock_kusto_client, mock_node):
        """Test get_node_status method for new node"""
        test_node = "test-node"
        test_node_id = "node-123"
        timestamp = datetime.utcnow()

        mock_node.get_vm_node_id_by_hostname.return_value = test_node_id
        mock_kusto_client.execute_command.return_value = [{
            "Timestamp":
            timestamp,
            "HostName":
            test_node,
            "Status":
            NodeStatus.NEW.value,
            "NodeId":
            test_node_id,
            "Endpoint":
            TEST_ENDPOINT
        }]
        # Call method under test
        result = client.get_node_status(test_node, timestamp.timestamp())

        # Verify result
        assert isinstance(result, NodeStatusRecord)
        assert result.NodeId == test_node_id
        assert result.Status == NodeStatus.NEW.value
        assert result.HostName == test_node
        assert result.Endpoint == TEST_ENDPOINT

    def test_update_node_status(self, client, mock_kusto_client, mock_node,
                                sample_node_record):
        """Test update_node_status method"""
        test_node = "test-node"
        test_node_id = "node-123"
        timestamp = datetime.utcnow()

        # Setup mock return values
        mock_node.get_vm_node_id_by_hostname.return_value = test_node_id
        mock_kusto_client.execute_command.return_value = None
        # Call method under test
        result = client.update_node_status(test_node,
                                           NodeStatus.CORDONED.value,
                                           timestamp.timestamp())

        # Verify result
        assert result == NodeStatus.CORDONED.value

    def test_update_node_status_invalid_transition(self, client,
                                                   mock_kusto_client,
                                                   mock_node):
        """Test update_node_status method with invalid transition"""
        test_node = "test-node"
        test_node_id = "node-123"
        timestamp = datetime.utcnow()

        # Setup mock return values
        mock_node.get_vm_node_id_by_hostname.return_value = test_node_id
        mock_kusto_client.execute_command.return_value = [{
            "Timestamp":
            timestamp,
            "HostName":
            test_node,
            "Status":
            NodeStatus.DEALLOCATED_UA.value,
            "NodeId":
            test_node_id,
            "Endpoint":
            TEST_ENDPOINT
        }]

        # Attempt invalid transition
        with pytest.raises(ValueError) as exc_info:
            client.update_node_status(test_node, NodeStatus.TRIAGED_HARDWARE.value,
                                      timestamp.timestamp())

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import sys
from unittest.mock import patch
import pytest
from datetime import datetime, timedelta, timezone
from typing import Generator

# Set up Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from node_updater import NodeRecordUpdater
from ltp_storage.data_schema.node_status import NodeStatus, NodeStatusRecord


@pytest.fixture(scope="session")
def mock_env_vars():
    """Mock environment variables used in the tests"""
    env_vars = {
        'CLUSTER_ID': 'test-cluster',
        'LTP_KUSTO_CLUSTER_URI': 'https://luciatrainingplatform.westcentralus.kusto.windows.net',
        'LTP_KUSTO_DATABASE_NAME': 'Test',
        'KUSTO_NODE_STATUS_TABLE_NAME': 'TestNodeStatusRecord',
        'KUSTO_NODE_STATUS_ATTRIBUTE_TABLE_NAME': 'TestNodeStatusAttributes',
        'KUSTO_NODE_ACTION_TABLE_NAME': 'TestNodeActionRecord',
        'KUSTO_NODE_ACTION_ATTRIBUTE_TABLE_NAME': 'TestNodeActionAttributes',
        'ENVIRONMENT': 'test'
    }
    with pytest.MonkeyPatch.context() as m:
        for key, value in env_vars.items():
            m.setenv(key, value)
        yield env_vars

@pytest.fixture(scope="session")
def updater(mock_env_vars):
    """Create a NodeRecordUpdater instance with real Kusto clients"""
    updater = NodeRecordUpdater()
    
    # Ensure test tables exist
    try:
        updater.node_status_client.create_table()
        updater.node_action_client.create_table()
    except RuntimeError:
        # Tables might already exist, which is fine
        pass
        
    yield updater
    
    # Cleanup: Drop test tables after all tests
    # try:
    #     updater.node_status_client.kusto_client.execute_command(f".drop table {updater.node_status_client.table_name} ifexists")
    #     updater.node_status_client.kusto_client.execute_command(f".drop table {updater.node_status_client.attribute_table_name} ifexists")
    #     updater.node_action_client.kusto_client.execute_command(f".drop table {updater.node_action_client.table_name} ifexists")
    #     updater.node_action_client.kusto_client.execute_command(f".drop table {updater.node_action_client.attribute_table_name} ifexists")
    # except Exception:
    #     pass

@pytest.fixture
def test_node_status(updater) -> Generator[dict, None, None]:
    """Create a test node status and clean it up after the test"""
    hostname = "test-node-integration"
    timestamp = datetime.utcnow()
    status = NodeStatus.AVAILABLE.value
    
    test_node_status = NodeStatusRecord(
        Timestamp=timestamp,
        HostName=hostname,
        Status=status,
        NodeId="test-node-id",
        Endpoint=updater.endpoint
    )
    # Create test status
  # Create test status record
    updater.node_status_client.update_node_status(
        hostname=hostname,
        to_status=status,
        timestamp=timestamp
    )
    
    yield test_node_status.to_dict()
    
    # clean up items related to the test node
    cleanup_query = f""".delete table {updater.node_status_client.table_name} records <| ({updater.node_status_client.table_name} | where HostName == "{hostname}")"""
    try:
        updater.node_status_client.execute_command(cleanup_query)
    except Exception:
        pass
    cleanup_query = f""".delete table {updater.node_action_client.table_name} records <| ({updater.node_action_client.table_name} | where HostName == "{hostname}")"""
    try:
        updater.node_action_client.execute_command(cleanup_query)
    except Exception:
        pass
            # clean up the additional node
    cleanup_query = f""".delete table {updater.node_status_client.table_name} records <| ({updater.node_status_client.table_name} | where HostName == "another-test-node")"""
    try:
        updater.node_status_client.execute_command(cleanup_query)
    except Exception:
        pass

class TestNodeRecordUpdaterIntegration:
    """Integration tests for NodeRecordUpdater using real Kusto clients"""
    
    def test_get_node_latest_status(self, updater, test_node_status):
        """Test retrieving the latest status of a node"""
        status = updater.get_node_latest_status(test_node_status['HostName'])
        
        assert status.HostName == test_node_status['HostName']
        assert status.Status == test_node_status['Status']
    
    def test_get_nodes_by_status(self, updater, test_node_status):
        """Test retrieving nodes by status"""
        # add another node with the same status and other status
        another_node = NodeStatusRecord(
            Timestamp=datetime.utcnow(),
            HostName="another-test-node",
            Status=test_node_status['Status'],
            NodeId="another-test-node-id",
            Endpoint=updater.endpoint
        )
        updater.node_status_client.update_node_status(
            hostname=another_node.HostName,
            to_status=another_node.Status,
            timestamp=another_node.Timestamp
        )
        another_node.Status = NodeStatus.CORDONED.value
        another_node.Timestamp = datetime.utcnow() + timedelta(minutes=1)
        updater.node_status_client.update_node_status(
                hostname=another_node.HostName,
                to_status=another_node.Status,
                timestamp=another_node.Timestamp
            )
        nodes = updater.get_nodes_by_status(test_node_status['Status'])
        nodes = [node['HostName'] for node in nodes]

        assert [test_node_status['HostName']] == nodes
    
    def test_update_status_action(self, updater, test_node_status):
        """Test updating node status and action"""
        new_status = NodeStatus.CORDONED.value
        timestamp = datetime.utcnow()
        reason = "Integration test"
        detail = "Testing status update"
        
        # Update status
        result = updater.update_status_action(
            node=test_node_status['HostName'],
            from_status=test_node_status['Status'],
            to_status=new_status,
            timestamp=timestamp,
            reason=reason,
            detail=detail
        )
        
        assert result is True
        
        # Verify status was updated
        updated_status = updater.get_node_latest_status(test_node_status['HostName'])
        assert updated_status.Status == new_status
        
        # Verify action was recorded
        actions = updater.node_action_client.get_node_actions(
            node=test_node_status['HostName'],
            start_time=timestamp - timedelta(minutes=1),
            end_time=timestamp + timedelta(minutes=1)
        )
        
        assert len(actions) > 0
        latest_action = actions[0]
        assert latest_action.HostName == test_node_status['HostName']
        assert latest_action.Reason == reason
        assert latest_action.Detail == detail
    
    def test_get_last_actions_update_time(self, updater, test_node_status):
        """Test retrieving the last action update time"""
        # First create an action
        timestamp = datetime.now(timezone.utc)
        updater.update_status_action(
            node=test_node_status['HostName'],
            from_status=test_node_status['Status'],
            to_status=NodeStatus.CORDONED.value,
            timestamp=timestamp,
            reason="Test last update time",
            detail="Testing"
        )
        
        # Get last update time
        last_time_dt = updater.get_last_actions_update_time()
        
        assert last_time_dt is not None
        # Allow for small time differences due to processing
        assert abs((last_time_dt - timestamp).total_seconds()) < 5
    
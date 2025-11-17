# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
from typing import Generator
import pandas as pd

# Set up Python path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from node_updater import NodeRecordUpdater
from node_alert_monitor import NodeAvailabilityMonitor
from ltp_storage.data_schema.node_status import NodeStatus, NodeStatusRecord
from ltp_storage.utils.time_util import convert_timestamp


def _is_kusto_backend(client):
    """Check if the client is a Kusto backend by checking for execute_command method"""
    return hasattr(client, 'execute_command') and callable(getattr(client, 'execute_command', None))


def _cleanup_kusto_records(client, hostname):
    """Cleanup records for Kusto backend"""
    try:
        cleanup_query = f""".delete table {client.table_name} records <| ({client.table_name} | where HostName == "{hostname}")"""
        client.execute_command(cleanup_query)
    except Exception:
        pass


def _cleanup_postgresql_records(client, hostname):
    """Cleanup records for PostgreSQL backend"""
    try:
        if not hasattr(client, 'get_session'):
            return
        
        # Try to import PostgreSQL models (may not be available if using Kusto)
        try:
            from ltp_postgresql_sdk.models import NodeStatus as StatusModel
            from ltp_postgresql_sdk.models import NodeAction as ActionModel
        except ImportError:
            # PostgreSQL SDK not available, skip cleanup
            return
        
        session = client.get_session()
        try:
            # Try to determine the model type by checking the client's module/class
            client_module = client.__class__.__module__
            client_name = client.__class__.__name__.lower()
            
            # Import the appropriate model based on client type
            if 'node_status' in client_module or 'nodestatus' in client_name:
                Model = StatusModel
            elif 'node_action' in client_module or 'nodeaction' in client_name:
                Model = ActionModel
            else:
                # Fallback: try both models
                session.query(StatusModel).filter(
                    StatusModel.hostname == hostname
                ).delete(synchronize_session=False)
                session.query(ActionModel).filter(
                    ActionModel.hostname == hostname
                ).delete(synchronize_session=False)
                session.commit()
                return
            
            session.query(Model).filter(
                Model.hostname == hostname
            ).delete(synchronize_session=False)
            session.commit()
        finally:
            session.close()
    except Exception:
        # Silently fail cleanup - test data may not exist or cleanup may not be critical
        pass


def _cleanup_records(client, hostname):
    """Cleanup records for either backend"""
    if _is_kusto_backend(client):
        _cleanup_kusto_records(client, hostname)
    else:
        _cleanup_postgresql_records(client, hostname)


@pytest.fixture(scope="session")
def updater():
    """Create a NodeRecordUpdater instance using actual pod environment variables"""
    # Ensure CLUSTER_ID is set to test-cluster for consistency
    os.environ['CLUSTER_ID'] = 'test-cluster'
    # Use actual environment variables from the pod
    # The backend will be determined by LTP_STORAGE_BACKEND_DEFAULT (defaults to 'kusto')
    updater = NodeRecordUpdater()
    
    # Ensure test tables exist (if supported by backend)
    # Tables might already exist in production, so we catch exceptions
    try:
        if hasattr(updater.node_status_client, 'create_table'):
            updater.node_status_client.create_table()
    except (RuntimeError, AttributeError):
        # Tables might already exist, which is fine
        pass
    
    try:
        if hasattr(updater.node_action_client, 'create_table'):
            updater.node_action_client.create_table()
    except (RuntimeError, AttributeError):
        # Tables might already exist, which is fine
        pass
        
    yield updater

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
    
    # Create test status record
    updater.node_status_client.update_node_status(
        hostname=hostname,
        to_status=status,
        timestamp=timestamp
    )
    
    yield test_node_status.to_dict()
    
    # Clean up items related to the test node (works for both Kusto and PostgreSQL)
    _cleanup_records(updater.node_status_client, hostname)
    _cleanup_records(updater.node_action_client, hostname)
    
    # Clean up the additional node used in test_get_nodes_by_status
    _cleanup_records(updater.node_status_client, "another-test-node")

class TestNodeRecordUpdaterIntegration:
    """Integration tests for NodeRecordUpdater using actual pod environment (supports both Kusto and PostgreSQL backends)"""
    
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
        node_hostnames = [node.HostName if hasattr(node, 'HostName') else node['HostName'] for node in nodes]

        assert test_node_status['HostName'] in node_hostnames
    
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
        start_time_str = (timestamp - timedelta(minutes=1)).isoformat()
        end_time_str = (timestamp + timedelta(minutes=1)).isoformat()
        actions = updater.node_action_client.get_node_actions(
            node=test_node_status['HostName'],
            start_time=start_time_str,
            end_time=end_time_str
        )
        
        assert len(actions) > 0
        latest_action = actions[0]
        assert latest_action.HostName == test_node_status['HostName']
        assert latest_action.Reason == reason
        assert latest_action.Detail == detail
    
    def test_get_last_actions_update_time(self, updater, test_node_status):
        """Test retrieving the last action update time"""
        # First create an action
        timestamp = datetime.utcnow()
        updater.update_status_action(
            node=test_node_status['HostName'],
            from_status=test_node_status['Status'],
            to_status=NodeStatus.CORDONED.value,
            timestamp=timestamp,
            reason="Test last update time",
            detail="Testing"
        )
        actions = updater.node_action_client.get_node_actions(
            node=test_node_status['HostName'],
            start_time=(timestamp - timedelta(minutes=1)).isoformat(),
            end_time=(timestamp + timedelta(minutes=1)).isoformat()
        )
        assert len(actions) > 0
        print(f"Actions: {actions[0].Timestamp} for node: {test_node_status['HostName']}")
        
        # Get last update time
        last_time_dt = updater.get_last_actions_update_time()
        
        assert last_time_dt is not None

class TestNodeAvailabilityMonitorEndToEnd:
    """End-to-end integration tests for NodeAvailabilityMonitor with real database updates"""
    
    @pytest.fixture
    def e2e_test_node(self, updater) -> Generator[str, None, None]:
        """Create a test node for end-to-end testing"""
        hostname = "test-node-e2e"
        timestamp = datetime.utcnow()
        status = NodeStatus.AVAILABLE.value
        
        # Create initial node status
        updater.node_status_client.update_node_status(
            hostname=hostname,
            to_status=status,
            timestamp=timestamp
        )
        
        yield hostname
        
        # Cleanup
        _cleanup_records(updater.node_status_client, hostname)
        _cleanup_records(updater.node_action_client, hostname)
    
    def test_end_to_end_node_cordoned_scenario(self, updater, e2e_test_node):
        """End-to-end test: Node becomes unschedulable (cordoned) with alerts"""
        # Setup: Create monitor with real updater
        monitor = NodeAvailabilityMonitor()
        monitor.node_updater = updater  # Use real updater
        
        # Setup test data
        test_node = e2e_test_node
        end_time = datetime.now().timestamp() + timedelta(minutes=10).total_seconds()
        time_offset_seconds = 300 
        time_offset = f"{time_offset_seconds}s"
        
        # Mock Prometheus queries
        # The flow calls:
        # 1. query_availability_changes - first query (unschedulable nodes)
        # 2. query_availability_changes - second query (schedulable nodes)
        # 3. get_node_status_changes - for each changed node
        
        change_timestamp = end_time - 120  # Change happened 2 minutes ago
        
        # First query: query_availability_changes - node changed to unschedulable
        mock_prom_response1 = {
            "result": [
                {"metric": {"node_name": test_node}, "value": [0, 0.5]}  # value < 1 means changed
            ]
        }
        # Second query: query_availability_changes - schedulable nodes
        mock_prom_response2 = None
        # Third query: get_node_status_changes - detailed changes for the node
        mock_prom_response3 = {
            "result": [{
                "values": [
                    [change_timestamp - 120, 0.0],  # Was schedulable
                    [change_timestamp, 1.0],  # Changed to unschedulable
                ]
            }]
        }
        
        # Mock alert data - query_alerts returns a list of dicts, not a DataFrame
        test_alerts_records = [{
            'alertname': 'NodeNotReady',
            'timestamp': datetime.fromtimestamp(change_timestamp, tz=timezone.utc),
            'node_name': test_node,
            'summary': 'Node is not ready',
            'severity': 'error'
        }]
        
        with patch('ltp_storage.utils.request_util.RequestUtil.prometheus_query') as mock_prom_query, \
             patch.object(monitor.alert_fetcher.client, 'query_alerts') as mock_query_alerts:
            
            # Configure mocks - prometheus_query is called multiple times
            # Side effect handles all calls in sequence
            mock_prom_query.side_effect = [
                mock_prom_response1,  # First query_availability_changes call (unschedulable)
                mock_prom_response2,  # Second query_availability_changes call (schedulable)
                mock_prom_response3,  # get_node_status_changes call for changed node
            ]
            # Mock only the database query - let get_node_alert_records, find_node_alerts, and shrink_alerts run with real logic
            mock_query_alerts.return_value = test_alerts_records
            
            # Run the monitoring flow
            monitor.monitor_status_changes(end_time, time_offset)
            
            # Verify alerts were queried from database
            assert mock_prom_query.call_count == 3
            
            # Verify node status was updated in database
            updated_status = updater.get_node_latest_status(test_node)
            assert updated_status is not None
            assert updated_status.Status == NodeStatus.CORDONED.value
            assert updated_status.HostName == test_node
            
            # Verify node action was recorded in database
            start_time_str = (datetime.fromtimestamp(change_timestamp, tz=timezone.utc) - timedelta(minutes=1)).isoformat()
            end_time_str = (datetime.fromtimestamp(change_timestamp, tz=timezone.utc) + timedelta(minutes=1)).isoformat()
            actions = updater.node_action_client.get_node_actions(
                node=test_node,
                start_time=start_time_str,
                end_time=end_time_str
            )
            
            assert len(actions) > 0
            latest_action = actions[0]
            assert latest_action.HostName == test_node
            assert latest_action.Action is not None
            assert latest_action.Reason is not None
            assert 'NodeNotReady' in latest_action.Reason
            assert 'Node is not ready' in latest_action.Detail

        
    def test_end_to_end_node_uncordoned_scenario(self, updater, e2e_test_node):
        """End-to-end test: Node becomes unschedulable (uncordoned) with alerts"""
        # Setup: Create monitor with real updater
        monitor = NodeAvailabilityMonitor()
        monitor.node_updater = updater
        monitor.tolerance_time = 60  # Set low tolerance for test
        # Setup: First cordon the node
        test_node = e2e_test_node
        cordon_time = datetime.utcnow() + timedelta(minutes=10)
        updater.update_status_action(
            node=test_node,
            from_status=NodeStatus.AVAILABLE.value,
            to_status=NodeStatus.CORDONED.value,
            timestamp=cordon_time,
            reason="Test cordon",
            detail="Test detail"
        )
        end_time = cordon_time.timestamp() + timedelta(minutes=10).total_seconds()
        time_offset_seconds = 300
        time_offset = f"{time_offset_seconds}s"
        
        # Mock Prometheus: Node is now unschedulable
        # First query: query_availability_changes - node changed to unschedulable
        mock_prom_response1 = {
            "result": [
                {"metric": {"node_name": test_node}, "value": [0, 0.5]}  # value < 1 means changed
            ]
        }
        # Second query: query_availability_changes - schedulable nodes
        mock_prom_response2 = {
            "result": []
        }
        # Third query: get_node_status_changes - detailed changes for the node
        mock_prom_response3 = {
            "result": [{
                "values": [
                    [end_time - 120, 1.0],  # Was cordoned
                    [end_time - 120, 0],  # Changed to schedulable
                ]
            }]
        }
        
        # Mock empty alerts (node recovered) - query_alerts returns a list
        test_alerts_records = []
        
        with patch('ltp_storage.utils.request_util.RequestUtil.prometheus_query') as mock_prom_query, \
             patch.object(monitor.alert_fetcher.client, 'query_alerts') as mock_query_alerts:
            
            mock_prom_query.side_effect = [
                mock_prom_response1,  # First query_availability_changes (unschedulable)
                mock_prom_response2,  # Second query_availability_changes (no changed nodes)
                mock_prom_response3,  # get_node_status_changes (schedulable)
            ]
            # Mock only the database query - let get_node_alert_records, find_node_alerts, and shrink_alerts run with real logic
            mock_query_alerts.return_value = test_alerts_records
            
            # Run monitoring
            monitor.monitor_status_changes(end_time, time_offset)
            
            assert mock_prom_query.call_count == 3
            
            # Verify node status was updated to available
            updated_status = updater.get_node_latest_status(test_node)
            assert updated_status is not None
            assert updated_status.Status == NodeStatus.AVAILABLE.value
            assert updated_status.HostName == test_node
            
            # Verify action was recorded
            # The action timestamp will be end_time (when monitoring ran)
            start_time_str = (datetime.fromtimestamp(end_time, tz=timezone.utc) - timedelta(minutes=5)).isoformat()
            end_time_str = (datetime.fromtimestamp(end_time, tz=timezone.utc) + timedelta(minutes=1)).isoformat()
            actions = updater.node_action_client.get_node_actions(
                node=test_node,
                start_time=start_time_str,
                end_time=end_time_str
            )
            
            assert len(actions) > 0
            # Find the uncordon action (cordoned-available or similar)
            uncordon_actions = [a for a in actions if 'available' in a.Action.lower() or a.Action.endswith('-available')]
            assert len(uncordon_actions) > 0

    def test_end_to_end_node_schedulable_scenario(self, updater, e2e_test_node):
        """End-to-end test: Node becomes schedulable after being cordoned"""
        # Setup: First cordon the node
        test_node = e2e_test_node
        cordon_time = datetime.utcnow() + timedelta(minutes=10)
        updater.update_status_action(
            node=test_node,
            from_status=NodeStatus.AVAILABLE.value,
            to_status=NodeStatus.CORDONED.value,
            timestamp=cordon_time,
            reason="Test cordon",
            detail="Test detail"
        )
        
        # Verify node is cordoned
        status = updater.get_node_latest_status(test_node)
        assert status.Status == NodeStatus.CORDONED.value
        
        # Setup monitor
        monitor = NodeAvailabilityMonitor()
        monitor.node_updater = updater
        monitor.tolerance_time = 60  # Set low tolerance for test
        
        end_time = cordon_time.timestamp() + timedelta(minutes=10).total_seconds()
        time_offset_seconds = 300
        time_offset = f"{time_offset_seconds}s"
        
        # Mock Prometheus: Node is now schedulable
        # When a node is schedulable but not in available, it's marked as uncordoned
        # This doesn't require get_node_status_changes - it's handled directly
        
        # First query: query_availability_changes - no changed nodes
        mock_prom_response1 = {
            "result": []  # No changed nodes
        }
        # Second query: query_availability_changes - schedulable nodes
        mock_prom_response2 = {
            "result": [
                {"metric": {"node_name": test_node}, "value": [0, 0.0]}  # Schedulable
            ]
        }
        
        # Mock empty alerts (node recovered) - query_alerts returns a list
        test_alerts_records = []
        
        with patch('ltp_storage.utils.request_util.RequestUtil.prometheus_query') as mock_prom_query, \
             patch.object(monitor.alert_fetcher.client, 'query_alerts') as mock_query_alerts:
            
            mock_prom_query.side_effect = [
                mock_prom_response1,  # First query_availability_changes (unschedulable)
                mock_prom_response2,  # Second query_availability_changes (schedulable)
                # Note: For schedulable nodes not in available, get_node_status_changes is not called
            ]
            # Mock only the database query - let get_node_alert_records, find_node_alerts, and shrink_alerts run with real logic
            mock_query_alerts.return_value = test_alerts_records
            
            # Run monitoring
            monitor.monitor_status_changes(end_time, time_offset)
            
            # Verify node status was updated to available
            updated_status = updater.get_node_latest_status(test_node)
            assert updated_status is not None
            assert updated_status.Status == NodeStatus.AVAILABLE.value
            
            # Verify action was recorded
            # The action timestamp will be end_time (when monitoring ran)
            start_time_str = (datetime.fromtimestamp(end_time, tz=timezone.utc) - timedelta(minutes=1)).isoformat()
            end_time_str = (datetime.fromtimestamp(end_time, tz=timezone.utc) + timedelta(minutes=1)).isoformat()
            actions = updater.node_action_client.get_node_actions(
                node=test_node,
                start_time=start_time_str,
                end_time=end_time_str
            )
            
            # Should have at least one action (cordoned -> available)
            assert len(actions) > 0
            # Find the uncordon action (cordoned-available or similar)
            uncordon_actions = [a for a in actions if 'available' in a.Action.lower() or a.Action.endswith('-available')]
            assert len(uncordon_actions) > 0

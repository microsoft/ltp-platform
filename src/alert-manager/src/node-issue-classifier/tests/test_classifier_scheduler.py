# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import unittest
from unittest.mock import patch, MagicMock, call
import pytest
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Generator

# Add the parent directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from classifier_scheduler import NodeIssueClassifierScheduler
from classifier import NodeFailure, NodeFailureCategory
from ltp_storage.data_schema.node_status import NodeStatus, NodeStatusRecord
from ltp_storage.data_schema.node_action import NodeAction

@pytest.fixture
def mock_node_record_updater():
    """Mock NodeRecordUpdater for testing"""
    with patch('classifier_scheduler.NodeRecordUpdater') as mock_updater_class:
        mock_updater = MagicMock()
        mock_updater_class.return_value = mock_updater
        
        # Set up default return values for common methods
        mock_updater.get_nodes_by_status.return_value = []
        mock_updater.get_node_latest_action.return_value = None
        mock_updater.get_node_latest_status.return_value = None
        mock_updater.update_status_action.return_value = True
        
        yield mock_updater

@pytest.fixture
def mock_node_issue_classifier():
    """Mock NodeIssueClassifier for testing"""
    with patch('classifier_scheduler.NodeIssueClassifier') as mock_classifier_class:
        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier
        
        # Set up default return values
        mock_classifier.classify_node_issue.return_value = (
            NodeFailure.UnknownIssue,
            NodeFailureCategory.unknown,
            'TRIAGED_UNKNOWN',
            '{"NodeId": "test-node-id"}'
        )
        
        yield mock_classifier

@pytest.mark.usefixtures("mock_node_record_updater", "mock_node_issue_classifier")
class TestNodeIssueClassifierScheduler(unittest.TestCase):
    
    @patch('classifier_scheduler.NodeRecordUpdater')
    @patch('classifier_scheduler.NodeIssueClassifier')
    def setUp(self, mock_classifier_class, mock_updater_class):
        """Set up test fixtures"""
        # Create mocks
        self.mock_updater = MagicMock()
        self.mock_classifier = MagicMock()
        
        mock_updater_class.return_value = self.mock_updater
        mock_classifier_class.return_value = self.mock_classifier
        
        # Create scheduler with mocked dependencies
        self.scheduler = NodeIssueClassifierScheduler(run_interval_minutes=10)
        self.scheduler.node_record_updater = self.mock_updater
        self.scheduler.classifier = self.mock_classifier

    def test_init(self):
        """Test scheduler initialization"""
        self.assertEqual(self.scheduler.run_interval_minutes, 10)
        self.assertFalse(self.scheduler.is_running)
        self.assertIsNotNone(self.scheduler.classifier)
        self.assertIsNotNone(self.scheduler.node_record_updater)

    def test_init_custom_interval(self):
        """Test scheduler initialization with custom interval"""
        scheduler = NodeIssueClassifierScheduler(run_interval_minutes=5)
        self.assertEqual(scheduler.run_interval_minutes, 5)

    @patch('classifier_scheduler.NodeRecordUpdater')
    @patch('classifier_scheduler.NodeIssueClassifier')
    def test_update_node_after_classification_success(self, mock_classifier_class, mock_updater_class):
        """Test successful node update after classification"""
        # Setup mocks
        mock_updater = MagicMock()
        mock_updater_class.return_value = mock_updater
        mock_updater.update_status_action.return_value = True
        
        # Create scheduler with mocked dependencies
        scheduler = NodeIssueClassifierScheduler()
        scheduler.node_record_updater = mock_updater
        
        # Test data
        node_name = 'test-node'
        node_status = NodeStatusRecord(
            Timestamp=datetime.now(timezone.utc),
            HostName='test-node',
            Status=NodeStatus.CORDONED.value,
            NodeId='test-node-id',
            Endpoint='test-endpoint'
        )
        issue = NodeFailure.NodeCrash
        category = NodeFailureCategory.hardware
        to_status = NodeStatus.TRIAGED_HARDWARE.value
        detail = '{"NodeId": "test-node-id", "FaultCode": "AmdGPUNodeCrash"}'
        
        # Call method
        result = scheduler.update_node_after_classification(
            node_name, node_status, issue, category, to_status, detail
        )
        
        # Verify success
        self.assertTrue(result)
        
        # Verify update_status_action was called with correct parameters
        mock_updater.update_status_action.assert_called_once()
        call_args = mock_updater.update_status_action.call_args
        self.assertEqual(call_args[1]['node'], node_name)
        self.assertEqual(call_args[1]['from_status'], NodeStatus.CORDONED.value)
        self.assertEqual(call_args[1]['to_status'], to_status)
        self.assertEqual(call_args[1]['reason'], issue)
        self.assertEqual(call_args[1]['detail'], detail)
        self.assertEqual(call_args[1]['category'], category)



    @patch('classifier_scheduler.NodeRecordUpdater')
    @patch('classifier_scheduler.NodeIssueClassifier')
    def test_monitor_and_classify_cordoned_nodes_success(self, mock_classifier_class, mock_updater_class):
        """Test successful monitoring and classification of cordoned nodes"""
        # Setup mocks
        mock_updater = MagicMock()
        mock_updater_class.return_value = mock_updater
        
        mock_classifier = MagicMock()
        mock_classifier_class.return_value = mock_classifier
        
        # Mock cordoned nodes
        cordoned_nodes = [
            NodeStatusRecord(
                Timestamp=datetime.now(timezone.utc),
                HostName='test-node-1',
                Status=NodeStatus.CORDONED.value,
                NodeId='node-id-1',
                Endpoint='test-endpoint'
            ),
            NodeStatusRecord(
                Timestamp=datetime.now(timezone.utc),
                HostName='test-node-2',
                Status=NodeStatus.CORDONED.value,
                NodeId='node-id-2',
                Endpoint='test-endpoint'
            )
        ]
        mock_updater.get_nodes_by_status.return_value = cordoned_nodes
        mock_updater.update_status_action.return_value = True
        
        # Mock node actions - first call returns action for node-1, second for node-2
        def get_action_side_effect(node_name):
            if node_name == 'test-node-1':
                return NodeAction(
                    HostName='test-node-1',
                    Action='available-cordoned',
                    Timestamp=datetime.now(timezone.utc),
                    Detail=json.dumps([{"alertname": "NodeNotReady", "summary": "Node not ready"}]),
                    NodeId='node-id-1',
                    Reason='Node cordoned for classification',
                    Category=NodeFailureCategory.hardware,
                    Endpoint='test-endpoint'
                )
            elif node_name == 'test-node-2':
                return NodeAction(
                    HostName='test-node-2',
                    Action='available-cordoned',
                    Timestamp=datetime.now(timezone.utc),
                    Detail=json.dumps([{"alertname": "NodeNotReady", "summary": "Node not ready"}]),
                    NodeId='node-id-2',
                    Reason='Node cordoned for classification',
                    Category=NodeFailureCategory.hardware,
                    Endpoint='test-endpoint'
                )
            return None
        
        mock_updater.get_node_latest_action.side_effect = get_action_side_effect      
        
        # Create scheduler with mocked dependencies
        scheduler = NodeIssueClassifierScheduler()
        scheduler.node_record_updater = mock_updater
        scheduler.classifier = mock_classifier
        
        # Mock classify_node_issue method
        def mock_classify_node_issue(node_name, node_status, node_action):
            """Mock classification method"""
            return (
                NodeFailure.NodeCrash,
                NodeFailureCategory.hardware,
                NodeStatus.TRIAGED_HARDWARE.value,
                f'{{"NodeId": "{node_status.NodeId}"}}'
            )
        mock_classifier.classify_node_issue.side_effect = mock_classify_node_issue
        
        # Call method
        results = scheduler.monitor_and_classify_cordoned_nodes()
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertTrue(results['test-node-1'])
        self.assertTrue(results['test-node-2'])
        
        # Test case where last action is not to cordoned
        mock_updater.get_nodes_by_status.return_value = []
        results = scheduler.monitor_and_classify_cordoned_nodes()
        self.assertEqual(len(results), 0)     

    @patch('classifier_scheduler.NodeRecordUpdater')
    @patch('classifier_scheduler.NodeIssueClassifier')
    def test_monitor_and_classify_cordoned_nodes_no_nodes(self, mock_classifier_class, mock_updater_class):
        """Test monitoring when no cordoned nodes exist"""
        # Setup mocks
        mock_updater = MagicMock()
        mock_updater_class.return_value = mock_updater
        mock_updater.get_nodes_by_status.return_value = []
        
        # Create scheduler with mocked dependencies
        scheduler = NodeIssueClassifierScheduler()
        scheduler.node_record_updater = mock_updater
        
        # Call method
        results = scheduler.monitor_and_classify_cordoned_nodes()
        
        # Verify results
        self.assertEqual(results, {})

    @patch.dict(os.environ, {'CLASSIFICATION_INTERVAL_MINUTES': '15'})
    def test_main_with_custom_interval(self):
        """Test main function with custom interval from environment"""
        with patch('classifier_scheduler.NodeIssueClassifierScheduler') as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler
            
            # Import and call main
            from classifier_scheduler import main
            main()
            
            # Verify scheduler was created with custom interval
            mock_scheduler_class.assert_called_once_with(run_interval_minutes=15)
            mock_scheduler.start_scheduler.assert_called_once()

    def test_main_with_default_interval(self):
        """Test main function with default interval"""
        with patch('classifier_scheduler.NodeIssueClassifierScheduler') as mock_scheduler_class:
            mock_scheduler = MagicMock()
            mock_scheduler_class.return_value = mock_scheduler
            
            # Import and call main
            from classifier_scheduler import main
            main()
            
            # Verify scheduler was created with default interval
            mock_scheduler_class.assert_called_once_with(run_interval_minutes=10)
            mock_scheduler.start_scheduler.assert_called_once()

@pytest.mark.usefixtures("mock_node_record_updater")
class TestNodeIssueClassifierSchedulerIntegration(unittest.TestCase):
    """Integration-style tests using real fixtures"""
    @patch('classifier_scheduler.NodeRecordUpdater')
    def test_classify_node_issue_integration(self, mock_updater):
        """Test classify_node_issue with real classifier"""
        # Create scheduler with real classifier
        scheduler = NodeIssueClassifierScheduler()

        # Create node action with detail
        node_action = NodeAction(
            HostName='test-node',
            NodeId='test-node-id',
            Action='available-cordoned',
            Timestamp=datetime.now(timezone.utc),
            Reason='Test',
            Detail=json.dumps([{
                "alertname": "NodeNotReady",
                "summary": "Node not ready for scheduling",
                "severity": "critical"
            }]),
            Category='',
            Endpoint='test-endpoint'
        )
        mock_updater.get_node_latest_action.return_value = node_action
        
        # Create node status record
        node_status = NodeStatusRecord(
            Timestamp=datetime.now(timezone.utc),
            HostName='test-node',
            Status=NodeStatus.CORDONED.value,
            NodeId='test-node-id',
            Endpoint='test-endpoint'
        )
        
        # Call method through scheduler (which should call classifier)
        issue, category, to_status, detail = scheduler.classifier.classify_node_issue('test-node', node_status, node_action)
        
        # Verify results
        self.assertEqual(issue, NodeFailure.NodeCrash)
        self.assertEqual(category, NodeFailureCategory.hardware)
        self.assertEqual(to_status, NodeStatus.TRIAGED_HARDWARE.value)
        
        detail_dict = json.loads(detail)
        self.assertEqual(detail_dict['NodeId'], 'test-node-id')
        self.assertEqual(detail_dict['FaultCode'], 'AmdGPUNodeCrash')


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
    from node_recorder_helper import NodeRecordUpdater
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
def test_cordoned_node(updater) -> Generator[str, None, None]:
    """Create a test cordoned node with action detail and clean it up after the test"""
    from node_recorder_helper import NodeRecordUpdater
    hostname = "test-node-classifier-e2e"
    timestamp = datetime.now(timezone.utc)
    
    # Then, create a CORDONED status with action detail
    cordon_timestamp = timestamp - timedelta(minutes=1)
    updater.update_status_action(
        node=hostname,
        from_status=NodeStatus.AVAILABLE.value,
        to_status=NodeStatus.CORDONED.value,
        timestamp=cordon_timestamp,
        reason="IBPortDown",
        detail=json.dumps([{
            "alertname": "IBPortDown",
            "summary": "IB port down",
            "severity": "critical"
        }])
    )
    
    yield hostname
    
    # Clean up items related to the test node (works for both Kusto and PostgreSQL)
    _cleanup_records(updater.node_status_client, hostname)
    _cleanup_records(updater.node_action_client, hostname)


class TestNodeIssueClassifierSchedulerEndToEnd:
    """End-to-end integration tests for NodeIssueClassifierScheduler with real database updates"""
    
    def test_classify_cordoned_node_end_to_end(self, updater, test_cordoned_node):
        """End-to-end test: Classify a cordoned node and verify status update in database"""
        from classifier_scheduler import NodeIssueClassifierScheduler
        
        # Create scheduler with real classifier and updater
        scheduler = NodeIssueClassifierScheduler()
        scheduler.node_record_updater = updater  # Use real updater
        
        # Verify initial state - node should be CORDONED
        initial_status = updater.get_node_latest_status(test_cordoned_node)
        assert initial_status is not None
        assert initial_status.Status == NodeStatus.CORDONED.value
        
        # Verify action exists with detail
        node_action = updater.get_node_latest_action(test_cordoned_node)
        assert node_action is not None
        assert node_action.Action == "available-cordoned"
        assert node_action.Detail is not None
        
        # Run classification
        results = scheduler.monitor_and_classify_cordoned_nodes()
        
        # Verify classification was successful
        assert test_cordoned_node in results
        assert results[test_cordoned_node] is True
        
        # Verify node status was updated in database
        updated_status = updater.get_node_latest_status(test_cordoned_node)
        assert updated_status is not None
        assert updated_status.Status == NodeStatus.TRIAGED_HARDWARE.value
        
        # Verify new action was created with classification details
        start_time_str = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        end_time_str = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        actions = updater.node_action_client.get_node_actions(
            node=test_cordoned_node,
            start_time=start_time_str,
            end_time=end_time_str
        )
        
        # Should have at least 2 actions: the original cordon action and the classification action
        assert len(actions) >= 2
        
        # Find the classification action (should be the latest)
        classification_action = actions[0]  # Actions are typically sorted by timestamp descending
        assert classification_action is not None
        assert classification_action.HostName == test_cordoned_node
        
        # Verify the action contains classification information
        # The action should be from CORDONED to one of the triaged statuses
        from_status, to_status = NodeAction.get_before_after_status(classification_action.Action)
        assert from_status == NodeStatus.CORDONED.value
        assert to_status == updated_status.Status
        
        # Verify detail contains classification information
        assert classification_action.Detail is not None
        detail_dict = json.loads(classification_action.Detail)
        assert 'NodeId' in detail_dict or 'FaultCode' in detail_dict


if __name__ == '__main__':
    unittest.main() 
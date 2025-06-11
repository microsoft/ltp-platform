import unittest
from unittest.mock import patch, MagicMock, call
import pytest
import json
import os
import sys
import time
from datetime import datetime

# Add the parent directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from classifier_scheduler import NodeIssueClassifierScheduler
from classifier import NodeFailure, NodeFailureCategory
from ltp_kusto_sdk.features.node_status.models import NodeStatus
from ltp_kusto_sdk.features.node_action.client import NodeAction

@pytest.fixture
def mock_node_record_updater():
    """Mock NodeRecordUpdater for testing"""
    with patch('classifier_scheduler.NodeRecordUpdater') as mock_updater_class:
        mock_updater = MagicMock()
        mock_updater_class.return_value = mock_updater
        
        # Set up default return values for common methods
        mock_updater.get_nodes_by_status.return_value = []
        mock_updater.get_node_latest_action.return_value = None
        mock_updater.get_node_latest_status.return_value = {}
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
            '{"NodeID": "test-node-id"}'
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
        node_status = {
            'HostName': 'test-node',
            'Status': 'Cordoned',
            'NodeID': 'test-node-id'
        }
        issue = NodeFailure.NodeCrash
        category = NodeFailureCategory.hardware
        to_status = NodeStatus.TRIAGED_HW.value
        detail = '{"NodeID": "test-node-id", "FaultCode": "AmdGPUNodeCrash"}'
        
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
        self.assertEqual(call_args[1]['from_status'], 'Cordoned')
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
            {'HostName': 'test-node-1', 'Status': 'Cordoned', 'NodeID': 'node-id-1'},
            {'HostName': 'test-node-2', 'Status': 'Cordoned', 'NodeID': 'node-id-2'}
        ]
        mock_updater.get_nodes_by_status.return_value = cordoned_nodes
        mock_updater.update_status_action.return_value = True
        mock_updater.get_node_latest_action.return_value = NodeAction(
            HostName='test-node-1',
            Action='avilable-cordoned',
            Timestamp=time.time(),
            Detail=json.dumps([{"NodeID": "node-id-1"}]),
            NodeId='node-id-1',
            Reason='Node cordoned for classification',
            Category=NodeFailureCategory.hardware,
            Endpoint='test-endpoint'
        )      
        
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
                NodeStatus.TRIAGED_HW.value,
                f'{{"NodeID": "{node_status["NodeID"]}"}}'
            )
        mock_classifier.classify_node_issue.side_effect = mock_classify_node_issue
        
        # Call method
        results = scheduler.monitor_and_classify_cordoned_nodes()
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertTrue(results['test-node-1'])
        self.assertTrue(results['test-node-2'])
        
        # Verify get_nodes_by_status was called
        mock_updater.get_nodes_by_status.assert_called_once_with(NodeStatus.CORDONED.value)
        
        mock_updater.get_node_latest_action.return_value = NodeAction(
            HostName='test-node-1',
            Action='avilable-validating',
            Timestamp=time.time(),
            Detail=json.dumps([{"NodeID": "node-id-1"}]),
            NodeId='node-id-1',
            Reason='Node cordoned for classification',
            Category=NodeFailureCategory.hardware,
            Endpoint='test-endpoint'
        ) 
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

        # Mock node action with detail
        node_action = {
            'Detail': json.dumps([{
                "alertname": "NodeNotReady",
                "summary": "Node not ready for scheduling",
                "severity": "critical"
            }])
        }
        mock_updater.get_node_latest_action.return_value = node_action
        
        # Test node status
        node_status = {
            'HostName': 'test-node',
            'Status': 'Cordoned',
            'NodeID': 'test-node-id'
        }
        
        # Call method through scheduler (which should call classifier)
        issue, category, to_status, detail = scheduler.classifier.classify_node_issue('test-node', node_status, node_action)
        
        # Verify results
        self.assertEqual(issue, NodeFailure.NodeCrash)
        self.assertEqual(category, NodeFailureCategory.hardware)
        self.assertEqual(to_status, NodeStatus.TRIAGED_HW.value)
        
        detail_dict = json.loads(detail)
        self.assertEqual(detail_dict['NodeID'], 'test-node-id')
        self.assertEqual(detail_dict['FaultCode'], 'AmdGPUNodeCrash')


if __name__ == '__main__':
    unittest.main() 
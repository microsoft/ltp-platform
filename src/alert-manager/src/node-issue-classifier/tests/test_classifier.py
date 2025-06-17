import unittest
from unittest.mock import patch, MagicMock
import pytest
import json
import os
import sys

# Add the parent directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from classifier import NodeIssueClassifier, NodeFailure, NodeFailureCategory
from ltp_kusto_sdk.features.node_status.models import NodeStatus


class TestNodeIssueClassifier(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.classifier = NodeIssueClassifier()

    def test_init_mappings(self):
        """Test that mappings are correctly initialized"""
        # Test hardware issue to fault code mapping
        self.assertIn(NodeFailure.NodeCrash, self.classifier.hardware_issue_to_faultcode)
        self.assertEqual(
            self.classifier.hardware_issue_to_faultcode[NodeFailure.NodeCrash],
            'AmdGPUNodeCrash'
        )
        
        # Test issue to category mapping
        self.assertIn(NodeFailure.NodeCrash, self.classifier.issue_to_category)
        self.assertEqual(
            self.classifier.issue_to_category[NodeFailure.NodeCrash],
            NodeFailureCategory.hardware
        )
        
        # Test all categories are represented
        categories = set(self.classifier.issue_to_category.values())
        expected_categories = {
            NodeFailureCategory.hardware,
            NodeFailureCategory.user,
            NodeFailureCategory.platform,
            NodeFailureCategory.unknown
        }
        self.assertTrue(expected_categories.issubset(categories))

    def test_classify_issue_from_cordon_detail_node_crash(self):
        """Test classification of NodeNotReady alert"""
        detail = json.dumps([{
            "alertname": "NodeNotReady",
            "summary": "Node not ready for scheduling",
            "severity": "critical"
        }])
        
        issue, category = self.classifier.classify_issue_from_cordon_detail(detail)
        
        self.assertEqual(issue, NodeFailure.NodeCrash)
        self.assertEqual(category, NodeFailureCategory.hardware)

    def test_classify_issue_from_cordon_detail_ib_port_down(self):
        """Test classification of IBPortDown alert"""
        detail = json.dumps([{
            "alertname": "IBPortDown",
            "summary": "InfiniBand port down",
            "severity": "warning"
        }])
        
        issue, category = self.classifier.classify_issue_from_cordon_detail(detail)
        
        self.assertEqual(issue, NodeFailure.IBPortDown)
        self.assertEqual(category, NodeFailureCategory.hardware)
        

    def test_classify_issue_from_cordon_detail_ib_link_flapping(self):
        """Test classification of IBLinkFlap alert"""
        detail = json.dumps([{
            "alertname": "IBLinkFlap",
            "summary": "IB link flapping detected",
            "severity": "warning"
        }])
        
        issue, category = self.classifier.classify_issue_from_cordon_detail(detail)
        
        self.assertEqual(issue, NodeFailure.IBLinkFlapping)
        self.assertEqual(category, NodeFailureCategory.hardware)

    def test_classify_issue_from_cordon_detail_gpu_segfault(self):
        """Test classification of DmesgGPUFault with segfault"""
        detail = json.dumps([{
            "alertname": "DmesgGPUFault",
            "summary": "GPU segfault detected",
            "severity": "critical"
        }])
        
        issue, category = self.classifier.classify_issue_from_cordon_detail(detail)
        
        self.assertEqual(issue, NodeFailure.GPUHangingwithSegfault)
        self.assertEqual(category, NodeFailureCategory.user)

    def test_classify_issue_from_cordon_detail_gpu_page_fault(self):
        """Test classification of DmesgGPUFault with page fault"""
        detail = json.dumps([{
            "alertname": "DmesgGPUFault",
            "summary": "GPU page fault detected",
            "severity": "critical"
        }])
        
        issue, category = self.classifier.classify_issue_from_cordon_detail(detail)
        
        self.assertEqual(issue, NodeFailure.MemoryAccessFault)
        self.assertEqual(category, NodeFailureCategory.user)

    def test_classify_issue_from_cordon_detail_gpu_fence_fallback(self):
        """Test classification of DmesgGPUFault with fence fallback timer"""
        detail = json.dumps([{
            "alertname": "DmesgGPUFault",
            "summary": "fence fallback timer expired",
            "severity": "critical"
        }])
        
        issue, category = self.classifier.classify_issue_from_cordon_detail(detail)
        
        self.assertEqual(issue, NodeFailure.GPUHangingwithFenceFallbackTimerExpired)
        self.assertEqual(category, NodeFailureCategory.hardware)

    def test_classify_issue_from_cordon_detail_nvidia_smi_failed(self):
        """Test classification of NvidiaSmiFailed alert"""
        detail = json.dumps([{
            "alertname": "NvidiaSmiFailed",
            "summary": "nvidia-smi command failed",
            "severity": "warning"
        }])
        
        issue, category = self.classifier.classify_issue_from_cordon_detail(detail)
        
        self.assertEqual(issue, NodeFailure.NvidiaSmiLatencyTooLarge)
        self.assertEqual(category, NodeFailureCategory.hardware)

    def test_classify_issue_from_cordon_detail_validation_ib_bandwidth(self):
        """Test classification of CordonValidationFailedNodes with IB bandwidth issue"""
        detail = json.dumps([{
            "alertname": "CordonValidationFailedNodes",
            "summary": "rccl-bw:ib validation failed",
            "severity": "warning"
        }])
        
        issue, category = self.classifier.classify_issue_from_cordon_detail(detail)
        
        self.assertEqual(issue, NodeFailure.IBBandwidthProblem)
        self.assertEqual(category, NodeFailureCategory.hardware)

    def test_classify_issue_from_cordon_detail_validation_model_benchmark(self):
        """Test classification of CordonValidationFailedNodes with model benchmark issue"""
        detail = json.dumps([{
            "alertname": "CordonValidationFailedNodes",
            "summary": "model-benchmark validation failed",
            "severity": "warning"
        }])
        
        issue, category = self.classifier.classify_issue_from_cordon_detail(detail)
        
        self.assertEqual(issue, NodeFailure.ModelPerformanceDegradation)
        self.assertEqual(category, NodeFailureCategory.hardware)

    def test_classify_issue_from_cordon_detail_validation_mem_bw(self):
        """Test classification of CordonValidationFailedNodes with memory bandwidth issue"""
        detail = json.dumps([{
            "alertname": "CordonValidationFailedNodes",
            "summary": "mem-bw validation failed",
            "severity": "warning"
        }])
        
        issue, category = self.classifier.classify_issue_from_cordon_detail(detail)
        
        self.assertEqual(issue, NodeFailure.PCIeBandwidthDegradation)
        self.assertEqual(category, NodeFailureCategory.hardware)

    def test_classify_issue_from_cordon_detail_validation_kernel_launch(self):
        """Test classification of CordonValidationFailedNodes with kernel launch issue"""
        detail = json.dumps([{
            "alertname": "CordonValidationFailedNodes",
            "summary": "kernel-launch validation failed",
            "severity": "warning"
        }])
        
        issue, category = self.classifier.classify_issue_from_cordon_detail(detail)
        
        self.assertEqual(issue, NodeFailure.GPUDriverHanging)
        self.assertEqual(category, NodeFailureCategory.hardware)

    def test_classify_issue_from_cordon_detail_admin_loss_nan(self):
        """Test classification of admin-abnormal-node with LossNaN"""
        detail = json.dumps([{
            "alertname": "admin-abnormal-node",
            "summary": "Loss detected",
            "severity": "critical"
        }])
        
        issue, category = self.classifier.classify_issue_from_cordon_detail(detail)
        
        self.assertEqual(issue, NodeFailure.LossNaN)
        self.assertEqual(category, NodeFailureCategory.hardware)

    def test_classify_issue_from_cordon_detail_admin_data_issue(self):
        """Test classification of admin-abnormal-node with Data issue"""
        detail = json.dumps([{
            "alertname": "admin-abnormal-node",
            "summary": "Data validation failed",
            "severity": "warning"
        }])
        
        issue, category = self.classifier.classify_issue_from_cordon_detail(detail)
        
        self.assertEqual(issue, NodeFailure.DatasetPreCheckFailure)
        self.assertEqual(category, NodeFailureCategory.platform)

    def test_classify_issue_from_cordon_detail_empty_detail(self):
        """Test classification with empty detail"""
        issue, category = self.classifier.classify_issue_from_cordon_detail("")
        
        self.assertEqual(issue, NodeFailure.UnknownIssue)
        self.assertEqual(category, NodeFailureCategory.unknown)

    def test_classify_issue_from_cordon_detail_invalid_json(self):
        """Test classification with invalid JSON"""
        issue, category = self.classifier.classify_issue_from_cordon_detail("invalid json")
        
        self.assertEqual(issue, NodeFailure.UnknownIssue)
        self.assertEqual(category, NodeFailureCategory.unknown)

    def test_classify_issue_from_cordon_detail_empty_list(self):
        """Test classification with empty alert list"""
        detail = json.dumps([])
        
        issue, category = self.classifier.classify_issue_from_cordon_detail(detail)
        
        self.assertEqual(issue, NodeFailure.UnknownIssue)
        self.assertEqual(category, NodeFailureCategory.unknown)

    def test_get_target_status_from_category(self):
        """Test target status mapping from categories"""
        # Test hardware category
        status = self.classifier.get_target_status_from_category(NodeFailureCategory.hardware)
        self.assertEqual(status, NodeStatus.TRIAGED_HARDWARE.value)
        
        # Test user category
        status = self.classifier.get_target_status_from_category(NodeFailureCategory.user)
        self.assertEqual(status, NodeStatus.TRIAGED_USER.value)
        
        # Test platform category
        status = self.classifier.get_target_status_from_category(NodeFailureCategory.platform)
        self.assertEqual(status, NodeStatus.TRIAGED_PLATFORM.value)
        
        # Test unknown category
        status = self.classifier.get_target_status_from_category(NodeFailureCategory.unknown)
        self.assertEqual(status, NodeStatus.TRIAGED_UNKNOWN.value)
        
        # Test invalid category
        status = self.classifier.get_target_status_from_category("invalid")
        self.assertEqual(status, NodeStatus.TRIAGED_UNKNOWN.value)

    def test_create_classified_detail_hardware_with_fault_code(self):
        """Test creating classified detail for hardware issue with fault code"""
        issue = NodeFailure.NodeCrash
        category = NodeFailureCategory.hardware
        node_id = "test-node-id-001"
        
        detail = self.classifier.create_classified_detail(issue, category, node_id)
        detail_dict = json.loads(detail)
        
        self.assertEqual(detail_dict['NodeId'], node_id)
        self.assertEqual(detail_dict['FaultCode'], 'AmdGPUNodeCrash')

    def test_create_classified_detail_user_no_fault_code(self):
        """Test creating classified detail for user issue without fault code"""
        issue = NodeFailure.GPUHangingwithSegfault
        category = NodeFailureCategory.user
        node_id = "test-node-id-002"
        
        detail = self.classifier.create_classified_detail(issue, category, node_id)
        detail_dict = json.loads(detail)
        
        self.assertEqual(detail_dict['NodeId'], node_id)

    def test_create_classified_detail_unknown_issue(self):
        """Test creating classified detail for unknown issue"""
        issue = NodeFailure.UnknownIssue
        category = NodeFailureCategory.unknown
        node_id = "test-node-id-003"
        
        detail = self.classifier.create_classified_detail(issue, category, node_id)
        detail_dict = json.loads(detail)
        
        self.assertEqual(detail_dict['NodeId'], node_id)

    def test_classify_node_issue_success(self):
        """Test successful node issue classification"""       
        # Create classifier with mocked updater
        classifier = NodeIssueClassifier()
        
        # Mock node action with detail
        node_action = {
            'nodeId': 'test-node-id',
            'Detail': json.dumps([{
                "alertname": "NodeNotReady",
                "summary": "Node not ready",
                "severity": "critical"
            }])
        }
        
        # Test node status
        node_status = {
            'HostName': 'test-node',
            'Status': 'Cordoned',
            'NodeId': 'test-node-id'
        }   
        
        # Call method
        issue, category, to_status, detail = classifier.classify_node_issue('test-node', node_status, node_action)
        
        # Verify results
        self.assertEqual(issue, NodeFailure.NodeCrash)
        self.assertEqual(category, NodeFailureCategory.hardware)
        self.assertEqual(to_status, NodeStatus.TRIAGED_HARDWARE.value)
        
        detail_dict = json.loads(detail)
        self.assertEqual(detail_dict['NodeId'], 'test-node-id')

    def test_classify_node_issue_no_action_detail(self):
        """Test node classification when no action detail is available"""
        # Create classifier with mocked updater
        classifier = NodeIssueClassifier()
        
        # Test node status
        node_status = {
            'HostName': 'test-node',
            'Status': 'Cordoned',
            'NodeId': 'test-node-id'
        }
        
        # Call method
        issue, category, to_status, detail = classifier.classify_node_issue('test-node', node_status, None)
        
        # Verify results for unknown issue
        self.assertEqual(issue, NodeFailure.UnknownIssue)
        self.assertEqual(category, NodeFailureCategory.unknown)
        self.assertEqual(to_status, NodeStatus.TRIAGED_UNKNOWN.value)

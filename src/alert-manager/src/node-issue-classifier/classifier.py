# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import os
import pandas as pd
import time
import logging
from typing import Dict, Tuple

from ltp_kusto_sdk.features.node_status.models import NodeStatus
from ltp_kusto_sdk import NodeAction


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NodeFailure:
    NodeCrash = 'NodeCrash'
    IBPortDown = 'IBPortDown'
    IBLinkFlapping = 'IBLinkFlapping'
    GPUHangingwithSegfault = 'GPUHangingwithSegfault'
    AMDGPUSMIHanging = 'AMDGPUSMIHanging'
    MemoryAccessFault = 'MemoryAccessFault'
    GPUHangingwithFenceFallbackTimerExpired = 'GPUHangingwithFenceFallbackTimerExpired'
    IBBandwidthProblem = 'IBBandwidthProblem'
    GPUDriverHanging = 'GPUDriverHanging'
    ModelPerformanceDegradation = 'ModelPerformanceDegradation'
    PCIeBandwidthDegradation = 'PCIeBandwidthDegradation'
    SuperBenchModelPerformanceDegradation = 'SuperBenchModelPerformanceDegradation'
    LossNaN = 'LossNaN'
    NvidiaSmiLatencyTooLarge = 'NvidiaSmiLatencyTooLarge'
    NvidiaSmiDoubleEccError = 'NvidiaSmiDoubleEccError'
    IBReregistration = 'IBReregistration'
    FrontendNetworkIssue = 'FrontendNetworkIssue'
    DiskError = 'DiskError'
    DatasetPreCheckFailure = 'DatasetPreCheckFailure'
    PlatformServiceIssue = 'PlatformServiceIssue'
    UnknownIssue = 'UnknownIssue'

class NodeFailureCategory:
    hardware = 'hardware'
    user = 'user'
    platform = 'platform'
    unknown = 'unknown'

class NodeIssueClassifier:
    def __init__(self):
        # Initialize issue mappings
        self._init_mappings()
        
    def _init_mappings(self):
        """Initialize issue to category and fault code mappings"""
        self.hardware_issue_to_faultcode = {
            NodeFailure.NodeCrash: 'AmdGPUNodeCrash',
            NodeFailure.IBPortDown: 'IBPortDown',
            NodeFailure.NvidiaSmiLatencyTooLarge: 'UnhealthyGPUNvidiasmi',
            NodeFailure.NvidiaSmiDoubleEccError: 'XID48DoubleBitECC',
            NodeFailure.IBLinkFlapping: 'IBPortFlapping',
            NodeFailure.GPUHangingwithSegfault: 'AmdGPUHangSegFault',
            NodeFailure.GPUDriverHanging: 'AmdGPUDriverHang',
            NodeFailure.AMDGPUSMIHanging: 'AmdGPUSMIHang',
            NodeFailure.MemoryAccessFault: 'AmdGPUHangMemoryAccess',
            NodeFailure.GPUHangingwithFenceFallbackTimerExpired: 'AmdGPUHangFenceFallbackTimer',
            NodeFailure.IBBandwidthProblem: 'SuperBenchRDMAfailure',
            NodeFailure.LossNaN: 'AmdGPULossNaN',
            NodeFailure.PCIeBandwidthDegradation: 'AmdPCIBWRegression',
            NodeFailure.ModelPerformanceDegradation: 'SuperBenchModelPerformanceDegradation',
        }
        
        self.issue_to_category = {
            NodeFailure.NvidiaSmiLatencyTooLarge: NodeFailureCategory.hardware,
            NodeFailure.NvidiaSmiDoubleEccError: NodeFailureCategory.hardware,
            NodeFailure.LossNaN: NodeFailureCategory.hardware,
            NodeFailure.IBPortDown: NodeFailureCategory.hardware,
            NodeFailure.IBLinkFlapping: NodeFailureCategory.hardware,
            NodeFailure.IBBandwidthProblem: NodeFailureCategory.hardware,
            NodeFailure.PCIeBandwidthDegradation: NodeFailureCategory.hardware,
            NodeFailure.ModelPerformanceDegradation: NodeFailureCategory.hardware,
            NodeFailure.GPUHangingwithFenceFallbackTimerExpired: NodeFailureCategory.hardware,
            NodeFailure.GPUDriverHanging: NodeFailureCategory.hardware,
            NodeFailure.AMDGPUSMIHanging: NodeFailureCategory.hardware,
            NodeFailure.FrontendNetworkIssue: NodeFailureCategory.hardware,
            NodeFailure.DiskError: NodeFailureCategory.hardware,
            NodeFailure.NodeCrash: NodeFailureCategory.hardware,
            NodeFailure.GPUHangingwithSegfault: NodeFailureCategory.hardware,
            NodeFailure.MemoryAccessFault: NodeFailureCategory.user,
            NodeFailure.PlatformServiceIssue: NodeFailureCategory.platform,
            NodeFailure.DatasetPreCheckFailure: NodeFailureCategory.platform,
            NodeFailure.IBReregistration: NodeFailureCategory.unknown,
            NodeFailure.UnknownIssue: NodeFailureCategory.unknown,
        }

    def classify_issue_from_cordon_detail(self, detail: str) -> Tuple[str, str]:
        """Classify issue based on action detail"""
        try:
            if not detail:
                return NodeFailure.UnknownIssue, NodeFailureCategory.unknown
                
            detail_records = json.loads(detail)
            if not isinstance(detail_records, list) or not detail_records:
                return NodeFailure.UnknownIssue, NodeFailureCategory.unknown
            
            issue = ''   
            # Process each alert record in the detail
            # traverse through the issues and find the first matching issue
            # if no any issue found, return UnknownIssue and unknown category
            for record in detail_records:
                alertname = record.get('alertname', '')
                summary = record.get('summary', '').lower()
                
                # Check for specific alert patterns
                if 'IBLinkFlap' in alertname:
                    issue = NodeFailure.IBLinkFlapping
                    break
                elif 'DmesgGPUFault' in alertname:
                    if 'segfault' in summary or 'gpu reset' in summary:
                        issue = NodeFailure.GPUHangingwithSegfault
                    elif 'page fault' in summary:
                        issue = NodeFailure.MemoryAccessFault
                    elif 'fence fallback timer' in summary:
                        issue = NodeFailure.GPUHangingwithFenceFallbackTimerExpired
                    else:
                        issue = NodeFailure.UnknownIssue
                    break
                elif 'ROCmSmiFailed' in alertname:
                    issue = NodeFailure.AMDGPUSMIHanging
                    break
                elif 'NvidiaSmiFailed' in alertname:
                    issue = NodeFailure.NvidiaSmiLatencyTooLarge
                elif 'NodeNotReady' in alertname:
                    issue = NodeFailure.NodeCrash
                    break
                elif 'PAISPaiServicePodNotReady' in alertname:
                    issue = NodeFailure.PlatformServiceIssue
                    break
                elif 'CordonValidationFailedNodes' in alertname:
                    if 'rccl-bw:ib' in summary or 'nccl-bw:ib' in summary:
                        issue = NodeFailure.IBBandwidthProblem
                    elif 'model-benchmark' in summary or 'megatron' in summary:
                        issue = NodeFailure.ModelPerformanceDegradation
                    elif 'mem-bw' in summary:
                        issue = NodeFailure.PCIeBandwidthDegradation
                    elif 'kernel-launch' in summary:
                        issue = NodeFailure.GPUDriverHanging
                elif 'admin-abnormal-node' in alertname:
                    if 'loss' in summary.lower() or 'nan' in summary.lower():
                        issue = NodeFailure.LossNaN
                    elif 'data' in summary.lower():
                        issue = NodeFailure.DatasetPreCheckFailure
                    # check if summary is in any of the NodeFailure enum str, such as NodeFailure.IBReregistration, etc.
                    elif summary in NodeFailure.__dict__.values():
                        issue = summary
                else:
                    # check if alertname is in any of the NodeFailure enum str
                    # such as NodeFailure.IBPortDown, etc.
                    if alertname in NodeFailure.__dict__.values():
                        issue = alertname
                        break

            
            # Get category for the issue
            category = self.issue_to_category.get(issue, NodeFailureCategory.unknown)
            return issue, category
            
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.warning(f"Error parsing detail: {e}")
            return NodeFailure.UnknownIssue, NodeFailureCategory.unknown

    def get_target_status_from_category(self, category: str) -> str:
        """Get target node status based on issue category"""
        category_to_status = {
            NodeFailureCategory.hardware: NodeStatus.TRIAGED_HARDWARE.value,
            NodeFailureCategory.user: NodeStatus.TRIAGED_USER.value,
            NodeFailureCategory.platform: NodeStatus.TRIAGED_PLATFORM.value,
            NodeFailureCategory.unknown: NodeStatus.TRIAGED_UNKNOWN.value,
        }
        return category_to_status.get(category, NodeStatus.TRIAGED_UNKNOWN.value)

    def create_classified_detail(self, issue: str, category: str, cordoned_node_id: str) -> str:
        """Create detailed information for the classified issue"""
        detail_info = {
            'NodeId': cordoned_node_id,
            'FaultCode': '',
        }
        # Add fault code for hardware issues
        if category == NodeFailureCategory.hardware and issue in self.hardware_issue_to_faultcode:
            detail_info['FaultCode'] = self.hardware_issue_to_faultcode[issue]
            
        return json.dumps(detail_info) if detail_info else ''

    def classify_node_issue(self, node_name: str, node_status: Dict, node_action: Dict) -> Tuple[str, str, str, str]:
        """
        Classify issues for a single node
        
        Args:
            node_name: Name of the node to classify
            node_status: Current status information of the node
            
        Returns:
            Tuple containing (issue, category, to_status, detail)
        """
        try:
            cordoned_node_id = node_status['NodeId']
            
            if not isinstance(node_action, dict):
                node_action = node_action.to_dict()
            
            if not node_action or not node_action.get('Detail'):
                logger.warning(f"No action detail found for node {node_name}")
                issue = NodeFailure.UnknownIssue
                category = NodeFailureCategory.unknown
            else:
                # Classify the issue based on action detail
                issue, category = self.classify_issue_from_cordon_detail(node_action['Detail'])
                logger.info(f"Classified node {node_name}: issue={issue}, category={category}")
            
            # Get target status based on category
            to_status = self.get_target_status_from_category(category)
            
            # Create detailed information
            detail = self.create_classified_detail(issue, category, cordoned_node_id)
            
            return issue, category, to_status, detail
            
        except Exception as e:
            logger.error(f"Error classifying node {node_name}: {str(e)}")
            # Return default values in case of error
            return NodeFailure.UnknownIssue, NodeFailureCategory.unknown, NodeStatus.TRIAGED_UNKNOWN.value, ""

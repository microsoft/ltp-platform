# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from ltp_kusto_sdk.features.node_action.models import NodeAction

TEST_ENDPOINT = "test-wcu"


@pytest.fixture
def sample_node_action():
    """Create a sample NodeAction instance"""
    return NodeAction(Timestamp=datetime.utcnow(),
                      HostName="test-node-1",
                      NodeId="node-123",
                      Action="available-cordoned",
                      Reason="Test reason",
                      Detail="Test details",
                      Category="Test",
                      Endpoint=TEST_ENDPOINT)


class TestNodeAction:

    def test_from_record(self, sample_node_action):
        """Test NodeAction.from_record method"""
        record = {
            "Timestamp": sample_node_action.Timestamp,
            "HostName": sample_node_action.HostName,
            "NodeId": sample_node_action.NodeId,
            "Action": sample_node_action.Action,
            "Reason": sample_node_action.Reason,
            "Detail": sample_node_action.Detail,
            "Category": sample_node_action.Category,
            "Endpoint": sample_node_action.Endpoint
        }

        action = NodeAction.from_record(record)
        assert isinstance(action, NodeAction)
        assert isinstance(action.Timestamp, datetime)
        assert action.HostName == sample_node_action.HostName
        assert action.Action == sample_node_action.Action
        assert action.Endpoint == sample_node_action.Endpoint

    def test_from_record_string_timestamp(self):
        """Test NodeAction.from_record method with string timestamp"""
        timestamp_str = "2023-06-01T12:00:00Z"
        record = {
            "Timestamp": timestamp_str,
            "HostName": "test-node-1",
            "NodeId": "node-123",
            "Action": "available-cordoned",
            "Reason": "Test reason",
            "Detail": "Test details",
            "Category": "Test",
            "Endpoint": TEST_ENDPOINT
        }

        action = NodeAction.from_record(record)
        assert isinstance(action, NodeAction)
        assert isinstance(action.Timestamp, datetime)
        assert action.HostName == "test-node-1"

    def test_from_record_missing_field(self):
        """Test NodeAction.from_record method with missing field"""
        record = {
            "Timestamp": datetime.utcnow().isoformat(),
            "HostName": "test-node"
            # Missing other required fields
        }

        with pytest.raises(KeyError):
            NodeAction.from_record(record)

    def test_to_dict(self, sample_node_action):
        """Test to_dict method"""
        action_dict = sample_node_action.to_dict()
        # Timestamp should be converted to string in dict format
        assert isinstance(action_dict["Timestamp"], str)
        assert action_dict["HostName"] == sample_node_action.HostName
        assert action_dict["NodeId"] == sample_node_action.NodeId
        assert action_dict["Action"] == sample_node_action.Action
        assert action_dict["Reason"] == sample_node_action.Reason
        assert action_dict["Detail"] == sample_node_action.Detail
        assert action_dict["Category"] == sample_node_action.Category
        assert action_dict["Endpoint"] == sample_node_action.Endpoint

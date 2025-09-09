# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from ltp_kusto_sdk.features.node_status.models import (NodeStatus, StatusGroup,
                                                       StatusMetadata,
                                                       NodeStatusRecord)


@pytest.fixture
def sample_node_record():
    return NodeStatusRecord(Timestamp=datetime.utcnow(),
                            HostName="test-node-1",
                            Status=NodeStatus.AVAILABLE.value,
                            NodeId="node-123",
                            Endpoint="wcu")


class TestNodeStatusRecord:

    def test_from_record(self):
        record_dict = {
            'Timestamp': 1234567890,
            'HostName': 'test-node',
            'Status': NodeStatus.NEW.value,
            'NodeId': 'node-123',
            'Endpoint': 'wcu'
        }
        record = NodeStatusRecord.from_record(record_dict)
        assert record.HostName == 'test-node'
        assert record.Status == NodeStatus.NEW.value
        assert record.NodeId == 'node-123'
        assert record.Endpoint == 'wcu'

    def test_update_valid_transition(self, sample_node_record):
        with patch.object(NodeStatus, 'can_transition', return_value=True):
            sample_node_record.update(NodeStatus.CORDONED.value)
            assert sample_node_record.Status == NodeStatus.CORDONED.value

    def test_update_invalid_transition(self, sample_node_record):
        with patch.object(NodeStatus, 'can_transition', return_value=False):
            with pytest.raises(ValueError) as exc_info:
                sample_node_record.update(NodeStatus.TRIAGED_HARDWARE.value)
            assert "Invalid transition" in str(exc_info.value)


class TestNodeStatus:

    def test_get_metadata(self):
        metadata = NodeStatus.get_metadata(NodeStatus.NEW.value)
        assert isinstance(metadata, StatusMetadata)
        assert metadata.group == StatusGroup.NEW

    def test_can_transition(self):
        # Test valid transition
        assert NodeStatus.can_transition(NodeStatus.AVAILABLE.value,
                                         NodeStatus.CORDONED.value)

    def test_get_group(self):
        group = NodeStatus.get_group(NodeStatus.TRIAGED_HARDWARE.value)
        assert group == StatusGroup.TRIAGED

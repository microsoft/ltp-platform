# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""Tests for NodeRecycler - focused on validation skip, retry logic, and bug fixes."""

import os
import sys
import time
import types
import pytest
from unittest.mock import MagicMock, patch, mock_open

# Add parent directory to path so we can import recycler
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock external modules that are not available in test environment
for mod_name in ["icm", "azure", "azure.identity", "azure.mgmt",
                 "azure.mgmt.compute", "ltp_storage", "ltp_storage.factory",
                 "ltp_storage.data_schema", "ltp_storage.data_schema.node_status"]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

# Set up the NodeStatus mock before importing recycler
mock_node_status = MagicMock()
mock_node_status.ALLOCATED_UA.value = "allocated_ua"
mock_node_status.ALLOCATED_PLATFORM.value = "allocated_platform"
mock_node_status.DEALLOCATED_UA.value = "deallocated_ua"
mock_node_status.DEALLOCATED_PLATFORM.value = "deallocated_platform"
mock_node_status.DEALLOCATED_CAPACITY.value = "deallocated_capacity"
mock_node_status.VALIDATING.value = "validating"
mock_node_status.AVAILABLE.value = "available"
mock_node_status.AVAILABLE_NODATA.value = "available_nodata"
mock_node_status.CORDONED.value = "cordoned"
mock_node_status.UA.value = "ua"
mock_node_status.TRIAGED_HARDWARE.value = "triaged_hardware"
mock_node_status.TRIAGED_USER.value = "triaged_user"
mock_node_status.TRIAGED_PLATFORM.value = "triaged_platform"
mock_node_status.NEW.value = "new"
sys.modules["ltp_storage.data_schema.node_status"].NodeStatus = mock_node_status
sys.modules["ltp_storage.factory"].create_node_status_client = MagicMock()
sys.modules["ltp_storage.factory"].create_node_action_client = MagicMock()
sys.modules["azure.identity"].DefaultAzureCredential = MagicMock()
sys.modules["azure.mgmt.compute"].ComputeManagementClient = MagicMock()
sys.modules["icm"].ICMApi = MagicMock()

import recycler as recycler_module


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Set up environment variables before NodeRecycler class is loaded."""
    monkeypatch.setenv("REST_SERVER_URI", "http://test-server")
    monkeypatch.setenv("REST_SERVER_TOKEN", "test-token")
    monkeypatch.setenv("LTP_VALIDATION_IMAGE", "test-image:latest")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("LTP_VMSS_IDS", "vmss-gpu-1,vmss-cpu-1")
    monkeypatch.setenv("VALIDATION_SKIP_VMSS_IDS", "vmss-cpu-1")
    monkeypatch.setenv("VALIDATION_MAX_RETRIES", "3")
    monkeypatch.setenv("CLUSTER_ID", "test-endpoint")


@pytest.fixture
def status_client():
    return MagicMock()


@pytest.fixture
def action_client():
    return MagicMock()


@pytest.fixture
def recycler(mock_env):
    """Configure NodeRecycler for testing."""
    cls = recycler_module.NodeRecycler
    default_nodes = {"node-a", "node-b", "test-node", "gpu-node-1", "cpu-node-1"}
    cls._ltp_rest_server_uri = "http://test-server"
    cls._ltp_rest_server_token = "test-token"
    cls._ltp_validation_image = "test-image:latest"
    cls._azure_client_id = "test-client-id"
    cls._ltp_vmss_ids = "vmss-gpu-1,vmss-cpu-1"
    cls._validation_skip_vmss_ids = {"vmss-cpu-1"}
    cls._cluster_id = "test-endpoint"
    cls._validation_max_retries = 3
    cls._validation_retries = {}
    cls._live_nodes_retry_attempts = 3
    cls._live_nodes_retry_interval_seconds = 0
    cls._layout_nodes_cache = set(default_nodes)
    cls._layout_nodes_loaded = True
    cls._layout_nodes_load_success = True
    cls._load_live_nodes = classmethod(lambda _cls: (set(default_nodes), set(default_nodes), True))
    return cls


# ============================================================
# Tests for _validation_skip_vmss_ids parsing
# ============================================================

class TestValidationSkipVmssIdsParsing:
    def test_empty_string(self):
        result = set(filter(None, "".split(",")))
        assert result == set()

    def test_single_vmss_id(self):
        result = set(filter(None, "vmss-cpu-1".split(",")))
        assert result == {"vmss-cpu-1"}

    def test_multiple_vmss_ids(self):
        result = set(filter(None, "vmss-cpu-1,vmss-cpu-2".split(",")))
        assert result == {"vmss-cpu-1", "vmss-cpu-2"}

    def test_trailing_comma(self):
        result = set(filter(None, "vmss-cpu-1,".split(",")))
        assert result == {"vmss-cpu-1"}


# ============================================================
# Tests for skip_validation()
# ============================================================

class TestSkipValidation:
    def test_marks_nodes_as_available(self, recycler, status_client, action_client):
        recycler.skip_validation(
            ["node-a", "node-b"], "allocated_ua",
            status_client=status_client, action_client=action_client,
        )

        assert status_client.update_node_status.call_count == 2
        status_client.update_node_status.assert_any_call("node-a", "available", pytest.approx(time.time(), abs=5))
        status_client.update_node_status.assert_any_call("node-b", "available", pytest.approx(time.time(), abs=5))

    def test_records_action(self, recycler, status_client, action_client):
        recycler.skip_validation(
            ["node-a"], "allocated_ua",
            status_client=status_client, action_client=action_client,
        )

        action_client.update_node_action.assert_called_once_with(
            "node-a", "allocated_ua-available",
            pytest.approx(time.time(), abs=5),
            "Skipping GPU validation per VMSS config", "", "",
        )

    def test_log_contains_uncordon_hint(self, recycler, status_client, action_client, caplog):
        import logging
        with caplog.at_level(logging.INFO):
            recycler.skip_validation(
                ["node-a"], "allocated_ua",
                status_client=status_client, action_client=action_client,
            )

        assert "kubectl uncordon node-a" in caplog.text

    def test_no_clients(self, recycler):
        # Should not raise even without clients
        recycler.skip_validation(["node-a"], "allocated_ua")

    def test_empty_hostnames(self, recycler, status_client, action_client):
        recycler.skip_validation(
            [], "allocated_ua",
            status_client=status_client, action_client=action_client,
        )
        status_client.update_node_status.assert_not_called()
        action_client.update_node_action.assert_not_called()


# ============================================================
# Tests for validate() - normal flow and bug fix
# ============================================================

class TestValidate:
    @patch("builtins.open", mock_open(read_data="template {uid} {image} {client_id} {instances} {hostnames}"))
    @patch.object(recycler_module.requests, "post")
    def test_updates_status_per_node_individually(self, mock_post, recycler, status_client, action_client):
        """Verify the inner-loop bug fix: each node's status is updated individually."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        recycler.validate(
            hostnames=["node-a", "node-b"],
            status_client=status_client,
            action_client=action_client,
        )

        assert status_client.update_node_status.call_count == 2
        status_client.update_node_status.assert_any_call("node-a", "validating", pytest.approx(time.time(), abs=5))
        status_client.update_node_status.assert_any_call("node-b", "validating", pytest.approx(time.time(), abs=5))

    @patch("builtins.open", mock_open(read_data="template {uid} {image} {client_id} {instances} {hostnames}"))
    @patch.object(recycler_module.requests, "post")
    def test_submits_job_for_each_node(self, mock_post, recycler, status_client, action_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        recycler.validate(
            hostnames=["node-a", "node-b"],
            status_client=status_client,
            action_client=action_client,
        )

        assert mock_post.call_count == 2

    @patch("builtins.open", mock_open(read_data="template {uid} {image} {client_id} {instances} {hostnames}"))
    @patch.object(recycler_module.requests, "post")
    def test_clears_retry_count_on_success(self, mock_post, recycler, status_client, action_client):
        recycler._validation_retries["node-a"] = 2
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        recycler.validate(
            hostnames=["node-a"],
            status_client=status_client,
            action_client=action_client,
        )

        assert "node-a" not in recycler._validation_retries

    def test_skips_empty_hostname(self, recycler, status_client, action_client):
        with patch("builtins.open", mock_open(read_data="template {uid} {image} {client_id} {instances} {hostnames}")):
            recycler.validate(
                hostnames=["", "  "],
                status_client=status_client,
                action_client=action_client,
            )
        status_client.update_node_status.assert_not_called()

    def test_no_hostnames_returns_early(self, recycler, status_client):
        status_client.get_nodes_by_status.return_value = []
        recycler.validate(status_client=status_client)
        # Should not try to open validation.yaml


# ============================================================
# Tests for validate() - retry limit and cordon
# ============================================================

class TestValidateRetryAndCordon:
    @patch("builtins.open", mock_open(read_data="template {uid} {image} {client_id} {instances} {hostnames}"))
    @patch.object(recycler_module.requests, "post")
    def test_increments_retry_on_failure(self, mock_post, recycler, status_client, action_client):
        mock_post.side_effect = Exception("connection error")

        recycler.validate(
            hostnames=["node-a"],
            status_client=status_client,
            action_client=action_client,
        )

        assert recycler._validation_retries["node-a"] == 1

    @patch("builtins.open", mock_open(read_data="template {uid} {image} {client_id} {instances} {hostnames}"))
    @patch.object(recycler_module.requests, "post")
    def test_cordons_after_max_retries(self, mock_post, recycler, status_client, action_client):
        mock_post.side_effect = Exception("connection error")
        recycler._validation_retries["node-a"] = 2  # Already failed twice

        recycler.validate(
            hostnames=["node-a"],
            status_client=status_client,
            action_client=action_client,
        )

        status_client.update_node_status.assert_called_once_with("node-a", "cordoned", pytest.approx(time.time(), abs=5))
        action_client.update_node_action.assert_called()
        assert "node-a" not in recycler._validation_retries

    @patch("builtins.open", mock_open(read_data="template {uid} {image} {client_id} {instances} {hostnames}"))
    @patch.object(recycler_module.requests, "post")
    def test_does_not_cordon_before_max_retries(self, mock_post, recycler, status_client, action_client):
        mock_post.side_effect = Exception("connection error")
        recycler._validation_retries["node-a"] = 0  # First failure

        recycler.validate(
            hostnames=["node-a"],
            status_client=status_client,
            action_client=action_client,
        )

        # Should NOT call update_node_status with cordoned
        for call in status_client.update_node_status.call_args_list:
            assert call[0][1] != "cordoned"


# ============================================================
# Tests for start_and_validate_pipeline() - VMSS skip logic
# ============================================================

class TestStartAndValidatePipeline:
    @patch.object(
        __import__("builtins"), "__import__", side_effect=ImportError
    )
    def _get_recycler_class(self, recycler):
        return recycler

    @patch("builtins.open", mock_open(read_data="template {uid} {image} {client_id} {instances} {hostnames}"))
    def test_skip_vmss_calls_skip_validation(self, recycler, status_client, action_client):
        """Nodes from skip VMSS should go to skip_validation, not validate."""
        gpu_vms = [{"computer_name": "gpu-node-1"}]
        cpu_vms = [{"computer_name": "cpu-node-1"}]

        with patch.object(recycler, "operate") as mock_operate, \
             patch.object(recycler, "validate") as mock_validate, \
             patch.object(recycler, "skip_validation") as mock_skip:

            def operate_side_effect(vmss_id, **kwargs):
                from_state = kwargs.get("from_state")
                if vmss_id == "vmss-gpu-1" and from_state == "deallocated_ua":
                    return gpu_vms
                if vmss_id == "vmss-cpu-1" and from_state == "deallocated_ua":
                    return cpu_vms
                return []

            mock_operate.side_effect = operate_side_effect

            recycler.start_and_validate_pipeline(status_client, action_client)

        # gpu-node-1 should go to validate
        mock_validate.assert_any_call(
            hostnames=["gpu-node-1"],
            status_client=status_client,
            action_client=action_client,
        )
        # cpu-node-1 should go to skip_validation
        mock_skip.assert_called_once_with(
            ["cpu-node-1"], "allocated_ua",
            status_client=status_client, action_client=action_client,
        )

    @patch("builtins.open", mock_open(read_data="template {uid} {image} {client_id} {instances} {hostnames}"))
    def test_no_skip_vmss_all_go_to_validate(self, recycler, status_client, action_client):
        """When skip list is empty, all nodes go to validate."""
        recycler._validation_skip_vmss_ids = set()
        vms = [{"computer_name": "node-1"}]

        with patch.object(recycler, "operate") as mock_operate, \
             patch.object(recycler, "validate") as mock_validate, \
             patch.object(recycler, "skip_validation") as mock_skip:

            def operate_side_effect(vmss_id, **kwargs):
                from_state = kwargs.get("from_state")
                if vmss_id == "vmss-gpu-1" and from_state == "deallocated_ua":
                    return vms
                return []

            mock_operate.side_effect = operate_side_effect
            recycler.start_and_validate_pipeline(status_client, action_client)

        mock_skip.assert_not_called()
        # validate called for node-1 + 3 fallback calls
        assert mock_validate.call_count >= 1

    @patch("builtins.open", mock_open(read_data="template {uid} {image} {client_id} {instances} {hostnames}"))
    def test_no_started_vms_skips_both(self, recycler, status_client, action_client):
        """When operate returns empty, neither validate nor skip_validation is called."""
        with patch.object(recycler, "operate") as mock_operate, \
             patch.object(recycler, "validate") as mock_validate, \
             patch.object(recycler, "skip_validation") as mock_skip:

            mock_operate.return_value = []
            recycler.start_and_validate_pipeline(status_client, action_client)

        mock_skip.assert_not_called()
        # validate is still called 3 times for the fallback calls at the end
        assert mock_validate.call_count == 3

    @patch("builtins.open", mock_open(read_data="template {uid} {image} {client_id} {instances} {hostnames}"))
    def test_skip_vmss_with_platform_state(self, recycler, status_client, action_client):
        """Skip VMSS nodes from DEALLOCATED_PLATFORM path should use allocated_platform state."""
        cpu_vms = [{"computer_name": "cpu-node-1"}]

        with patch.object(recycler, "operate") as mock_operate, \
             patch.object(recycler, "validate") as mock_validate, \
             patch.object(recycler, "skip_validation") as mock_skip:

            def operate_side_effect(vmss_id, **kwargs):
                from_state = kwargs.get("from_state")
                if vmss_id == "vmss-cpu-1" and from_state == "deallocated_platform":
                    return cpu_vms
                return []

            mock_operate.side_effect = operate_side_effect

            recycler.start_and_validate_pipeline(status_client, action_client)

        mock_skip.assert_called_once_with(
            ["cpu-node-1"], "allocated_platform",
            status_client=status_client, action_client=action_client,
        )


# ── OFR dedup tests ─────────────────────────────────────────────────────

class TestOfrDedup:
    """Test that ofr() skips nodes that already have an active OFR ticket."""

    def test_skips_node_with_existing_ofr_ticket(self, recycler, status_client, action_client):
        """If latest action is triaged_hardware-ua, node should not create a new ticket."""
        node = MagicMock()
        node.HostName = "test-node"
        node.NodeId = "test-node-id"
        status_client.get_nodes_by_status.return_value = [node]

        # Latest action is triaged_hardware-ua (OFR already submitted)
        latest_action = MagicMock()
        latest_action.Action = "triaged_hardware-ua"
        latest_action.Detail = "784487455"  # existing ticket id
        action_client.get_latest_node_action.return_value = latest_action

        with patch("recycler.icm") as mock_icm, \
             patch("recycler.time") as mock_time:
            mock_icm_api = MagicMock()
            mock_icm.ICMApi.return_value = mock_icm_api
            # Ticket already resolved so the polling loop exits immediately
            mock_icm_api.get_incident.return_value = {"Status": "Resolved"}

            recycler.ofr(status_client=status_client, action_client=action_client)

            # Should NOT create any new incident
            mock_icm_api.create_incident.assert_not_called()

    def test_creates_ticket_for_new_node(self, recycler, status_client, action_client):
        """If latest action is cordoned-triaged_hardware, a new ticket should be created."""
        node = MagicMock()
        node.HostName = "test-node"
        node.NodeId = "test-node-id"
        status_client.get_nodes_by_status.return_value = [node]

        # Latest action is NOT triaged_hardware-ua
        latest_action = MagicMock()
        latest_action.Action = "cordoned-triaged_hardware"
        latest_action.Detail = '{"NodeId": "test-node-id", "FaultCode": "AmdGPUNodeCrash"}'
        action_client.get_latest_node_action.return_value = latest_action

        # get_latest_action_by_state returns the same action
        action_by_state = MagicMock()
        action_by_state.Action = "cordoned-triaged_hardware"
        action_by_state.Detail = '{"NodeId": "test-node-id", "FaultCode": "AmdGPUNodeCrash"}'
        action_client.get_latest_action_by_state.return_value = action_by_state

        with patch("recycler.icm") as mock_icm, \
             patch("recycler.time") as mock_time:
            mock_icm_api = MagicMock()
            mock_icm.ICMApi.return_value = mock_icm_api
            mock_icm_api.create_incident.return_value = [123456]
            mock_icm_api.get_incident.return_value = {"Status": "Resolved"}

            recycler.ofr(status_client=status_client, action_client=action_client)

            # Should create exactly one incident
            mock_icm_api.create_incident.assert_called_once()


class TestNodeFilterPolicy:
    def test_layout_only_loads_once(self, recycler):
        recycler._layout_nodes_loaded = False
        recycler._layout_nodes_load_success = False
        recycler._layout_nodes_cache = set()

        with patch.object(recycler, "_load_layout_nodes", return_value=({"node-a"}, True)) as mock_load_layout:
            filtered_1, ok_1 = recycler._filter_nodes_by_policy(
                ["node-a"],
                stage="test-stage-1",
                require_layout=True,
                require_live=False,
            )
            filtered_2, ok_2 = recycler._filter_nodes_by_policy(
                ["node-a"],
                stage="test-stage-2",
                require_layout=True,
                require_live=False,
            )

        assert ok_1 is True
        assert ok_2 is True
        assert filtered_1 == ["node-a"]
        assert filtered_2 == ["node-a"]
        assert mock_load_layout.call_count == 1

    def test_layout_load_failure_raises_runtime_error(self, recycler):
        recycler._layout_nodes_loaded = False
        recycler._layout_nodes_load_success = False
        recycler._layout_nodes_cache = set()

        with patch.object(recycler, "_load_layout_nodes", return_value=(set(), False)):
            with pytest.raises(RuntimeError, match="failed to initialize layout nodes"):
                recycler._filter_nodes_by_policy(
                    ["node-a", "node-b"],
                    stage="test-layout-fail",
                    require_layout=True,
                    require_live=False,
                )

    def test_empty_layout_raises_runtime_error(self, recycler):
        recycler._layout_nodes_loaded = False
        recycler._layout_nodes_load_success = False
        recycler._layout_nodes_cache = set()

        with patch.object(recycler, "_load_layout_nodes", return_value=(set(), True)):
            with pytest.raises(RuntimeError, match="layout contains no usable nodes"):
                recycler._filter_nodes_by_policy(
                    ["node-a", "node-b"],
                    stage="test-layout-empty",
                    require_layout=True,
                    require_live=False,
                )

    def test_empty_layout_cache_after_load_raises_runtime_error(self, recycler):
        recycler._layout_nodes_loaded = True
        recycler._layout_nodes_load_success = True
        recycler._layout_nodes_cache = set()

        with pytest.raises(RuntimeError, match="layout cache is empty"):
            recycler._filter_nodes_by_policy(
                ["node-a"],
                stage="test-layout-empty-cache",
                require_layout=True,
                require_live=False,
            )

    def test_no_layout_load_when_not_required(self, recycler):
        with patch.object(recycler, "_load_layout_nodes") as mock_load_layout:
            filtered, ok = recycler._filter_nodes_by_policy(
                ["node-a"],
                stage="test-no-layout",
                require_layout=False,
                require_live=False,
            )

        assert ok is True
        assert filtered == ["node-a"]
        mock_load_layout.assert_not_called()

    def test_live_nodes_retry_success(self, recycler):
        recycler._live_nodes_retry_attempts = 3
        recycler._live_nodes_retry_interval_seconds = 0

        with patch.object(
            recycler,
            "_load_live_nodes",
            side_effect=[
                (set(), set(), False),
                (set(), set(), False),
                ({"node-a"}, {"node-a"}, True),
            ],
        ) as mock_load_live, patch("recycler.time.sleep") as mock_sleep:
            filtered, ok = recycler._filter_nodes_by_policy(
                ["node-a"],
                stage="test-live-retry-success",
                require_layout=True,
                require_live=True,
            )

        assert ok is True
        assert filtered == ["node-a"]
        assert mock_load_live.call_count == 3
        assert mock_sleep.call_count == 2

    def test_live_nodes_retry_exhausted_skip_stage(self, recycler):
        recycler._live_nodes_retry_attempts = 3
        recycler._live_nodes_retry_interval_seconds = 0

        with patch.object(
            recycler,
            "_load_live_nodes",
            return_value=(set(), set(), False),
        ) as mock_load_live, patch("recycler.time.sleep") as mock_sleep:
            filtered, ok = recycler._filter_nodes_by_policy(
                ["node-a"],
                stage="test-live-retry-fail",
                require_layout=True,
                require_live=True,
            )

        assert ok is False
        assert filtered == []
        assert mock_load_live.call_count == 3
        assert mock_sleep.call_count == 2

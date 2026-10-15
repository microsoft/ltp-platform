# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
import re
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import test_service_update_recovery as fixtures


tool, ROOT = fixtures.tool, fixtures.ROOT


class ReviewerRegressionTest(unittest.TestCase):
    setUp = fixtures.ServiceRecoveryTest.setUp
    tearDown = fixtures.ServiceRecoveryTest.tearDown
    state = fixtures.ServiceRecoveryTest.state
    make_plan = fixtures.ServiceRecoveryTest.make_plan

    def test_no_configuration_or_resource_verification_api_remains(self):
        for name in ("PUBLIC_CONFIG_FIELDS", "PUBLIC_DEPENDENCIES", "PUBLIC_CILIUM_OPTIONS",
                     "public_connection", "resource_quantity", "normalized_settings",
                     "load_configuration", "service_documents", "descriptor"):
            self.assertFalse(hasattr(tool, name), name)
        for name in ("inputs", "inventory", "snapshot", "ready", "stopped", "check_health",
                     "check_node_labels", "eligible_nodes", "startup_compatible"):
            self.assertFalse(hasattr(self.updater, name), name)

    def test_static_discovery_identities_exist_in_actual_deployment_sources(self):
        for (kind, name), service in tool.CONTROLLERS.items():
            with self.subTest(service=service, name=name):
                texts = [(path.read_text()) for path in (ROOT / "src" / service / "deploy").glob("*.template")]
                self.assertTrue(any(re.search(
                    r"kind:\s*" + kind + r"\s*\n(?:apiVersion:[^\n]*\n)?metadata:\s*\n\s+name:\s*"
                    + re.escape(name) + r"\s*\n",
                    text) for text in texts))

    def test_invalid_kubeconfig_fails_before_mutation(self):
        for content in ("kind: Config\n", "contexts: [broken]\ncurrent-context: missing\n"):
            with self.subTest(content=content), self.assertRaises(ValueError):
                tool.execution_kubeconfig(content)
        self.assertEqual([], self.state()["mutations"])

    def test_pending_step_ignores_configuration_template_and_image_changes(self):
        self.make_plan()
        before = json.loads(self.updater.path.read_text())
        self.config.write_text("entirely new configuration with synthetic-password")
        template = self.root / "src/webportal/deploy/workload.yaml.template"
        template.parent.mkdir(parents=True)
        template.write_text("deliberately not renderable by the updater: {{ missing }}")
        self.docs["webportal"][0]["spec"]["template"] = {"spec": {"containers": [{"image": "changed"}]}}
        self.targets.write_text(json.dumps(self.docs))
        with patch.object(self.updater, "discover", side_effect=AssertionError("Original plan only")):
            self.updater.run()
        after = json.loads(self.updater.path.read_text())
        self.assertEqual(before["run_id"], after["run_id"])
        self.assertEqual(before["service_order"], after["service_order"])
        self.assertEqual("complete", after["phase"])
        self.assertNotIn("synthetic-password", self.updater.path.read_text())

    def test_succeeded_steps_are_not_rechecked_even_if_resources_are_missing(self):
        state = self.make_plan()
        for step in state["steps"][:-1]:
            step["state"] = "succeeded"
        self.updater.save()
        cluster = self.state()
        cluster["resources"] = []
        self.cluster.write_text(json.dumps(cluster))
        with patch.object(self.updater, "discover", side_effect=AssertionError("No rediscovery")):
            self.updater.run()
        self.assertEqual([["webportal", "start"]], self.state()["mutations"])

    def test_resumed_plan_display_preserves_legacy_journal_bytes(self):
        state = self.make_plan()
        state.update(schema_version=1, inputs={"old": "ignored"}, inventory={"old": "ignored"})
        self.updater.save()
        before = self.updater.path.read_bytes()
        self.args.plan = True
        self.updater.run()
        self.assertEqual(before, self.updater.path.read_bytes())
        self.assertEqual([], self.state()["mutations"])

    def test_explicit_stage_conflict_keeps_pending_start_and_journal(self):
        self.make_plan()
        before = self.updater.path.read_bytes()
        self.args.device_plugin = True
        with self.assertRaisesRegex(RuntimeError, "conflicts"):
            self.updater.run()
        self.assertEqual(before, self.updater.path.read_bytes())
        self.assertEqual("pending", json.loads(before)["steps"][-1]["state"])

    def test_durable_zero_exit_is_not_replayed_after_receipt_was_consumed(self):
        step = self.make_plan()["steps"][-1]
        step.update(state="running", exit_code=0)
        with patch.object(self.updater, "execute") as execute:
            self.updater.perform(step, self.root / "unused")
        execute.assert_not_called()
        self.assertEqual("succeeded", step["state"])

    def test_failed_command_retries_once_despite_unchanged_visible_resources(self):
        step = self.make_plan()["steps"][-1]
        step.update(state="failed", exit_code=7)
        with patch.object(self.updater, "execute") as execute:
            self.updater.perform(step, self.root / "unused")
        execute.assert_called_once()
        self.assertEqual("succeeded", step["state"])

    def test_completed_cilium_steps_do_not_require_reading_manifest_on_resume(self):
        state = self.make_plan(selected={"cilium": True, "cluster-configuration": False, "device-plugin": False})
        for step in state["steps"][:2]:
            step["state"] = "succeeded"
        self.updater.save()
        self.assertFalse(self.updater.manifest.exists())
        self.updater.run()
        self.assertNotIn(["cilium", "delete"], self.state()["mutations"])
        self.assertNotIn(["cilium", "apply"], self.state()["mutations"])

    def test_corrupt_receipt_does_not_override_saved_result(self):
        step = self.make_plan()["steps"][-1]
        step.update(state="running", attempt="c" * 32, execution={"identity": "test"})
        path = self.updater.result_path(step)
        path.write_text("{broken")
        before = self.updater.path.read_bytes()
        with self.assertRaises(ValueError):
            self.updater.collect_result(step)
        self.assertEqual(before, self.updater.path.read_bytes())
        self.assertTrue(path.exists())


class ProcessIdentityTest(unittest.TestCase):
    def test_vanished_process_returns_none(self):
        for error in (FileNotFoundError, ProcessLookupError):
            with self.subTest(error=error), \
                    patch.object(Path, "read_text", side_effect=error):
                self.assertIsNone(tool.process_identity(123))

    def test_other_read_errors_are_not_suppressed(self):
        for error in (PermissionError, OSError):
            with self.subTest(error=error), \
                    patch.object(Path, "read_text", side_effect=error), \
                    self.assertRaises(error):
                tool.process_identity(123)

    def test_session_scan_continues_after_process_disappears(self):
        fields = ["S", "1", "123", "456"] + ["0"] * 15 + ["789"]
        stat = "124 (command with spaces) " + " ".join(fields)
        for error in (FileNotFoundError, ProcessLookupError):
            with self.subTest(error=error), \
                    patch.object(Path, "iterdir", return_value=iter(
                        [Path("/proc/123"), Path("/proc/124")]
                    )), \
                    patch.object(Path, "read_text", side_effect=[error(), stat]):
                self.assertEqual(
                    [{"pid": 124, "state": "S", "pgid": 123, "session": 456, "start": "789"}],
                    tool.session_members({"session": 456}),
                )


class CommandErrorTest(unittest.TestCase):
    def test_command_failure_includes_stderr_and_exit_context(self):
        for command in (["kubectl", "get", "deployment"], ["paictl.py", "config", "get-id"]):
            with self.subTest(command=command):
                error = subprocess.CalledProcessError(
                    9, command, output="less useful stdout", stderr="  credentials expired; log in again\n")
                with patch.object(tool.subprocess, "run", side_effect=error), \
                        self.assertRaises(tool.CommandError) as raised:
                    tool.run_command(command)
                self.assertIn(command[0], str(raised.exception))
                self.assertIn("exit 9", str(raised.exception))
                self.assertIn("credentials expired; log in again", str(raised.exception))
                self.assertNotIn("less useful stdout", str(raised.exception))

    def test_command_failure_falls_back_to_stdout_when_stderr_is_empty(self):
        command = ["paictl.py", "config", "get-id"]
        for stderr in (None, "", " \n"):
            with self.subTest(stderr=stderr):
                error = subprocess.CalledProcessError(
                    2, command, output="  configuration download failed\n", stderr=stderr)
                with patch.object(tool.subprocess, "run", side_effect=error), \
                        self.assertRaisesRegex(tool.CommandError, "configuration download failed"):
                    tool.run_command(command)

    def test_raw_kubeconfig_failure_never_includes_stdout(self):
        command = ["kubectl", "config", "view", "--minify", "--flatten", "--raw"]
        for stderr in ("raw export failed", None):
            with self.subTest(stderr=stderr):
                error = subprocess.CalledProcessError(
                    3, command, output="synthetic-kubeconfig-credential", stderr=stderr)
                with patch.object(tool.subprocess, "run", side_effect=error), \
                        self.assertRaises(tool.CommandError) as raised:
                    tool.run_command(command)
                self.assertNotIn("synthetic-kubeconfig-credential", str(raised.exception))
                self.assertIn("exit 3", str(raised.exception))
                if stderr:
                    self.assertIn(stderr, str(raised.exception))

    def test_command_failure_without_output_still_includes_exit_context(self):
        command = ["kubectl", "get", "deployment"]
        error = subprocess.CalledProcessError(4, command)
        with patch.object(tool.subprocess, "run", side_effect=error), \
                self.assertRaisesRegex(tool.CommandError, "exit 4"):
            tool.run_command(command)


if __name__ == "__main__":
    unittest.main()

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("service_update", ROOT / "tools/updatePaiService.py")
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


def controller(service, namespace="default", kind="DaemonSet", name=None):
    return {"kind": kind, "service": service,
            "metadata": {"namespace": namespace, "name": name or service},
            "spec": {"selector": {"matchLabels": {"app": name or service}}},
            "status": {"numberReady": 0}}


FAKE_COMMAND = r'''#!/usr/bin/env python3
import copy, json, os, sys, yaml
from pathlib import Path
args = sys.argv[1:]
state_path = Path(os.environ["FAKE_CLUSTER"])
state = json.loads(state_path.read_text())
with open(os.environ["FAKE_CALLS"], "a") as log:
    log.write(json.dumps([Path(sys.argv[0]).name] + args) + "\n")
def save():
    state_path.write_text(json.dumps(state))
def record(service, action):
    journal = json.loads(Path(os.environ["FAKE_JOURNAL"]).read_text())
    assert any(step["service"] == service and step["action"] == action and step["state"] == "running"
               for step in journal["steps"])
    assert Path.cwd() == Path(os.environ["FAKE_ROOT"])
    state["mutations"].append([service, action])
    state["saved_plans"].append(journal["service_order"])
    cfg = yaml.safe_load(Path(os.environ["KUBECONFIG"]).read_text())
    context = next(item["context"] for item in cfg["contexts"] if item["name"] == cfg["current-context"])
    assert context["namespace"] == "default"
    assert Path(os.environ["KUBECONFIG"]).stat().st_mode & 0o777 == 0o600
if Path(sys.argv[0]).name == "paictl.py":
    if args[:2] == ["config", "get-id"]:
        print(os.environ.get("FAKE_ID_OUTPUT", "Cluster-id is: " + os.environ.get("FAKE_ID", "test")))
        sys.exit(int(os.environ.get("FAKE_ID_EXIT", "0")))
    if args[:2] not in (["service", "start"], ["service", "stop"], ["service", "delete"]):
        sys.exit(91)
    action, service = args[1], args[args.index("-n") + 1]
    supplied = sys.stdin.read()
    assert supplied == ("Y\n" if action == "delete" else "") + "test\n"
    record(service, action)
    state.setdefault("confirmations", []).append([service, action, supplied])
    state.setdefault("config_reads", []).append(Path(os.environ["FAKE_CONFIG"]).read_text())
    save()
    if os.environ.get("FAIL_SERVICE") == service and action == os.environ.get("FAIL_ACTION", "start"):
        sys.exit(7)
    if os.environ.get("NO_RESOURCE_UPDATE") != "1":
        state["resources"] = [item for item in state["resources"]
                              if not (item.get("service") == service
                                      and item["metadata"]["namespace"] == "default")]
        if action == "start":
            state["resources"].extend(copy.deepcopy(
                json.loads(Path(os.environ["FAKE_TARGETS"]).read_text()).get(service, [])))
    save()
elif args == ["config", "view", "--minify", "--flatten", "--raw"]:
    print(json.dumps({"apiVersion": "v1", "kind": "Config", "current-context": "selected",
        "contexts": [{"name": "selected", "context": {"cluster": "cluster", "user": "user",
            "namespace": os.environ.get("FAKE_NAMESPACE", "default")}}],
        "clusters": [{"name": "cluster", "cluster": {"server": "https://cluster.invalid"}}],
        "users": [{"name": "user", "user": {"token": "synthetic-token"}}]}))
elif args == ["get", "deployment,statefulset,daemonset", "-A", "-o", "json"]:
    if os.environ.get("DISCOVERY_ERROR"):
        sys.exit(9)
    print(json.dumps({"items": state["resources"]}))
elif args[0] in ("delete", "apply"):
    action = args[0]
    record("cilium", action)
    manifest = Path(args[args.index("-f") + 1])
    assert manifest.stat().st_mode & 0o777 == 0o600
    state.setdefault("manifests", []).append(manifest.read_text())
    save()
    if os.environ.get("FAIL_CILIUM_ACTION") == action:
        sys.exit(6)
else:
    sys.exit(92)
'''


class ServiceRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for path in (self.bin / "kubectl", self.root / "paictl.py"):
            path.write_text(FAKE_COMMAND)
            path.chmod(0o755)
        self.directory = self.root / "state"
        self.directory.mkdir()
        self.args = type("Args", (), {"cluster_name": "test", "timeout": 3, "plan": False,
                                      "cilium": None, "cluster_configuration": None, "device_plugin": None})()
        self.updater = tool.Updater(self.root, self.args, self.directory)
        self.docs = {"job-exporter": [controller("job-exporter")],
                     "webportal": [controller("webportal", name="webportal-ds")]}
        self.cluster, self.calls = self.root / "cluster.json", self.root / "calls.jsonl"
        self.targets, self.config = self.root / "targets.json", self.root / "live-config"
        self.targets.write_text(json.dumps(self.docs))
        self.config.write_text("port=5432; password=synthetic-one")
        self.cluster.write_text(json.dumps({"resources": [doc for docs in self.docs.values() for doc in docs],
                                           "mutations": [], "saved_plans": []}))
        self.environment = patch.dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"],
                                      FAKE_CLUSTER=str(self.cluster), FAKE_CALLS=str(self.calls),
                                      FAKE_TARGETS=str(self.targets), FAKE_JOURNAL=str(self.updater.path),
                                      FAKE_ROOT=str(self.root), FAKE_CONFIG=str(self.config))
        self.environment.start()
        self.output = io.StringIO()
        self.stdout = contextlib.redirect_stdout(self.output)
        self.stdout.__enter__()

    def tearDown(self):
        self.stdout.__exit__(None, None, None)
        self.environment.stop()
        self.temporary.cleanup()

    def state(self):
        return json.loads(self.cluster.read_text())

    def calls_made(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def make_plan(self, services=None, selected=None):
        selected = selected or dict.fromkeys(tool.OPTIONAL_STAGES, False)
        with patch.object(self.updater, "discover", return_value=services or ["job-exporter", "webportal"]):
            self.updater.prepare(None, selected)
        self.updater.save()
        return self.updater.state

    def test_command_order_original_plan_and_zero_exit_success_without_health_queries(self):
        with patch.dict(os.environ, NO_RESOURCE_UPDATE="1"):
            self.updater.run()
        self.assertEqual([["webportal", "stop"], ["job-exporter", "stop"],
                          ["job-exporter", "start"], ["webportal", "start"]], self.state()["mutations"])
        self.assertTrue(all(plan == ["job-exporter", "webportal"] for plan in self.state()["saved_plans"]))
        journal = json.loads(self.updater.path.read_text())
        self.assertEqual("complete", journal["phase"])
        self.assertTrue(all(step["exit_code"] == 0 for step in journal["steps"]))
        self.assertEqual(1, sum(call[1:3] == ["config", "get-id"] for call in self.calls_made()))
        self.assertEqual([["kubectl", "get", "deployment,statefulset,daemonset", "-A", "-o", "json"]],
                         [call for call in self.calls_made() if call[1] == "get"])
        self.assertIn("All planned service commands completed successfully.", self.output.getvalue())
        self.assertNotIn("verified", self.output.getvalue())
        self.assertEqual([], list(self.directory.glob("*.result.json")))

    def test_start_failure_retains_original_plan_and_repair_retries_only_failed_command(self):
        with patch.dict(os.environ, FAIL_SERVICE="webportal"):
            with self.assertRaisesRegex(RuntimeError, "exit 7"):
                self.updater.run()
        original = json.loads(self.updater.path.read_text())
        self.assertEqual("failed", original["steps"][-1]["state"])
        self.assertEqual(7, original["steps"][-1]["exit_code"])
        self.assertEqual(["job-exporter"], [item["service"] for item in self.state()["resources"]])
        self.config.write_text("port=5544; password=synthetic-two")
        self.updater = tool.Updater(self.root, self.args, self.directory)
        with patch.object(self.updater, "discover", side_effect=AssertionError("Must not rediscover")):
            self.updater.run()
        journal = json.loads(self.updater.path.read_text())
        self.assertEqual(original["run_id"], journal["run_id"])
        self.assertEqual(original["service_order"], journal["service_order"])
        self.assertEqual(5, len(self.state()["mutations"]))
        self.assertEqual(["webportal", "start"], self.state()["mutations"][-1])
        self.assertEqual(self.config.read_text(), self.state()["config_reads"][-1])
        self.assertNotIn("synthetic", self.updater.path.read_text())

    def test_stop_failure_is_fail_fast_and_does_not_enter_start_phase(self):
        with patch.dict(os.environ, FAIL_SERVICE="webportal", FAIL_ACTION="stop"):
            with self.assertRaisesRegex(RuntimeError, "webportal stop failed"):
                self.updater.run()
        self.assertEqual([["webportal", "stop"]], self.state()["mutations"])
        state = json.loads(self.updater.path.read_text())
        self.assertEqual("stopping", state["phase"])
        self.assertEqual("failed", state["steps"][0]["state"])
        self.assertTrue(all(step["state"] == "pending" for step in state["steps"][1:]))

    def test_cluster_mismatch_bad_id_and_nonzero_gate_do_not_mutate(self):
        for env in ({"FAKE_ID": "wrong"}, {"FAKE_ID_OUTPUT": "missing id"},
                    {"FAKE_ID_OUTPUT": "Cluster-id is: test\nCluster-id is: other"},
                    {"FAKE_ID_EXIT": "8"}):
            with self.subTest(env=env), patch.dict(os.environ, **env):
                with self.assertRaises(RuntimeError):
                    self.updater.run()
                self.assertFalse(self.updater.path.exists())
                self.assertEqual([], self.state()["mutations"])

    def test_read_only_plan_does_not_save_or_mutate(self):
        self.args.plan = True
        self.updater.run()
        self.assertFalse(self.updater.path.exists())
        self.assertEqual([], self.state()["mutations"])

    def test_completed_run_creates_new_plan(self):
        self.updater.run()
        first = json.loads(self.updater.path.read_text())["run_id"]
        tool.Updater(self.root, self.args, self.directory).run()
        self.assertNotEqual(first, json.loads(self.updater.path.read_text())["run_id"])
        self.assertEqual(8, len(self.state()["mutations"]))

    def test_optional_order_delete_prompts_and_internal_storage_stop_only(self):
        for stage in tool.OPTIONAL_STAGES:
            setattr(self.args, stage.replace("-", "_"), True)
        state = self.state()
        state["resources"].append(controller("internal-storage", name="internal-storage-create-ds"))
        self.cluster.write_text(json.dumps(state))
        self.updater.manifest.parent.mkdir(parents=True)
        self.updater.manifest.write_text("opaque fixed manifest, not interpreted by updater\n")
        self.updater.run()
        mutations = self.state()["mutations"]
        self.assertEqual([["cilium", "delete"], ["cilium", "apply"],
                          ["cluster-configuration", "stop"], ["cluster-configuration", "start"],
                          ["device-plugin", "delete"], ["device-plugin", "start"]], mutations[:6])
        self.assertIn(["internal-storage", "stop"], mutations)
        self.assertNotIn(["internal-storage", "start"], mutations)
        delete = next(call for call in self.calls_made() if call[:2] == ["kubectl", "delete"])
        self.assertIn("--wait=true", delete)
        self.assertIn("--ignore-not-found", delete)
        self.assertEqual(2, len(self.state()["manifests"]))
        self.assertEqual(*self.state()["manifests"])
        self.assertIn(["device-plugin", "delete", "Y\ntest\n"], self.state()["confirmations"])
        self.assertIn(["device-plugin", "start", "test\n"], self.state()["confirmations"])

    def test_cilium_apply_failure_does_not_repeat_successful_delete_on_resume(self):
        self.args.cilium = True
        self.updater.manifest.parent.mkdir(parents=True)
        self.updater.manifest.write_text("fixed manifest")
        with patch.dict(os.environ, FAIL_CILIUM_ACTION="apply"):
            with self.assertRaisesRegex(RuntimeError, "exit 6"):
                self.updater.run()
        self.args.cilium = None
        tool.Updater(self.root, self.args, self.directory).run()
        self.assertEqual(1, self.state()["mutations"].count(["cilium", "delete"]))
        self.assertEqual(2, self.state()["mutations"].count(["cilium", "apply"]))

    def test_discovery_errors_are_not_an_empty_successful_plan(self):
        with patch.dict(os.environ, DISCOVERY_ERROR="1"):
            with self.assertRaises(tool.CommandError):
                self.updater.run()
        self.assertFalse(self.updater.path.exists())

    def test_original_namespace_is_unchanged_and_wrong_namespace_is_not_selected(self):
        original = self.root / "original-kubeconfig"
        original.write_text("original content must not be changed")
        state = self.state()
        state["resources"].append(controller("job-exporter", "sandbox"))
        self.cluster.write_text(json.dumps(state))
        with patch.dict(os.environ, KUBECONFIG=str(original), FAKE_NAMESPACE="sandbox"):
            self.updater.run()
            self.assertEqual(str(original), os.environ["KUBECONFIG"])
        self.assertEqual("original content must not be changed", original.read_text())
        self.assertTrue(any(item["metadata"]["namespace"] == "sandbox" for item in self.state()["resources"]))

    def test_storage_and_hived_vcs_deduplicate_and_preserve_dependency_order(self):
        resources = [
            controller("cluster-local-storage", kind="StatefulSet", name="cluster-local-storage-sts-one"),
            controller("cluster-local-storage", kind="StatefulSet", name="cluster-local-storage-sts-two"),
            controller("cluster-local-storage-worker", name="cluster-local-storage-worker-ds"),
            controller("hivedscheduler", kind="StatefulSet", name="hivedscheduler-ds-one"),
        ]
        state = self.state()
        state["resources"] = resources
        self.cluster.write_text(json.dumps(state))
        self.assertEqual(["hivedscheduler", "cluster-local-storage-worker", "cluster-local-storage"],
                         self.updater.discover())

    def test_wrong_kinds_namespaces_near_names_and_unmanaged_dynamic_labels_are_not_selected(self):
        resources = [
            controller("webportal", kind="Deployment", name="webportal-ds"),
            controller("webportal", "sandbox", name="webportal-ds"),
            controller("webportal", name="webportal-ds-unmanaged"),
            controller("storage", kind="StatefulSet", name="cluster-local-storage-sts-vc"),
        ]
        resources[-1]["spec"]["selector"]["matchLabels"]["app"] = "not-managed-storage"
        state = self.state()
        state["resources"] = resources
        self.cluster.write_text(json.dumps(state))
        self.assertEqual([], self.updater.discover())

    def test_legacy_progress_migrates_without_frozen_inputs_or_resource_snapshots(self):
        old = self.make_plan()
        old["schema_version"] = 1
        old["inputs"], old["inventory"] = {"obsolete": "changed"}, {"obsolete": ["irrelevant"]}
        for step in old["steps"][:-1]:
            step.update(state="succeeded", snapshot={"legacy": "ignored"}, restart_generation=123)
        old["steps"][-1]["state"] = "failed"
        old["phase"] = "starting"
        self.updater.save()
        self.config.write_text("arbitrarily repaired configuration")
        with patch.object(self.updater, "discover", side_effect=AssertionError("Must preserve old plan")):
            self.updater.run()
        new = json.loads(self.updater.path.read_text())
        self.assertEqual(2, new["schema_version"])
        self.assertEqual(old["run_id"], new["run_id"])
        self.assertEqual([["webportal", "start"]], self.state()["mutations"])
        self.assertNotIn("inputs", new)
        self.assertNotIn("inventory", new)
        self.assertTrue(all("snapshot" not in step and "restart_generation" not in step for step in new["steps"]))

    def test_invalid_journal_and_explicit_stage_conflicts_preserve_file(self):
        valid = copy.deepcopy(self.make_plan())
        for value in ([], {"schema_version": 1}, {**valid, "schema_version": 999},
                      {**valid, "phase": "complete"},
                      {**valid, "steps": valid["steps"][:-1]}, "{broken"):
            with self.subTest(value=value):
                content = value if isinstance(value, str) else json.dumps(value)
                self.updater.path.write_text(content)
                with self.assertRaises((RuntimeError, ValueError)):
                    self.updater.selections()
                self.assertEqual(content, self.updater.path.read_text())
        self.updater.path.write_text(json.dumps(valid))
        self.args.cilium = True
        with self.assertRaisesRegex(RuntimeError, "conflicts"):
            self.updater.selections()

    def test_running_start_with_unknown_result_retries_without_resource_queries(self):
        state = self.make_plan()
        step = state["steps"][-1]
        step["state"] = "running"
        with patch.object(self.updater, "execute") as execute:
            self.updater.perform(step, self.root / "unused")
        execute.assert_called_once()
        self.assertEqual("succeeded", step["state"])

    def test_zero_receipt_recovers_unknown_delete_without_repeating_it(self):
        state = self.make_plan(selected={"cilium": True, "cluster-configuration": False, "device-plugin": False})
        step = state["steps"][0]
        step.update(state="running", execution=dict(tool.process_identity(os.getpid()), **tool.host_identity()),
                    attempt="a" * 32)
        tool.atomic_json(self.updater.result_path(step),
                         {"execution": step["execution"], "exit_code": 0, "error": None})
        with patch.object(tool, "ensure_ended"), patch.object(self.updater, "execute") as execute:
            self.updater.perform(step, self.root / "unused")
        execute.assert_not_called()
        self.assertEqual("succeeded", step["state"])
        self.assertFalse(self.updater.result_path(step).exists())

    def test_unknown_delete_outcome_blocks_destructive_retry(self):
        state = self.make_plan(selected={"cilium": True, "cluster-configuration": False, "device-plugin": False})
        step = state["steps"][0]
        step.update(state="failed", execution=dict(tool.process_identity(os.getpid()), **tool.host_identity()))
        with patch.object(tool, "ensure_ended"), patch.object(self.updater, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "Unknown outcome.*manual recovery"):
                self.updater.perform(step, self.root / "unused")
        execute.assert_not_called()

    def test_invalid_receipt_does_not_become_success(self):
        step = self.make_plan()["steps"][0]
        step.update(attempt="b" * 32, state="running", execution={"opaque": "identity"})
        path = self.updater.result_path(step)
        tool.atomic_json(path, {"execution": {"different": "identity"}, "exit_code": 0, "error": None})
        with self.assertRaisesRegex(RuntimeError, "Invalid command receipt"):
            self.updater.collect_result(step)
        self.assertTrue(path.exists())
        self.assertNotEqual("succeeded", step["state"])


class SupervisorTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.lock = self.root / "operation.lock"
        self.receipt = self.root / "result.json"
        self.process = None
        self.execution_identity = None

    def tearDown(self):
        try:
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=12)
        finally:
            if self.execution_identity:
                self.cleanup_session(self.execution_identity)
            self.temporary.cleanup()

    def launch(self, command, timeout=1):
        read_fd, write_fd = os.pipe()
        self.process = subprocess.Popen([sys.executable, str(ROOT / "tools/updatePaiService.py"),
                                         "--supervise", str(self.lock), str(write_fd)],
                                        pass_fds=(write_fd,), stdin=subprocess.PIPE,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                        text=True, start_new_session=True)
        os.close(write_fd)
        with os.fdopen(read_fd) as output:
            identity = json.loads(output.readline())
        self.execution_identity = identity
        self.process.stdin.write(json.dumps({"command": command, "cwd": str(self.root),
                                            "input": None, "timeout": timeout,
                                            "result_file": str(self.receipt)}) + "\n")
        self.process.stdin.flush()
        return identity

    def live_session(self, identity):
        members = [tool.process_identity(int(path.name)) for path in Path("/proc").iterdir()
                   if path.name.isdigit()]
        return [item for item in members if item and item["session"] == identity["session"]
                and item["state"] not in ("Z", "X")]

    def cleanup_session(self, identity):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            members = self.live_session(identity)
            if not members:
                return
            for item in members:
                current = tool.process_identity(item["pid"])
                if current and current["start"] == item["start"] and current["session"] == identity["session"]:
                    try:
                        os.kill(item["pid"], signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            time.sleep(0.05)
        self.fail("Test-owned session still has live processes")

    def launch_other_group(self, timeout=60, parent_exits=False, ignore_term=False):
        child_path = self.root / "other-group.json"
        child_code = r'''
import json, os, signal, sys, time
from pathlib import Path
os.setpgid(0, 0)
if sys.argv[2] == "ignore":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
path = Path(sys.argv[1])
temporary = path.with_suffix(".tmp")
temporary.write_text(json.dumps({"pid": os.getpid(), "pgid": os.getpgrp(), "session": os.getsid(0)}))
temporary.replace(path)
time.sleep(60)
'''
        parent_code = r'''
import subprocess, sys, time
from pathlib import Path
subprocess.Popen([sys.executable, "-c", sys.argv[1], sys.argv[2], sys.argv[3]],
                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
while not Path(sys.argv[2]).exists():
    time.sleep(0.01)
if sys.argv[4] == "exit":
    raise SystemExit(0)
time.sleep(60)
'''
        identity = self.launch(
            [sys.executable, "-c", parent_code, child_code, str(child_path),
             "ignore" if ignore_term else "normal", "exit" if parent_exits else "wait"], timeout=timeout)
        deadline = time.monotonic() + 5
        while not child_path.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(child_path.exists())
        child = json.loads(child_path.read_text())
        self.assertEqual(identity["session"], child["session"])
        self.assertNotEqual(identity["pgid"], child["pgid"])
        return identity, child

    def test_other_process_group_in_private_session_is_tracked(self):
        identity, child = self.launch_other_group()
        try:
            self.assertIn(child["pid"], [item["pid"] for item in tool.session_members(identity)])
        finally:
            self.cleanup_session(identity)
            self.process.communicate(timeout=3)
        self.assertEqual([], self.live_session(identity))
        tool.ensure_ended(identity, self.lock)

    def test_other_group_orphan_blocks_retry_after_original_group_is_killed(self):
        identity, child = self.launch_other_group()
        try:
            self.process.kill()
            self.process.wait(timeout=3)
            for item in self.live_session(identity):
                if item["pgid"] == identity["pgid"]:
                    current = tool.process_identity(item["pid"])
                    if current and all(current[name] == item[name] for name in ("start", "pgid", "session")):
                        try:
                            os.kill(item["pid"], signal.SIGKILL)
                        except ProcessLookupError:
                            pass
            deadline = time.monotonic() + 3
            while any(item["pgid"] == identity["pgid"] for item in self.live_session(identity)):
                self.assertLess(time.monotonic(), deadline)
                time.sleep(0.02)
            self.assertIn(child["pid"], [item["pid"] for item in self.live_session(identity)])
            with tool.locked(self.lock):
                pass
            with self.assertRaisesRegex(RuntimeError, "still alive"):
                tool.ensure_ended(identity, self.lock)
        finally:
            self.cleanup_session(identity)
            self.process.communicate(timeout=3)
        self.assertEqual([], self.live_session(identity))
        tool.ensure_ended(identity, self.lock)

    def test_timeout_cleans_other_group_even_when_it_ignores_term(self):
        identity, _ = self.launch_other_group(timeout=1, ignore_term=True)
        try:
            self.process.communicate(timeout=15)
            self.assertNotEqual(0, self.process.returncode)
            self.assertEqual([], self.live_session(identity))
            receipt = json.loads(self.receipt.read_text())
            self.assertIsNone(receipt["exit_code"])
            self.assertEqual("TimeoutExpired", receipt["error"])
        finally:
            self.cleanup_session(identity)
        tool.ensure_ended(identity, self.lock)

    def test_zero_exit_with_other_group_descendant_does_not_acknowledge_success(self):
        identity, _ = self.launch_other_group(parent_exits=True, ignore_term=True)
        try:
            self.process.communicate(timeout=15)
            self.assertNotEqual(0, self.process.returncode)
            self.assertEqual([], self.live_session(identity))
            receipt = json.loads(self.receipt.read_text())
            self.assertIsNone(receipt["exit_code"])
            self.assertEqual("RuntimeError", receipt["error"])
        finally:
            self.cleanup_session(identity)
        tool.ensure_ended(identity, self.lock)

    def test_cleanup_rechecks_start_and_session_but_allows_group_changes(self):
        execution = {"session": 123}
        member = {"pid": 456, "start": "old", "pgid": 456, "session": 123}
        for changes, signaled in (({"start": "new"}, False), ({"session": 999}, False),
                                  ({"pgid": 789}, True)):
            with self.subTest(changes=changes), \
                    patch.object(tool, "session_members", side_effect=[[member], []]), \
                    patch.object(tool, "process_identity", return_value=dict(member, **changes)), \
                    patch.object(tool.os, "kill") as kill:
                tool.terminate_members(execution)
                if signaled:
                    kill.assert_called_once_with(member["pid"], signal.SIGTERM)
                else:
                    kill.assert_not_called()

    def test_live_operation_blocks_retry_and_timeout_cleans_descendants(self):
        identity = self.launch([sys.executable, "-c",
                                "import subprocess,time; subprocess.Popen(['sleep','60']); time.sleep(60)"])
        with self.assertRaisesRegex(RuntimeError, "holds"):
            tool.ensure_ended(identity, self.lock)
        self.process.communicate(timeout=15)
        self.assertNotEqual(0, self.process.returncode)
        self.assertEqual([], tool.session_members(identity))
        tool.ensure_ended(identity, self.lock)
        self.assertEqual("TimeoutExpired", json.loads(self.receipt.read_text())["error"])

    def test_receipt_records_real_command_exit_status(self):
        for code in (0, 7):
            identity = self.launch([sys.executable, "-c", f"raise SystemExit({code})"])
            self.process.communicate(timeout=10)
            receipt = json.loads(self.receipt.read_text())
            self.assertEqual(code, self.process.returncode)
            self.assertEqual(code, receipt["exit_code"])
            self.assertEqual(identity, receipt["execution"])
            self.assertIsNone(receipt["error"])

    def test_handled_signal_cleans_descendants(self):
        identity = self.launch(["sleep", "60"], timeout=60)
        deadline = time.monotonic() + 3
        while len(tool.session_members(identity)) < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
        self.process.send_signal(signal.SIGTERM)
        self.process.communicate(timeout=15)
        self.assertNotEqual(0, self.process.returncode)
        self.assertEqual([], tool.session_members(identity))

    def test_uncertain_reused_pid_and_foreign_host_fail_closed(self):
        identity = dict(tool.host_identity(), pid=123, pgid=123, session=123, start="old")
        with patch.object(tool, "process_identity", return_value={"start": "new"}), \
                patch.object(tool, "session_members", return_value=[{"pid": 123}]):
            with self.assertRaisesRegex(RuntimeError, "PID reused"):
                tool.ensure_ended(identity, self.lock)
        identity["host"] = "different-host"
        with self.assertRaisesRegex(RuntimeError, "another host"):
            tool.ensure_ended(identity, self.lock)

    def test_parent_sigkill_preserves_operation_and_durable_exit_receipt(self):
        identity_file = self.root / "identity.json"
        parent_code = r'''
import json, os, subprocess, sys, time
from pathlib import Path
read_fd, write_fd = os.pipe()
supervisor = subprocess.Popen([sys.executable, sys.argv[1], "--supervise", sys.argv[2], str(write_fd)],
    pass_fds=(write_fd,), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    text=True, start_new_session=True)
os.close(write_fd)
with os.fdopen(read_fd) as pipe:
    identity = json.loads(pipe.readline())
supervisor.stdin.write(json.dumps({"command": ["sleep", "2"], "cwd": sys.argv[4],
    "input": None, "timeout": 4, "result_file": sys.argv[5]}) + "\n")
supervisor.stdin.flush()
Path(sys.argv[3]).write_text(json.dumps(identity))
time.sleep(60)
'''
        self.process = subprocess.Popen([sys.executable, "-c", parent_code, str(ROOT / "tools/updatePaiService.py"),
                                         str(self.lock), str(identity_file), str(self.root), str(self.receipt)])
        deadline = time.monotonic() + 5
        while not identity_file.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(identity_file.exists())
        identity = json.loads(identity_file.read_text())
        self.execution_identity = identity
        try:
            self.process.kill()
            self.process.wait(timeout=3)
            with self.assertRaisesRegex(RuntimeError, "holds|alive"):
                tool.ensure_ended(identity, self.lock)
            deadline = time.monotonic() + 8
            while tool.session_members(identity) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertEqual([], tool.session_members(identity))
            tool.ensure_ended(identity, self.lock)
            self.assertEqual(0, json.loads(self.receipt.read_text())["exit_code"])
        finally:
            current = tool.process_identity(identity["pid"])
            if current and current["start"] == identity["start"] and current["state"] not in ("Z", "X"):
                os.kill(identity["pid"], signal.SIGTERM)

    def test_killed_supervisor_leaves_descendants_blocking_retry(self):
        identity = self.launch(["sleep", "60"], timeout=60)
        try:
            deadline = time.monotonic() + 3
            while len(tool.session_members(identity)) < 2 and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertGreaterEqual(len(tool.session_members(identity)), 2)
            self.process.kill()
            self.process.wait(timeout=3)
            with self.assertRaisesRegex(RuntimeError, "session still alive"):
                tool.ensure_ended(identity, self.lock)
        finally:
            tool.terminate_members(identity)
            self.process.communicate(timeout=3)
        self.assertEqual([], tool.session_members(identity))
        self.assertFalse(self.receipt.exists())


if __name__ == "__main__":
    unittest.main()

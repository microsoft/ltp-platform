# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import importlib.util
import itertools
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from jinja2 import Environment, StrictUndefined
import yaml


ROOT = Path(__file__).resolve().parents[1]


class TestPrometheusStartup(unittest.TestCase):
    def test_readiness_and_optional_configuration(self):
        for remote, disk, blob, qos in itertools.product((False, True), repeat=4):
            with self.subTest(remote=remote, disk=disk, blob=blob, qos=qos):
                config = {
                    "cluster": {
                        "docker-registry": {
                            "prefix": "test/", "tag": "test", "secret-name": "",
                        },
                        "common": {
                            "qos-switch": str(qos).lower(), "data-path": "/data",
                        },
                    },
                    "prometheus": {
                        "port": 9091, "url": "http://localhost:9091",
                        "retention_size": "100GB",
                        "disk": "data-pvc" if disk else "",
                        "blob": "blob-pvc" if blob else "",
                        "remote_write": {
                            "image": "remote:test", "ingestion_url": "http://remote",
                            "azure_client_id": "test-client",
                        } if remote else None,
                    },
                    "alert-manager": {"use-pylon": remote},
                    "pylon": {"uri": "http://pylon"},
                }
                template = ROOT / "deploy/prometheus-deployment.yaml.template"
                deployment = yaml.safe_load(
                    Environment(undefined=StrictUndefined).from_string(
                        template.read_text()).render(cluster_cfg=config))
                self.assertEqual(3600, deployment["spec"]["progressDeadlineSeconds"])
                pod = deployment["spec"]["template"]["spec"]
                containers = {c["name"]: c for c in pod["containers"]}
                main = containers["prometheus"]
                self.assertEqual(
                    {"path": "/prometheus/-/ready", "port": "web"},
                    main["readinessProbe"]["httpGet"])
                self.assertNotIn("livenessProbe", main)
                self.assertNotIn("startupProbe", main)
                self.assertIn("--web.route-prefix=prometheus", main["args"])
                self.assertEqual(remote, "prom-remotewrite" in containers)
                if remote:
                    self.assertEqual(
                        "/ready",
                        containers["prom-remotewrite"]["readinessProbe"]["httpGet"]["path"])
                volumes = {v["name"]: v for v in pod["volumes"]}
                self.assertEqual(disk, "persistentVolumeClaim" in volumes["prometheus-data"])
                self.assertEqual(blob, "prometheus-blob" in volumes)

    def test_start_command_propagates_timeout_and_uses_explicit_bound(self):
        for exit_code in (0, 1):
            with self.subTest(exit_code=exit_code), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                for command, body in {
                    "kubectl": "exit 0",
                    "sleep": "exit 0",
                    "python": 'printf "%s\\n" "$*" > "$CALL_LOG"; exit "$CHECK_EXIT"',
                }.items():
                    executable = directory / command
                    executable.write_text("#!/bin/bash\n" + body + "\n")
                    executable.chmod(0o755)
                environment = dict(
                    os.environ, PATH=f"{tmp}:{os.environ['PATH']}",
                    CALL_LOG=str(directory / "calls"), CHECK_EXIT=str(exit_code))
                result = subprocess.run(
                    ["bash", str(ROOT / "deploy/start.sh")],
                    env=environment, capture_output=True, text=True, timeout=10)
                self.assertEqual(exit_code, result.returncode, result.stdout + result.stderr)
                self.assertIn("--timeout 3600", (directory / "calls").read_text())
                if exit_code:
                    self.assertIn("has not been restarted", result.stderr)

    def test_wait_handles_fresh_recovering_and_timed_out_instances(self):
        helper = ROOT.parents[1] / "deployment/k8sPaiLibrary/monitorTool/check_pod_ready_status.py"
        monitorlib = types.ModuleType("k8sPaiLibrary.monitorlib")
        monitorlib.servicestatus = Mock()
        spec = importlib.util.spec_from_file_location(
            "k8sPaiLibrary.monitorTool.check_pod_ready_status", helper)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"k8sPaiLibrary.monitorlib": monitorlib}):
            spec.loader.exec_module(module)
        for states in ([True], [False, False, True]):
            monitorlib.servicestatus.pod_is_ready_or_not.side_effect = states
            with patch.object(module.time, "sleep"):
                module.waiting_until_service_ready("app", "prometheus", 3600)
        monitorlib.servicestatus.pod_is_ready_or_not.side_effect = None
        monitorlib.servicestatus.pod_is_ready_or_not.return_value = False
        with patch.object(module.time, "sleep"), patch.object(
                module.time, "time", side_effect=[0, 3601]):
            with self.assertRaises(SystemExit) as raised:
                module.waiting_until_service_ready("app", "prometheus", 3600)
            self.assertEqual(1, raised.exception.code)


if __name__ == "__main__":
    unittest.main()

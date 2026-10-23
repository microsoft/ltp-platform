# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from pathlib import Path
import unittest

from jinja2 import Environment, StrictUndefined
import yaml


class TestWatchdogDeployment(unittest.TestCase):
    def render(self, qos):
        template = Path(__file__).resolve().parents[1] / "deploy/watchdog.yaml.template"
        config = {
            "cluster": {
                "docker-registry": {"prefix": "test/", "tag": "test", "secret-name": ""},
                "common": {"qos-switch": qos, "k8s-rbac": "true"},
            },
            "hivedscheduler": {"webservice": "http://scheduler"},
        }
        rendered = Environment(undefined=StrictUndefined).from_string(
            template.read_text()).render(cluster_cfg=config)
        return yaml.safe_load(rendered)

    def test_memory_limit_with_qos(self):
        deployment = self.render("true")
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual({"limits": {"memory": "2Gi"}}, container["resources"])

    def test_no_resource_limits_without_qos(self):
        deployment = self.render("false")
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        self.assertNotIn("resources", container)

    def test_fixed_port_instances_do_not_overlap_during_updates(self):
        for qos in ("true", "false"):
            with self.subTest(qos=qos):
                deployment = self.render(qos)
                self.assertEqual({"type": "Recreate"}, deployment["spec"]["strategy"])
                pod = deployment["spec"]["template"]["spec"]
                self.assertTrue(pod["hostNetwork"])
                self.assertEqual(9101, pod["containers"][0]["readinessProbe"]["httpGet"]["port"])


if __name__ == "__main__":
    unittest.main()

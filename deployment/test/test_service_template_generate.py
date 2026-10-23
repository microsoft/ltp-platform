# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import copy
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

from paiLibrary.paiService.service_template_generate import service_template_generate


ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "src/job-exporter/deploy"
REQUIRED = "requiredDuringSchedulingIgnoredDuringExecution"
EXCLUDE = {"key": "no-jobexporter", "operator": "NotIn", "values": ["true"]}


class TestServiceTemplateGenerate(unittest.TestCase):
    def setUp(self):
        self.renderer = service_template_generate(
            {}, "job-exporter", {"deploy-rules": [{"notin": "no-jobexporter"}]})
        self.manifest = {
            "apiVersion": "apps/v1", "kind": "DaemonSet",
            "spec": {"template": {"spec": {}}},
        }

    def render(self):
        return yaml.safe_load(
            self.renderer.add_deploy_rule_to_yaml(yaml.safe_dump(self.manifest)))

    def test_existing_deploy_rules_without_template_affinity(self):
        self.renderer.service_conf["deploy-rules"].append({"in": "pai-worker"})
        expected = {"nodeAffinity": {REQUIRED: {"nodeSelectorTerms": [{
            "matchExpressions": [
                EXCLUDE, {"key": "pai-worker", "operator": "In", "values": ["true"]},
            ],
        }]}}}
        self.assertEqual(expected, self.render()["spec"]["template"]["spec"]["affinity"])

    def test_rules_are_added_to_each_or_term_without_losing_other_affinity(self):
        affinity = {
            "nodeAffinity": {
                REQUIRED: {"nodeSelectorTerms": [
                    {"matchExpressions": [
                        {"key": "vendor", "operator": "In", "values": ["amd"]},
                    ]},
                    {"matchFields": [
                        {"key": "metadata.name", "operator": "In", "values": ["gpu-node"]},
                    ]},
                ]},
                "preferredDuringSchedulingIgnoredDuringExecution": [{
                    "weight": 10, "preference": {"matchExpressions": [
                        {"key": "zone", "operator": "In", "values": ["a"]},
                    ]},
                }],
            },
            "podAntiAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": [{
                "topologyKey": "kubernetes.io/hostname",
                "labelSelector": {"matchLabels": {"app": "other"}},
            }]},
        }
        self.manifest["spec"]["template"]["spec"]["affinity"] = copy.deepcopy(affinity)
        expected = copy.deepcopy(affinity)
        for term in expected["nodeAffinity"][REQUIRED]["nodeSelectorTerms"]:
            term.setdefault("matchExpressions", []).append(EXCLUDE)
        self.assertEqual(expected, self.render()["spec"]["template"]["spec"]["affinity"])

    def test_empty_required_selectors_still_match_no_nodes(self):
        for terms in (None, [], [{}], [{"matchExpressions": []}]):
            with self.subTest(terms=terms):
                self.manifest["spec"]["template"]["spec"]["affinity"] = {
                    "nodeAffinity": {REQUIRED: {"nodeSelectorTerms": terms}},
                }
                self.assertEqual(self.manifest, self.render())

    def test_null_optional_affinity_is_treated_as_absent(self):
        for affinity in (None, {"nodeAffinity": None}, {"nodeAffinity": {REQUIRED: None}}):
            with self.subTest(affinity=affinity):
                self.manifest["spec"]["template"]["spec"]["affinity"] = affinity
                self.assertEqual(
                    {"nodeAffinity": {REQUIRED: {"nodeSelectorTerms": [
                        {"matchExpressions": [EXCLUDE]},
                    ]}}},
                    self.render()["spec"]["template"]["spec"]["affinity"])

    def test_empty_deploy_rules_do_not_add_affinity(self):
        self.renderer.service_conf["deploy-rules"] = []
        self.assertEqual(self.manifest, self.render())

    def test_non_workload_and_empty_templates_are_unchanged(self):
        for source in ("", "apiVersion: v1\nkind: ConfigMap\ndata: {}\n"):
            self.assertEqual(source, self.renderer.add_deploy_rule_to_yaml(source))


class TestGpuExporterDeployment(unittest.TestCase):
    def render_manifests(self, qos="true", secret=""):
        config = {
            "cluster": {
                "common": {"qos-switch": qos, "cluster-type": "k8s"},
                "docker-registry": {"prefix": "test/", "tag": "test", "secret-name": secret},
            },
            "job-exporter": {
                "job-port": 9102, "gpu-port": 8000, "net-port": 8001,
                "node-port": 8002, "logging-level": "INFO", "net_exporter_interval": 5,
            },
            "prometheus": {"scrape_interval": 30},
        }
        service = yaml.safe_load((DEPLOY / "service.yaml").read_text())
        renderer = service_template_generate(config, "job-exporter", service)
        with patch(
                "paiLibrary.paiService.service_template_generate.file_handler.write_generated_file"
        ) as write:
            renderer.generate_template()
        return {
            Path(call.args[0]).name: yaml.safe_load(call.args[1])
            for call in write.call_args_list
        }

    def test_registered_templates_preserve_other_exporters_and_scraping(self):
        for qos in ("true", "false"):
            for secret in ("", "registry-secret"):
                with self.subTest(qos=qos, secret=secret):
                    manifests = self.render_manifests(qos, secret)
                    self.assertEqual(
                        {"job-exporter.yaml", "moneo-gpu-exporter.yaml"}, set(manifests))
                    main, gpu = (manifests[name] for name in (
                        "job-exporter.yaml", "moneo-gpu-exporter.yaml"))
                    self.assertEqual(
                        ["job-exporter", "moneo-net-exporter", "moneo-node-exporter"],
                        [c["name"] for c in main["spec"]["template"]["spec"]["containers"]])
                    self.assertEqual(
                        ["moneo-gpu-exporter"],
                        [c["name"] for c in gpu["spec"]["template"]["spec"]["containers"]])
                    self.assertNotEqual(
                        main["spec"]["selector"], gpu["spec"]["selector"])
                    for manifest in (main, gpu):
                        pod = manifest["spec"]["template"]
                        self.assertEqual(
                            manifest["spec"]["selector"]["matchLabels"], pod["metadata"]["labels"])
                        self.assertEqual("true", pod["metadata"]["annotations"]["prometheus.io/scrape"])
                        self.assertEqual("/metrics", pod["metadata"]["annotations"]["prometheus.io/path"])
                        self.assertTrue(pod["spec"]["hostNetwork"])
                        self.assertEqual(
                            bool(secret), "imagePullSecrets" in pod["spec"])

    def test_gpu_scheduling_uses_vendor_and_preserves_service_exclusion(self):
        manifests = self.render_manifests()
        main = manifests["job-exporter.yaml"]["spec"]["template"]["spec"]
        gpu = manifests["moneo-gpu-exporter.yaml"]["spec"]["template"]["spec"]
        main_rules = main["affinity"]["nodeAffinity"][REQUIRED]["nodeSelectorTerms"]
        gpu_rules = gpu["affinity"]["nodeAffinity"][REQUIRED]["nodeSelectorTerms"]
        self.assertEqual([{"matchExpressions": [EXCLUDE]}], main_rules)
        self.assertEqual([{"matchExpressions": [
            {"key": "vendor", "operator": "In", "values": ["amd", "nvidia"]}, EXCLUDE,
        ]}], gpu_rules)
        for vendor in ("amd", "nvidia", "cpu", "unknown", None):
            for excluded in (False, True):
                labels = {"no-jobexporter": "true"} if excluded else {}
                if vendor:
                    labels["vendor"] = vendor
                matches = all(
                    (labels.get(rule["key"]) in rule["values"])
                    if rule["operator"] == "In"
                    else (labels.get(rule["key"]) not in rule["values"])
                    for rule in gpu_rules[0]["matchExpressions"])
                self.assertEqual(vendor in ("amd", "nvidia") and not excluded, matches)

    def run_lifecycle(self, script, fail_command=""):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            kubectl = directory / "kubectl"
            kubectl.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\n'
                'if [ "$*" = "$FAIL_COMMAND" ]; then exit 7; fi\n')
            kubectl.chmod(0o755)
            result = subprocess.run(
                ["bash", str(DEPLOY / script)],
                env=dict(
                    os.environ, PATH=f"{tmp}:{os.environ['PATH']}",
                    CALL_LOG=str(directory / "calls"), FAIL_COMMAND=fail_command),
                capture_output=True, text=True, timeout=10)
            return result, (directory / "calls").read_text().splitlines()

    def test_start_waits_for_migration_and_gpu_rollout_with_bounded_timeouts(self):
        expected = [
            "apply --overwrite=true -f job-exporter.yaml",
            "rollout status daemonset/job-exporter --timeout=3600s",
            "apply --overwrite=true -f moneo-gpu-exporter.yaml",
            "rollout status daemonset/moneo-gpu-exporter --timeout=3600s",
        ]
        result, calls = self.run_lifecycle("start.sh")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(expected, calls)
        for index, command in enumerate(expected):
            with self.subTest(failure=command):
                result, calls = self.run_lifecycle("start.sh", command)
                self.assertEqual(7, result.returncode)
                self.assertEqual(expected[:index + 1], calls)

    def test_stop_handles_both_daemonsets_and_propagates_failures(self):
        command = "delete --ignore-not-found --now daemonset/job-exporter daemonset/moneo-gpu-exporter"
        for failure, status in (("", 0), (command, 7)):
            result, calls = self.run_lifecycle("stop.sh", failure)
            self.assertEqual(status, result.returncode, result.stderr)
            self.assertEqual([command], calls)


if __name__ == "__main__":
    unittest.main()

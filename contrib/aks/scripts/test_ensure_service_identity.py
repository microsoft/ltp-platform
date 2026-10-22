# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import copy
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    "ensure_service_identity", Path(__file__).with_name("ensure-service-identity.py")
)
provision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(provision)

IDENTITY = "/subscriptions/sub/resourceGroups/shared/providers/Microsoft.ManagedIdentity/userAssignedIdentities/login"
EXISTING = "/subscriptions/sub/resourceGroups/shared/providers/Microsoft.ManagedIdentity/userAssignedIdentities/storage"


class ServiceIdentityTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.pools = [
            {"name": "services", "mode": "User", "nodeLabels": {"pai-master": "true"}},
            {"name": "system", "mode": "System", "nodeLabels": {}},
            {"name": "workers", "mode": "User", "nodeLabels": {"pai-worker": "true"}},
        ]
        self.models = {
            name: {
                "name": name,
                "tags": {"aks-managed-poolName": pool},
                "identity": {
                    "type": "SystemAssigned, UserAssigned",
                    "userAssignedIdentities": {EXISTING: {}},
                },
            }
            for name, pool in [
                ("service-vmss", "services"),
                ("system-vmss", "system"),
                ("worker-vmss", "workers"),
            ]
        }
        self.az_patch = patch.object(provision, "az", side_effect=self.fake_az)
        self.az_patch.start()
        self.addCleanup(self.az_patch.stop)
        self.output_patch = patch("builtins.print")
        self.output_patch.start()
        self.addCleanup(self.output_patch.stop)

    def fake_az(self, *args):
        self.calls.append(args)
        if args[:2] == ("identity", "show"):
            return {"id": IDENTITY}
        if args[:2] == ("aks", "show"):
            return {
                "id": "/subscriptions/sub/resourceGroups/cluster/providers/Microsoft.ContainerService/managedClusters/aks",
                "nodeResourceGroup": "nodes",
            }
        if args[:3] == ("aks", "nodepool", "list"):
            return copy.deepcopy(self.pools)
        if args[:2] == ("vmss", "list"):
            return copy.deepcopy(list(self.models.values()))
        if args[:3] == ("vmss", "identity", "assign"):
            model = self.models[args[args.index("--name") + 1]]
            identity = model.get("identity") or {}
            identities = identity.get("userAssignedIdentities") or {}
            identities[IDENTITY] = {}
            identity["userAssignedIdentities"] = identities
            identity["type"] = (
                "SystemAssigned, UserAssigned"
                if "SystemAssigned" in identity.get("type", "") else "UserAssigned"
            )
            model["identity"] = identity
            return model["identity"]
        if args[:2] == ("vmss", "show"):
            return copy.deepcopy(self.models[args[args.index("--name") + 1]])
        if args[:3] == ("deployment", "group", "create"):
            return {}
        self.fail("Unexpected Azure CLI command: " + repr(args))

    def run_ensure(self, check_only=False):
        provision.ensure_identity("cluster", "aks", IDENTITY, check_only)

    def assignments(self):
        return [args for args in self.calls if args[:3] == ("vmss", "identity", "assign")]

    def test_assigns_only_service_vmss_and_preserves_existing_identities(self):
        self.run_ensure()
        self.assertEqual(len(self.assignments()), 1)
        self.assertEqual(
            provision.identity_ids(self.models["service-vmss"]),
            {EXISTING.lower(), IDENTITY.lower()},
        )
        for name in ["system-vmss", "worker-vmss"]:
            self.assertEqual(provision.identity_ids(self.models[name]), {EXISTING.lower()})
        self.assertIn("--subscription", self.assignments()[0])

    def test_repeated_assignment_is_idempotent(self):
        self.run_ensure()
        self.run_ensure()
        self.assertEqual(len(self.assignments()), 1)

    def test_handles_vmss_without_an_identity(self):
        self.models["service-vmss"]["identity"] = None
        self.run_ensure()
        self.assertEqual(
            provision.identity_ids(self.models["service-vmss"]), {IDENTITY.lower()}
        )

    def test_preserves_a_system_identity_with_null_user_identities(self):
        self.models["service-vmss"]["identity"] = {
            "type": "SystemAssigned", "userAssignedIdentities": None,
        }
        self.run_ensure()
        self.assertIn("SystemAssigned", self.models["service-vmss"]["identity"]["type"])

    def test_checks_present_identity_case_insensitively_without_writes(self):
        self.models["service-vmss"]["identity"]["userAssignedIdentities"][IDENTITY.upper()] = {}
        self.run_ensure(check_only=True)
        self.assertEqual(self.assignments(), [])

    def test_check_only_fails_on_missing_identity_without_writes(self):
        with self.assertRaisesRegex(RuntimeError, "identity is missing"):
            self.run_ensure(check_only=True)
        self.assertEqual(self.assignments(), [])

    def test_handles_multiple_vmsses_for_a_service_pool(self):
        self.models["replacement-vmss"] = copy.deepcopy(self.models["service-vmss"])
        self.models["replacement-vmss"]["name"] = "replacement-vmss"
        self.run_ensure()
        self.assertEqual(len(self.assignments()), 2)

    def test_rejects_service_pool_that_also_runs_workers(self):
        self.pools[0]["nodeLabels"]["pai-worker"] = "true"
        with self.assertRaisesRegex(RuntimeError, "isolated User node pool"):
            self.run_ensure()
        self.assertEqual(self.assignments(), [])

    def test_rejects_system_pool_labeled_as_service(self):
        self.pools[0]["mode"] = "System"
        with self.assertRaisesRegex(RuntimeError, "isolated User node pool"):
            self.run_ensure()

    def test_fails_before_writes_if_any_service_pool_has_no_vmss(self):
        self.pools.append(
            {"name": "missing", "mode": "User", "nodeLabels": {"pai-master": "true"}}
        )
        with self.assertRaisesRegex(RuntimeError, "every service node pool"):
            self.run_ensure()
        self.assertEqual(self.assignments(), [])

    def test_fails_without_a_service_pool(self):
        self.pools[0]["nodeLabels"] = {}
        with self.assertRaisesRegex(RuntimeError, "No service node pool"):
            self.run_ensure()
        self.assertEqual(self.assignments(), [])

    def test_fails_when_azure_does_not_persist_assignment(self):
        def missing_assignment(*args):
            if args[:3] == ("vmss", "identity", "assign"):
                return {}
            return self.fake_az(*args)

        provision.az.side_effect = missing_assignment
        with self.assertRaisesRegex(RuntimeError, "MI assignment is missing"):
            self.run_ensure()

    def test_fails_if_an_existing_user_identity_is_lost(self):
        def destructive_assignment(*args):
            result = self.fake_az(*args)
            if args[:3] == ("vmss", "identity", "assign"):
                self.models["service-vmss"]["identity"]["userAssignedIdentities"].pop(EXISTING)
            return result

        provision.az.side_effect = destructive_assignment
        with self.assertRaisesRegex(RuntimeError, "existing identity was lost"):
            self.run_ensure()

    def test_fails_if_system_identity_is_lost(self):
        def destructive_assignment(*args):
            result = self.fake_az(*args)
            if args[:3] == ("vmss", "identity", "assign"):
                self.models["service-vmss"]["identity"]["type"] = "UserAssigned"
            return result

        provision.az.side_effect = destructive_assignment
        with self.assertRaisesRegex(RuntimeError, "system-assigned identity was lost"):
            self.run_ensure()

    def test_creation_deploys_before_binding(self):
        with patch("sys.argv", [
            "ensure-service-identity.py", "--resource-group", "cluster",
            "--identity-resource-id", IDENTITY,
            "--deploy-parameters", "contrib/aks/aks.bicepparam",
        ]):
            self.assertEqual(provision.main(), 0)
        commands = [args[:3] for args in self.calls]
        self.assertLess(
            commands.index(("deployment", "group", "create")),
            commands.index(("vmss", "identity", "assign")),
        )

    def test_deployment_failure_stops_before_identity_assignment(self):
        def fail_deploy(*args):
            if args[:3] == ("deployment", "group", "create"):
                raise RuntimeError("Deployment failed")
            return self.fake_az(*args)

        provision.az.side_effect = fail_deploy
        with patch("sys.argv", [
            "ensure-service-identity.py", "--resource-group", "cluster",
            "--identity-resource-id", IDENTITY, "--deploy-parameters", "params.bicepparam",
        ]):
            self.assertEqual(provision.main(), 1)
        self.assertEqual(self.assignments(), [])


class AzureCliTest(unittest.TestCase):
    def test_surfaces_cli_errors(self):
        result = subprocess.CompletedProcess([], 1, "", "Permission denied")
        with patch.object(provision.shutil, "which", return_value="az"), \
                patch.object(provision.subprocess, "run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "Permission denied"):
                provision.az("aks", "show")

    def test_reports_missing_azure_cli(self):
        with patch.object(provision.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Azure CLI is not installed"):
                provision.az("aks", "show")


if __name__ == "__main__":
    unittest.main()

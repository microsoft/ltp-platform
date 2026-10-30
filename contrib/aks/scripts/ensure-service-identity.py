#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
import json
import shutil
import subprocess
import sys


def az(*args):
    executable = shutil.which("az")
    if not executable:
        raise RuntimeError("Azure CLI is not installed or is not on PATH")
    result = subprocess.run(
        [executable, *args, "--output", "json", "--only-show-errors"],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Azure CLI command failed")
    return json.loads(result.stdout)


def identity_ids(vmss):
    return {
        resource_id.lower()
        for resource_id in (
            (vmss.get("identity") or {}).get("userAssignedIdentities") or {}
        )
    }


def ensure_identity(resource_group, cluster_name, identity_resource_id, check_only=False):
    identity = az("identity", "show", "--ids", identity_resource_id)
    identity_resource_id = identity["id"]
    cluster = az("aks", "show", "--resource-group", resource_group, "--name", cluster_name)
    subscription = cluster["id"].split("/")[2]
    pools = az(
        "aks", "nodepool", "list", "--resource-group", resource_group,
        "--cluster-name", cluster_name, "--subscription", subscription,
    )
    service_pools = set()
    for pool in pools:
        labels = pool.get("nodeLabels") or {}
        if labels.get("pai-master") == "true":
            if labels.get("pai-worker") == "true" or pool.get("mode") != "User":
                raise RuntimeError("The service identity requires an isolated User node pool")
            service_pools.add(pool["name"])
    if not service_pools:
        raise RuntimeError("No service node pool labeled pai-master=true was found")

    node_group = cluster["nodeResourceGroup"]
    scale_sets = az(
        "vmss", "list", "--resource-group", node_group, "--subscription", subscription,
    )
    targets = [
        vmss for vmss in scale_sets
        if (vmss.get("tags") or {}).get("aks-managed-poolName") in service_pools
    ]
    matched_pools = {
        vmss["tags"]["aks-managed-poolName"] for vmss in targets
    }
    if matched_pools != service_pools:
        raise RuntimeError("Cannot find a VMSS for every service node pool")

    for vmss in targets:
        before = identity_ids(vmss)
        expected = before | {identity_resource_id.lower()}
        if identity_resource_id.lower() not in before:
            if check_only:
                raise RuntimeError("Service identity is missing from VMSS " + vmss["name"])
            az(
                "vmss", "identity", "assign", "--resource-group", node_group,
                "--name", vmss["name"], "--subscription", subscription,
                "--identities", identity_resource_id,
            )
        updated = az(
            "vmss", "show", "--resource-group", node_group, "--name", vmss["name"],
            "--subscription", subscription,
        )
        if not expected.issubset(identity_ids(updated)):
            raise RuntimeError("MI assignment is missing or an existing identity was lost: " + vmss["name"])
        if "SystemAssigned" in (vmss.get("identity") or {}).get("type", ""):
            if "SystemAssigned" not in (updated.get("identity") or {}).get("type", ""):
                raise RuntimeError("The existing system-assigned identity was lost: " + vmss["name"])
        print("Verified service VMSS identity model: " + vmss["name"])
    print("Validate native IMDS acquisition and user login on every REST Server node.")


def main():
    parser = argparse.ArgumentParser(
        description="Ensure native login MI assignment on isolated AKS service node pools."
    )
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--cluster-name", default="aks-openpai")
    parser.add_argument("--identity-resource-id", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument(
        "--deploy-parameters",
        help="Deploy the AKS Bicep parameter file before assigning the existing identity.",
    )
    args = parser.parse_args()
    try:
        if args.deploy_parameters:
            az("identity", "show", "--ids", args.identity_resource_id)
            az(
                "deployment", "group", "create", "--resource-group", args.resource_group,
                "--parameters", args.deploy_parameters,
            )
        ensure_identity(
            args.resource_group, args.cluster_name, args.identity_resource_id,
            args.check_only,
        )
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print("Service identity provisioning failed: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


RESOURCE_TYPES = ("deployment", "statefulset", "daemonset")
SERVICE_ORDER = (
    "node-exporter",
    "job-exporter",
    "log-manager",
    "copilot-chat",
    "dashboard-data-backup",
    "prometheus",
    "prometheus-pushgateway",
    "grafana",
    "alert-manager",
    "watchdog",
    "internal-storage",
    "postgresql",
    "frameworkcontroller",
    "database-controller",
    "fluentd",
    "hivedscheduler",
    "cluster-local-storage-worker",
    "cluster-local-storage",
    "ssh-proxy",
    "utilization-reporter",
    "rest-server",
    "model-proxy",
    "webportal",
    "pylon",
)
# Preserve the legacy updater's stop-without-restart behavior.
STOP_ONLY_SERVICES = {"internal-storage"}


def clean_service_name(service_name):
    for suffix in ("-deployment", "-sts", "-hs", "-ds"):
        if service_name.endswith(suffix):
            return service_name[: -len(suffix)]
    return service_name


def run_command(command, cluster_name=None, timeout=None, cwd=None):
    input_text = None if cluster_name is None else f"{cluster_name}\n"
    return subprocess.run(
        command,
        input=input_text,
        text=True,
        check=True,
        timeout=timeout,
        cwd=cwd,
    )


def get_running_services():
    services = set()
    for resource_type in RESOURCE_TYPES:
        result = subprocess.run(
            [
                "kubectl",
                "get",
                resource_type,
                "-o",
                "jsonpath={.items[*].metadata.name}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        services.update(
            clean_service_name(name) for name in result.stdout.strip().split()
        )

    if "alertmanager" in services:
        services.remove("alertmanager")
        services.add("alert-manager")
    return services


def restart_service(paictl, repo_root, action, service, cluster_name):
    print(f"[{action.upper()}] {service}")
    try:
        run_command(
            [str(paictl), "service", action, "-n", service],
            cluster_name=cluster_name,
            timeout=5 * 60,
            cwd=repo_root,
        )
    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] {service}: {action} exceeded 5 minutes", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as error:
        print(
            f"[ERROR] {service}: {action} failed with exit code {error.returncode}",
            file=sys.stderr,
        )
        return False
    return True


def parse_args():
    parser = argparse.ArgumentParser(description="Restart running PAI services in order.")
    parser.add_argument("--cluster-name", required=True, help="Name of the target cluster.")
    return parser.parse_args()


def main():
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    paictl = repo_root / "paictl.py"

    try:
        running_services = get_running_services()
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"[ERROR] Failed to query running Kubernetes services: {error}", file=sys.stderr)
        return 1

    print("Running services: " + ", ".join(sorted(running_services)))

    managed_services = [service for service in SERVICE_ORDER if service in running_services]
    unmanaged_services = sorted(running_services.difference(SERVICE_ORDER))
    if unmanaged_services:
        print(
            "[WARNING] Running resources not mapped to the restart order: "
            + ", ".join(unmanaged_services)
        )

    failures = []
    with tempfile.TemporaryDirectory(prefix="pai-config-") as config_dir:
        try:
            run_command(
                [str(paictl), "config", "pull", "-o", config_dir],
                cluster_name=args.cluster_name,
                cwd=repo_root,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            print(f"[ERROR] Failed to pull cluster configuration: {error}", file=sys.stderr)
            return 1

        for service in reversed(managed_services):
            if not restart_service(
                paictl, repo_root, "stop", service, args.cluster_name
            ):
                failures.append(f"stop:{service}")

        for service in managed_services:
            if service in STOP_ONLY_SERVICES:
                continue
            if not restart_service(
                paictl, repo_root, "start", service, args.cluster_name
            ):
                failures.append(f"start:{service}")

    if failures:
        print("[ERROR] Service update completed with failures: " + ", ".join(failures))
        return 1

    print("PAI service update completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

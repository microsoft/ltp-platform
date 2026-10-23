# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from pathlib import Path
import subprocess
import unittest


class TestInitialization(unittest.TestCase):
    """Run initialization in a disposable service-image filesystem, never the host."""

    def run_init(self, worker=False, failing_service=""):
        script = Path(__file__).resolve().parents[1] / "bin/init.sh"
        command = """
mkdir -p /secret
ssh-keygen -q -t ed25519 -N '' -f /secret/ssh_host_ed25519_key
service() {
  echo "$1" >> /tmp/services
  if [ "$1" = "$FAILING_SERVICE" ]; then
    echo "service $1 failed" >&2
    return 42
  fi
}
export -f service
bash /test-init.sh || exit $?
test -s /etc/ssh/ssh_host_ed25519_key || exit 1
grep -q 'Port 23333' /root/.ssh/config || exit 1
if [ -n "$CLUSTER_LOCAL_STORAGE_WORKER" ]; then
  test "$(cat /tmp/services)" = "$(printf 'ssh\\nrsync')" || exit 1
  grep -q 'port = 8873' /etc/rsyncd.conf || exit 1
  grep -q 'path = /clstore' /etc/rsyncd.conf || exit 1
  test -s /root/.ssh/authorized_keys || exit 1
else
  test ! -e /tmp/services || exit 1
  bash /test-init.sh || exit $?
fi
"""
        return subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none",
                "-v", f"{script}:/test-init.sh:ro",
                "-e", f"CLUSTER_LOCAL_STORAGE_WORKER={'TRUE' if worker else ''}",
                "-e", "CLUSTER_LOCAL_STORAGE_IPOIB_NUM=0",
                "-e", "CLUSTER_LOCAL_STORAGE_ROOT=/clstore",
                "-e", f"FAILING_SERVICE={failing_service}",
                "--entrypoint", "/bin/bash",
                os.environ.get("CLSTORE_TEST_IMAGE", "cluster-local-storage:latest"),
                "-c", command,
            ],
            capture_output=True, text=True, timeout=60,
        )

    def test_controllers_only_initialize_ssh_clients(self):
        result = self.run_init()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_workers_initialize_both_servers(self):
        result = self.run_init(worker=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_worker_startup_failures_are_not_hidden(self):
        for service in ("ssh", "rsync"):
            with self.subTest(service=service):
                result = self.run_init(worker=True, failing_service=service)
                self.assertEqual(42, result.returncode, result.stdout + result.stderr)
                self.assertIn(f"service {service} failed", result.stderr)


if __name__ == "__main__":
    unittest.main()

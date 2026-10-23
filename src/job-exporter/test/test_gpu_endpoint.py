# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.request import urlopen

from prometheus_client import generate_latest, start_http_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from non_gpu_exporter import non_gpu_registry


class TestGpuEndpoint(unittest.TestCase):
    def add_device(self, directory, vendor, device_class):
        device = directory / "0000:01:00.0"
        device.mkdir()
        (device / "vendor").write_text(vendor)
        (device / "class").write_text(device_class)

    def test_non_gpu_endpoint_is_scrapable_without_gpu_samples(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.add_device(Path(tmp), "0x1002", "0x040300")
            registry = non_gpu_registry(Path(tmp))
            server, thread = start_http_server(0, addr="127.0.0.1", registry=registry)
            try:
                with urlopen(f"http://127.0.0.1:{server.server_port}/metrics", timeout=5) as response:
                    self.assertEqual(200, response.status)
                    self.assertEqual(generate_latest(registry), response.read())
                samples = [
                    line for line in generate_latest(registry).decode().splitlines()
                    if not line.startswith("#")]
                self.assertEqual(["gpu_exporter_applicable 0.0"], samples)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_missing_gpu_drivers_do_not_become_healthy_non_gpu_endpoints(self):
        for vendor in ("0x1002", "0x10de"):
            for device_class in ("0x030000", "0x030200", "0x120000"):
                with self.subTest(vendor=vendor, device_class=device_class):
                    with tempfile.TemporaryDirectory() as tmp:
                        self.add_device(Path(tmp), vendor, device_class)
                        with self.assertRaisesRegex(RuntimeError, "GPU hardware detected"):
                            non_gpu_registry(Path(tmp))

    def test_missing_or_unreadable_pci_inventory_is_not_assumed_non_gpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, "Cannot inspect PCI"):
                non_gpu_registry(directory / "missing")
            (directory / "device").mkdir()
            with self.assertRaises(FileNotFoundError):
                non_gpu_registry(directory)

    def test_driver_dispatch_and_exporter_failures(self):
        entrypoint = Path(__file__).resolve().parents[1] / "build/moneo-gpu-exporter_entrypoint.sh"
        for module, expected in (
            ("amdgpu", "/Moneo/src/worker/exporters/amd_exporter.py"),
            ("nvidia", "/Moneo/src/worker/exporters/nvidia_exporter.py"),
            ("", "/job_exporter/non_gpu_exporter.py --port 18000"),
        ):
            with self.subTest(module=module), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                for command, body in {
                    "lsmod": 'echo "$GPU_MODULE"',
                    "nohup": "exit 0",
                    "python3": 'echo "$*"; exit 7',
                }.items():
                    executable = directory / command
                    executable.write_text("#!/bin/bash\n" + body + "\n")
                    executable.chmod(0o755)
                result = subprocess.run(
                    ["bash", str(entrypoint), "18000"],
                    env=dict(os.environ, PATH=f"{tmp}:{os.environ['PATH']}", GPU_MODULE=module),
                    capture_output=True, text=True, timeout=5)
                self.assertEqual(7, result.returncode, result.stdout + result.stderr)
                self.assertIn(expected, result.stdout)
                if module:
                    self.assertNotIn("non_gpu_exporter.py", result.stdout)


if __name__ == "__main__":
    unittest.main()

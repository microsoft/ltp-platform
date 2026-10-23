# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
from pathlib import Path

from prometheus_client import CollectorRegistry, Gauge, start_http_server


def non_gpu_registry(pci_devices=Path("/sys/bus/pci/devices")):
    # Absence of a driver alone does not establish absence of GPU hardware.
    if not pci_devices.is_dir():
        raise RuntimeError("Cannot inspect PCI devices to establish GPU applicability")
    for device in pci_devices.iterdir():
        vendor = int((device / "vendor").read_text().strip(), 16)
        device_class = int((device / "class").read_text().strip(), 16) >> 16
        if vendor in (0x1002, 0x10DE) and device_class in (0x03, 0x12):
            raise RuntimeError(
                f"GPU hardware detected at {device.name}, but no AMD/NVIDIA driver "
                "is loaded; refusing to serve a non-GPU endpoint")

    registry = CollectorRegistry()
    Gauge(
        "gpu_exporter_applicable",
        "Whether this endpoint is applicable to GPU hardware (0 = non-GPU node).",
        registry=registry,
    ).set(0)
    return registry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    registry = non_gpu_registry()
    print(
        f"No GPU hardware detected. Serving non-GPU applicability on port {args.port}.",
        flush=True,
    )
    _, thread = start_http_server(args.port, registry=registry)
    thread.join()


if __name__ == "__main__":
    main()

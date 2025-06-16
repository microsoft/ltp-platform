import subprocess
import sys
import re
import fileinput

#!/usr/bin/env python3


def get_dcgm_version():
    try:
        result = subprocess.run(
            ["dpkg", "--list", "datacenter-gpu-manager"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        for line in result.stdout.splitlines():
            if line.startswith("ii") and "datacenter-gpu-manager" in line:
                # Example line: ii  datacenter-gpu-manager  1.2.3-1  amd64  NVIDIA datacenter GPU management tools
                parts = re.split(r'\s+', line)
                if len(parts) >= 3:
                    return parts[2]
        print("datacenter-gpu-manager is not installed.", file=sys.stderr)
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        print("Error running dpkg:", e, file=sys.stderr)
        sys.exit(0)


def get_cuda_version():
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        for line in result.stdout.splitlines():
            match = re.search(r"CUDA Version:\s*([\d\.]+)", line)
            if match:
                return match.group(1)
        print("CUDA version not found in nvidia-smi output.", file=sys.stderr)
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        print("Error running nvidia-smi:", e, file=sys.stderr)
        sys.exit(0)


def remove_dcgm():
    try:
        subprocess.run(
            ["apt", "purge", "--yes", "datacenter-gpu-manager"],
            check=True
        )
        subprocess.run(
            ["apt", "purge", "--yes", "datacenter-gpu-manager-config"],
            check=True
        )
        print("datacenter-gpu-manager and its config have been removed.")
    except subprocess.CalledProcessError as e:
        print("Error removing datacenter-gpu-manager:", e, file=sys.stderr)



def install_latest_dcgm():
    try:
        subprocess.run(
            ["apt", "update"],
            check=True
        )
        subprocess.run(
            [
                "apt-get", "install", "--yes", "--install-recommends",
                "datacenter-gpu-manager-4-cuda12"
            ],
            check=True
        )
        print("Latest datacenter-gpu-manager-4-cuda12 has been installed.")
    except subprocess.CalledProcessError as e:
        print("Error installing datacenter-gpu-manager-4-cuda12:", e, file=sys.stderr)
        sys.exit(1)


def update_nvidia_exporter_path(file_path):

    old_line = "sys.path.append('/usr/local/dcgm/bindings/python3')"
    new_line = "sys.path.append('/usr/share/datacenter-gpu-manager-4/bindings/python3')"

    replaced = False
    for line in fileinput.input(file_path, inplace=True):
        if old_line in line:
            print(line.replace(old_line, new_line), end='')
            replaced = True
        else:
            print(line, end='')
    if replaced:
        print(f"Updated sys.path in {file_path}")
    else:
        print(f"No matching sys.path line found in {file_path}")

if __name__ == "__main__":
    version = get_dcgm_version()
    print(f"Current DCGM version: {version}")
    cuda_version = get_cuda_version()
    print(f"Current CUDA version: {cuda_version}")

    if version.startswith("1:3.") and float(cuda_version) >= 12.8:
        remove_dcgm()
        install_latest_dcgm()
        update_nvidia_exporter_path("/Moneo/src/worker/exporters/nvidia_exporter.py")
    else:
        print("no dcgm update")
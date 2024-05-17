ROCm Container Runtime
======================

rocm-container-runtime is a wrapper for [runc](https://github.com/opencontainers/runc).

If environment variable `AMD_VISIBLE_DEVICES` is set in OCI config,
the runtime will inject necessary fields into OCI config to use AMD GPUs in containers.

The runtime is the same as [ROCm-docker](https://github.com/RadeonOpenCompute/ROCm-docker) on the host, but provides flexibility for AMD GPUs on Kubernetes.

The runtime achieves similar functionality to [nvidia-container-runtime](https://github.com/NVIDIA/nvidia-container-runtime), but is for AMD GPUs on [ROCm Platform](https://rocm.github.io/).


Installation
------------

```sh
git clone https://github.com/abuccts/rocm-container-runtime
cd rocm-container-runtime
# you can edit rocm-container-runtime.conf for configurations
bash install.sh
```

> NOTE: the runtime only works for Debian distributions currently, changes are needed for other Linux distributions.


Docker Engine Setup
-------------------

* Docker daemon configuration file

    Add the following fields into `/etc/docker/daemon.json` and restart Docker service:
    ```json
    {
      "runtimes": {
        "rocm": {
          "path": "/usr/bin/rocm-container-runtime",
          "runtimeArgs": []
        }
      }
    }
    ```

    You can optionally set it to default runtime in `/etc/docker/daemon.json`:
    ```json
    "default-runtime": "rocm"
    ```


Docker Usage
------------

```sh
# use 4 AMD GPUs
docker run --runtime=rocm -e AMD_VISIBLE_DEVICES=0,1,2,3 --security-opt seccomp=unconfined rocm/rocm-terminal rocminfo

# use the 3rd AMD GPU
docker run --runtime=rocm -e AMD_VISIBLE_DEVICES=2 --security-opt seccomp=unconfined rocm/rocm-terminal rocminfo
```

> NOTE: To use AMD GPUs in Docker, please follow [ROCm's document](https://rocm.github.io/ROCmInstall.html#Ubuntu) to install drivers first.

Containerd
-----------
```toml
version = 2
root = "/var/lib/containerd"
state = "/run/containerd"
oom_score = 0

[grpc]
  max_recv_message_size = 16777216
  max_send_message_size = 16777216

[debug]
  level = "info"

[metrics]
  address = ""
  grpc_histogram = false

[plugins]
  [plugins."io.containerd.grpc.v1.cri"]
    sandbox_image = "registry.k8s.io/pause:3.9"
    max_container_log_line_size = -1
    enable_unprivileged_ports = false
    enable_unprivileged_icmp = false
    [plugins."io.containerd.grpc.v1.cri".containerd]
      default_runtime_name = "rocm"
      snapshotter = "overlayfs"
      [plugins."io.containerd.grpc.v1.cri".containerd.runtimes]
        [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.rocm]
          runtime_type = "io.containerd.runc.v2"
          runtime_engine = ""
          runtime_root = ""
          base_runtime_spec = "/etc/containerd/cri-base.json"

          [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.rocm.options]
            systemdCgroup = true
            binaryName = "/usr/bin/rocm-container-runtime"
    [plugins."io.containerd.grpc.v1.cri".registry]
      [plugins."io.containerd.grpc.v1.cri".registry.mirrors]
        [plugins."io.containerd.grpc.v1.cri".registry.mirrors."docker.io"]
          endpoint = ["https://registry-1.docker.io"]
```

runtime usage
-----
```sh
sudo ctr run --runc-binary /usr/bin/rocm-container-runtime --env AMD_VISIBLE_DEVICES=0,1,2,3 --user 0:0 --rm -t docker.io/rocm/rocm-terminal:latest rocm-test rocm-smi
```

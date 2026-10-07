# Maintenance tools

## Build and push maintained images

`build_and_push_images.sh` discovers Kubernetes/common Dockerfiles under
`src/*/build`, excluding `base-image`, `dev-box`, and `internal-storage`.
Progress is stored under `.git/ltp-image-tools`.
The script resolves the repository root from its own location, so it can be
invoked from outside the repository.

The following standalone images are also intentionally excluded:
`cleaning-image`, `kubernetes-dashboard-amd64`, `marketplace-db`,
`postgresql-sdk`, `prometheus`, and `prometheus-pushgateway`.

```bash
tools/build_and_push_images.sh build -c <config-dir>
tools/build_and_push_images.sh push -c <config-dir>
tools/build_and_push_images.sh all -c <config-dir>
tools/build_and_push_images.sh all --status
tools/build_and_push_images.sh all --list
```

Cilium images are pushed through `src/cilium/build/push.sh`; all other images
use `build/pai_build.py`.

## Restart running PAI services

```bash
tools/updatePaiService.py --cluster-name <cluster-name>
```

The updater pulls the cluster configuration into an isolated temporary
directory, stops running services in reverse dependency order, and starts them
in forward order. It also runs `paictl.py` with the repository root as its
working directory, so invocation does not depend on the caller's directory.

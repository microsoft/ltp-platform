# Maintenance tools

Image publication and service updates are separate: building/pushing does not
restart services, and the service updater does not build or push images.
Run these examples from the repository root.

## Build and push maintained images

Requires Bash, Git, Docker, and the dependencies of `build/pai_build.py`.
`<config-dir>` must contain `services-configuration.yaml`.

```bash
# Build only, push only, or build everything before pushing.
tools/build_and_push_images.sh build -c <config-dir>
tools/build_and_push_images.sh push -c <config-dir>
tools/build_and_push_images.sh all -c <config-dir>

# Build and push without Cilium.
tools/build_and_push_images.sh all -c <config-dir> --skip-cilium

# Preview tasks or view progress; no configuration directory needed.
tools/build_and_push_images.sh all --list --skip-cilium
tools/build_and_push_images.sh all --status --skip-cilium
```

The script discovers Kubernetes/common Dockerfiles under `src/*/build`.
It excludes `base-image`, `dev-box`, `internal-storage`, and these standalone
images: `cleaning-image`, `kubernetes-dashboard-amd64`, `marketplace-db`,
`postgresql-sdk`, `prometheus`, and `prometheus-pushgateway`.

| Option | Usage |
| --- | --- |
| `-c, --config DIR` | Configuration directory; required for build/push |
| `--list` | List ordered image tasks without executing |
| `--status` | Show saved progress without executing |
| `--reset` | Clear progress for the selected action; `all` resets both phases |
| `--from N` | Start at task N (1-based), rerunning from there; applies to both phases for `all` |
| `--use-cache` | Enable Docker build cache; disabled by default |
| `--skip-cilium` | Exclude Cilium from execution, task lists and status |
| `--cilium-date YYYYMMDD` | Override the Cilium publication date |

On failure, fix the error and rerun the same command to resume. Completed tasks
are recorded in `.git/ltp-image-tools` (or the repository's Git directory).
Source, configuration and local-image changes do not invalidate build or
non-Cilium push progress: use `--reset` to repeat all selected tasks, or
`--from N` to repeat from a task in the current filtered `--list`.
Cilium pushes detect changed local image IDs; `CHECK` status means that this
comparison will happen when pushing.

Do not run overlapping build/push commands or edit publication inputs during
a push; these scripts do not lock shared images, progress or manifests.

### Push Cilium images

Requires Python 3 with PyYAML, Azure CLI with ACR login permission, and all three
local images: `cilium-agent:latest`, `cilium-operator:latest`,
`cilium-envoy:latest`.

```bash
# Publish using the date already in contrib/aks/k8s-deploy/cilium.yaml.
src/cilium/build/push.sh -c <config-dir>

# Publish with an explicit date.
src/cilium/build/push.sh -c <config-dir> -d 20261015
tools/build_and_push_images.sh push -c <config-dir> --cilium-date 20261015
```

The ACR domain comes from the configuration; the image namespace defaults to
`cilium`. For standalone pushes, use `-n <namespace>` to override it or
`-n @config` to use the configured namespace.

All three destination tags use `<version>-<YYYYMMDD>`. Versions come from the
Dockerfiles, with a trailing 40-character lowercase hexadecimal Git hash
removed for all three images. Agent and Operator versions must match before
hash removal; Envoy uses its own version. Without an explicit date, the helper
uses the consistent date in the manifest, not today's date.
**Reusing a version and date replaces the existing tag**, including when the
source commit changes.

After pushing, the helper asks whether to update the manifest if references
have changed. Answer `y`/`yes` to update it; `n`/`no` or an empty answer leaves
it unchanged. No prompt appears when references already match. If confirmation
input is unavailable or invalid, the command fails even though images have
already been pushed. Partial pushes are not rolled back.
Review any manifest changes and commit them separately; the script does not
commit or deploy automatically.

## Restart running PAI services

Requires Linux procfs, Python 3 with PyYAML, Git, kubectl, and paictl's
dependencies. Select the intended Kubernetes context first. `<cluster-name>`
must match the ID returned by `./paictl.py config get-id`.

```bash
# Preview before executing.
tools/updatePaiService.py --cluster-name <cluster-name> --plan
tools/updatePaiService.py --cluster-name <cluster-name>

# Include optional stages, or change the per-command timeout.
tools/updatePaiService.py --cluster-name <cluster-name> \
  --with-cilium --with-cluster-configuration --with-device-plugin
tools/updatePaiService.py --cluster-name <cluster-name> --timeout 600
```

The updater stops supported deployed services in reverse dependency order and
starts them in forward order, using `paictl.py`. Ordinary services are selected
in `default`; explicit `kube-system` targets remain there. The user's kubeconfig
is not changed. Internal storage is stop-only.

| Option | Usage |
| --- | --- |
| `--cluster-name NAME` | Required cluster ID; also identifies saved progress |
| `--plan` | Preview the new or resumed plan; contacts the cluster but runs no lifecycle commands |
| `--with-cilium` | Include whole-manifest Cilium delete/apply |
| `--with-cluster-configuration` | Include cluster-configuration stop/start |
| `--with-device-plugin` | Include device-plugin delete/start |
| `--timeout SECONDS` | Per-command timeout; positive number, default 300 |

**`--with-cilium` is disruptive:** it deletes the entire
`contrib/aks/k8s-deploy/cilium.yaml` manifest, including its Namespace, Secrets
and RBAC, before applying it again. There is no automatic rollback.

On failure, fix the cause and rerun with the same cluster name to resume the
saved plan. Completed commands are skipped; omitted optional flags inherit
the unfinished plan. After a completed run, another invocation starts a new
plan. Progress is stored under the common Git directory's `ltp-service-update/`;
do not delete it to bypass recovery errors. A still-running previous operation
or a destructive delete with an unknown outcome requires recovery before retry.

Success means lifecycle commands exited with zero; the updater does not check
Pod readiness or application health. Check the deployment after the run.

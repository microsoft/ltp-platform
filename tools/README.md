# Maintenance tools

These tools separate image publication from service updates. Building/pushing
does not restart services, and the service updater does not build or push images.
Run the examples from the repository root, or use absolute script paths.

## Build and push maintained images

`build_and_push_images.sh` discovers Kubernetes/common Dockerfiles under
`src/*/build`, excluding `base-image`, `dev-box`, and `internal-storage`.
Tasks are sorted by Dockerfile path. Progress is stored under
`$(git rev-parse --git-dir)/ltp-image-tools`, normally `.git/ltp-image-tools`.
The script resolves the repository root from its own location, so it can be
invoked from outside the repository.

Building/pushing requires Bash, Git, Docker, and the existing
dependencies of `build/pai_build.py`. Supply a configuration directory containing
`services-configuration.yaml`. Cilium publishing additionally requires Python 3
with PyYAML and Azure CLI with permission to log in to the target ACR.
`--list` and `--status` do not require a configuration directory.

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

`all` finishes the build phase before starting the push phase. Both phases stop
on the first failure; fix the error and rerun the same command to resume.
Builds disable the Docker cache by default.

Build/push workflows and the standalone Cilium publisher do not acquire locks.
Users are responsible for avoiding overlapping operations on shared Docker
tags, registry destinations, progress files and the Cilium manifest. Concurrent
invocations are not rejected and can overwrite progress or each other's work;
the scripts do not guarantee concurrency safety.

| Option | Behavior |
| --- | --- |
| `-c, --config DIR` | Configuration directory; required for build/push execution |
| `--list` | Show the ordered image tasks without building or pushing |
| `--status` | Show saved progress for the selected action without building or pushing |
| `--reset` | Clear progress for the selected action before executing it; `all` resets both phases |
| `--from N` | Start at task N (1-based), skipping earlier tasks and ignoring completion records from N onward; applies to both phases for `all` |
| `--use-cache` | Allow Docker build cache |
| `--skip-cilium` | Exclude Cilium from build, push, list and status |
| `--cilium-date YYYYMMDD` | Override the date used for Cilium publication |

Builds and non-Cilium pushes use saved `service/image` completion markers.
They do not automatically detect source, configuration or local-image changes.
Use `--reset` or `--from N` when intentionally repeating recorded work.
Use the same filtering options with `--list` to find the current task numbers.
`--from N` must be within that filtered task list. Out-of-range values fail
before resetting progress or running image commands.

Cilium images are pushed through `src/cilium/build/push.sh`; all other images
use `build/pai_build.py`.

### Cilium publishing

The helper requires `cilium-agent:latest`, `cilium-operator:latest` and
`cilium-envoy:latest`. It validates all three before any login/tag/push and
publishes their recorded IDs, even when called from one Cilium batch task.
This is a Cilium-group preflight, not a preflight of all maintained images
before the batch's first push.

Without a date argument it reuses the consistent date in
`contrib/aks/k8s-deploy/cilium.yaml`; an explicit date overrides it.
Multi-document manifests are supported; YAML aliases within a document are
rejected to keep image-reference updates unambiguous.
It never automatically selects today's date. Missing or conflicting manifest
dates fail when no explicit date is supplied. Image versions come from the
Cilium Dockerfiles; Agent and Operator must have the same `CILIUM_VERSION`,
otherwise planning/publication fails before inspecting or publishing images.
Envoy keeps its separate version. Destination tags are `<version>-<YYYYMMDD>`.
After all pushes succeed, if the fixed manifest needs changes, the helper shows
the old/new image references and asks whether to update it. Only `y` or `yes`
(case-insensitive) authorizes replacement, including repeated
Agent/init-container references. It requests review/check-in after updating.
No prompt is needed when the references already match.

Choosing `n`, `no`, or an empty answer leaves the manifest unchanged, records
publication success with `manifest_status: skipped`, and lets the batch continue.
The cluster will still use the manifest's old references until you update them.
EOF/no available input or an invalid answer leaves it unchanged, reports an
error and stops the batch without recording new Cilium completion, even though
all three images have already been pushed.

Confirmation authorizes a write; it is not a lock or a compare-and-swap.
Do not edit the manifest or change publication inputs concurrently. Detected
input changes, including changes while awaiting confirmation, abort writeback,
but the check and atomic replacement are separate operations and do not
guarantee protection against every external edit.

The registry domain comes from the supplied configuration. The image namespace
defaults to `cilium`, including batch invocations. Standalone calls support
`-n <namespace>` or `-n @config` to use the configured registry namespace.

```bash
src/cilium/build/push.sh -c <config-dir>
src/cilium/build/push.sh -c <config-dir> -d 20261014
tools/build_and_push_images.sh all -c <config-dir> --skip-cilium
tools/build_and_push_images.sh push -c <config-dir> --cilium-date 20261014
```

For a new publication date, pass `--cilium-date` explicitly. After a successful
push, inspect `git diff -- contrib/aks/k8s-deploy/cilium.yaml` and check in the
manifest change as appropriate. Neither script commits it automatically.
Reusing a date can overwrite existing registry tags; the date is not an
immutable image identity.

Cilium batch push completion uses destination references and image IDs, not old
name-only records. A group is skipped only when its saved completion matches the
current destinations/IDs and either the manifest already references those
targets or its update was explicitly declined for that publication.
To request confirmation again after declining, run the standalone helper or
use batch `--from N` at a Cilium task; this republishes the image group.
A same-date rebuild with different IDs is pushed again. Build progress still
controls whether builds run: `--reset` resets the selected phases, not just
Cilium. With `--skip-cilium`, historical Cilium progress is preserved even when
resetting the other tasks.
Cilium push status displays `CHECK`; a push invocation resolves the current
IDs before deciding whether it can skip the group. `CHECK` does not itself mean
success or failure.

Partial push, conflicting inputs, or manifest/result persistence failure
returns nonzero and never records new group completion. A failed image push
leaves the manifest unchanged; if only the later manifest/result write fails,
the images may already be published. Publication is not a registry transaction:
already-pushed tags are not rolled back.
For the batch interface, the helper exposes `--plan-json` (read-only preflight),
`--publish-plan PATH` (execute a saved plan) and `--result-file PATH` (write the
success result).

## Restart running PAI services

```bash
tools/updatePaiService.py --cluster-name <cluster-name>
tools/updatePaiService.py --cluster-name <cluster-name> --plan
tools/updatePaiService.py --cluster-name <cluster-name> \
  --with-cilium --with-cluster-configuration --with-device-plugin
tools/updatePaiService.py --cluster-name <cluster-name> --timeout 600
```

The updater selects deployed services, stops them in reverse dependency order,
and starts them in forward order. It runs `paictl.py` from the repository root;
paictl owns configuration loading, validation and template rendering.

Linux procfs, Python 3 with PyYAML, Git, kubectl, and paictl's existing
dependencies are required. Select the intended Kubernetes context before
running the updater. `--cluster-name` must match the ID returned by
`paictl config get-id`.

| Option | Behavior |
| --- | --- |
| `--cluster-name NAME` | Required cluster ID and progress identity |
| `--plan` | Show the new or resumed command plan without running lifecycle commands or rewriting the journal; still contacts the cluster |
| `--with-cilium` | Opt into whole-manifest Cilium delete/apply |
| `--with-cluster-configuration` | Opt into cluster-configuration stop/start |
| `--with-device-plugin` | Opt into device-plugin delete/start |
| `--timeout SECONDS` | Positive command timeout; defaults to 300 seconds |

### Resumable updater

**Command orchestration only:** exit zero completes a lifecycle step. Nonzero
exit, timeout or interruption stops the run. The updater does not interpret
service configuration, render manifests, compare resources or check Pod
readiness, rollout, RBAC, probes or application health. Successful commands
are not a guarantee of a healthy deployment.

Every invocation first checks `paictl config get-id` once. Discovery uses all
namespaces but accepts only known deployed identities. The original service
order, selected stages, command statuses/results and execution ownership are
saved under the common Git directory's `ltp-service-update/`.
Errors **fail fast**. Rerunning the same command resumes unfinished work even
when stopped services have disappeared from discovery. Omitted optional flags
inherit an unfinished plan; explicit stage conflicts fail without discarding
it. Configuration, image and source repairs do not invalidate progress.
After a completed run, another invocation creates a new plan rather than
skipping the entire update.

Failed preflight commands report their exit status and captured stderr, falling
back to stdout when stderr is empty. Raw kubeconfig stdout is never included
in failure messages because it can contain credentials.

Lifecycle commands use a private kubeconfig whose selected context is normalized
to `default`, matching unqualified paictl scripts; the user's kubeconfig is not
changed and explicit `kube-system` targets remain explicit. Discovery accepts
only explicit supported controller identities/managed VC naming, not generic
normalized-name fallbacks. Ordinary service selection accepts mapped controllers
in `default`; unsupported resources are reported as `[UNMAPPED]`. Controller
discovery is only used when creating a new plan, not when resuming it.

The optional order is Cilium delete/wait/apply, cluster-configuration stop/start,
device-plugin delete/start, then ordinary reverse stop/forward start.
**Cilium deletes the entire fixed manifest**, including its Namespace, Secrets
and RBAC; it is deliberately disruptive and opt-in. No alternate manifest,
automatic rollback, force deletion, image publication or automatic commit is
performed. Internal storage remains stop-only.

Commands are bounded by `--timeout` (default 300 seconds). An operation
supervisor prevents overlapping retries and records an atomic command-exit
receipt if the updater dies before saving progress. Receipts are consumed into
the journal and removed after durable acknowledgement. Recorded successful
commands are skipped without resource checks.

Execution ownership covers every process group in the supervisor's private
session, including GNU `parallel` jobs. Live descendants block retry even after
the supervisor/original group dies. Cleanup rechecks each PID's start time and
session before signaling it, and incomplete cleanup cannot acknowledge success.
Children that deliberately create another session are outside this boundary.

If an old command ended without any recorded outcome, ordinary commands may
be retried; exactly-once execution is not guaranteed. An unknown destructive
delete result requires manual recovery instead of an automatic repeat.
Live/uncertain execution ownership also blocks retry. Do not delete the
journal: it retains services still needing their startup command.
The failure summary lists each step and services still needing startup.
Repair a failed command's cause, then rerun with the same cluster ID; already
successful commands, including destructive deletes, are not repeated.

Schema-1 journals from the earlier implementation retain their original plan,
statuses and execution identity when upgraded to schema 2. Obsolete config
guards, expected inventories and resource snapshots are dropped, not enforced.
Legacy uncertain deletes without command results require manual recovery too.

Concurrent external configuration changes are not coordinated;
the next paictl invocation reads its configuration normally.

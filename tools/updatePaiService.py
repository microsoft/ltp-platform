#!/usr/bin/env python3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import tempfile
import time
import uuid

import yaml


SERVICE_ORDER = (
    "node-exporter", "job-exporter", "log-manager", "copilot-chat",
    "dashboard-data-backup", "prometheus", "prometheus-pushgateway", "grafana",
    "alert-manager", "watchdog", "internal-storage", "postgresql",
    "frameworkcontroller", "database-controller", "fluentd", "hivedscheduler",
    "cluster-local-storage-worker", "cluster-local-storage", "ssh-proxy",
    "utilization-reporter", "rest-server", "model-proxy", "webportal", "pylon",
)
STOP_ONLY_SERVICES = {"internal-storage"}
OPTIONAL_STAGES = ("cilium", "cluster-configuration", "device-plugin")
TIMEOUT = 300
SCHEMA = 2
CONTROLLERS = {
    ("DaemonSet", "node-exporter"): "node-exporter",
    ("DaemonSet", "job-exporter"): "job-exporter",
    ("DaemonSet", "log-manager-ds"): "log-manager",
    ("Deployment", "copilot-chat"): "copilot-chat",
    ("Deployment", "dashboard-data-backup"): "dashboard-data-backup",
    ("Deployment", "prometheus-deployment"): "prometheus",
    ("Deployment", "prometheus-pushgateway"): "prometheus-pushgateway",
    ("Deployment", "grafana"): "grafana",
    ("Deployment", "alertmanager"): "alert-manager",
    ("Deployment", "redis"): "alert-manager",
    ("Deployment", "watchdog"): "watchdog",
    ("DaemonSet", "internal-storage-create-ds"): "internal-storage",
    ("DaemonSet", "postgresql-ds"): "postgresql",
    ("StatefulSet", "frameworkcontroller-sts"): "frameworkcontroller",
    ("StatefulSet", "database-controller-sts"): "database-controller",
    ("DaemonSet", "fluentd-ds"): "fluentd",
    ("StatefulSet", "hivedscheduler-hs"): "hivedscheduler",
    ("DaemonSet", "cluster-local-storage-worker-ds"): "cluster-local-storage-worker",
    ("Deployment", "ssh-proxy-deployment"): "ssh-proxy",
    ("Deployment", "utilization-reporter-deployment"): "utilization-reporter",
    ("DaemonSet", "rest-server-ds"): "rest-server",
    ("DaemonSet", "model-proxy-ds"): "model-proxy",
    ("DaemonSet", "webportal-ds"): "webportal",
    ("DaemonSet", "pylon-ds"): "pylon",
}


class CommandError(RuntimeError):
    pass


def atomic_json(path, value):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w") as output:
            output.write(json.dumps(value, sort_keys=True, indent=2) + "\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def locked(path):
    with open(path, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"Another operation holds {Path(path).name}; no mutation allowed") from error
        yield


def process_identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except (FileNotFoundError, ProcessLookupError):
        return None
    return {"pid": int(pid), "state": fields[0], "pgid": int(fields[2]),
            "session": int(fields[3]), "start": fields[19]}


def host_identity():
    return {"host": hashlib.sha256(Path("/etc/machine-id").read_bytes()).hexdigest(),
            "boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}


def session_members(identity):
    members = []
    for path in Path("/proc").iterdir():
        if path.name.isdigit():
            item = process_identity(int(path.name))
            if (item and item["session"] == identity["session"]
                    and item["state"] not in ("Z", "X")):
                members.append(item)
    return members


def terminate_members(identity):
    for sig, grace in ((signal.SIGTERM, 3), (signal.SIGKILL, 3)):
        for item in session_members(identity):
            current = process_identity(item["pid"])
            if (item["pid"] != os.getpid() and current
                    and current["start"] == item["start"]
                    and current["session"] == identity["session"]):
                try:
                    os.kill(item["pid"], sig)
                except ProcessLookupError:
                    pass
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            if not [item for item in session_members(identity) if item["pid"] != os.getpid()]:
                return
            time.sleep(0.1)
    raise RuntimeError("Command descendants remain alive; manual recovery required")


def supervise(lock_path, identity_fd):
    identity = dict(process_identity(os.getpid()), **host_identity())

    def interrupted(signum, frame):
        raise InterruptedError("Operation interrupted")

    with locked(lock_path):
        with os.fdopen(identity_fd, "w") as pipe:
            pipe.write(json.dumps(identity) + "\n")
            pipe.flush()
        if not select.select([sys.stdin], [], [], 15)[0]:
            raise RuntimeError("Execution handshake timed out; no command launched")
        line = sys.stdin.readline()
        if not line:
            return 1
        request = json.loads(line)
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        command, exit_code, failure = None, None, None
        try:
            command = subprocess.Popen(request["command"], stdin=subprocess.PIPE,
                                       text=True, cwd=request["cwd"])
            command.communicate(request["input"], timeout=request["timeout"])
            exit_code = command.returncode
            deadline = time.monotonic() + 3
            while [item for item in session_members(identity) if item["pid"] != os.getpid()]:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Command exited with surviving descendants")
                time.sleep(0.1)
            return exit_code
        except (RuntimeError, OSError, subprocess.TimeoutExpired, InterruptedError) as error:
            failure = type(error).__name__
            raise
        finally:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            terminate_members(identity)
            if command is not None:
                command.wait(timeout=3)
            # A receipt survives the updater dying before it can record the exit.
            if request.get("result_file"):
                atomic_json(request["result_file"], {
                    "execution": identity, "exit_code": exit_code if failure is None else None,
                    "error": failure,
                })


def ensure_ended(execution, operation_lock):
    with locked(operation_lock):
        if not execution:
            return
        current_host = host_identity()
        if current_host["host"] != execution["host"]:
            raise RuntimeError("Previous execution belongs to another host; manual recovery required")
        if current_host["boot"] != execution["boot"]:
            return
        leader = process_identity(execution["pid"])
        if session_members(execution):
            reused = leader and leader["start"] != execution["start"]
            reason = "PID reused; execution ownership uncertain" if reused else "previous command session still alive"
            raise RuntimeError(f"{reason}; refusing concurrent retry (PID {execution['pid']})")


def run_command(command, timeout=TIMEOUT, cwd=None):
    try:
        return subprocess.run(command, text=True, capture_output=True, check=True, timeout=timeout, cwd=cwd)
    except subprocess.CalledProcessError as error:
        details = (error.stderr or "").strip()
        # A failed raw kubeconfig export may already contain credentials on stdout.
        if not details and not (command[:3] == ["kubectl", "config", "view"] and "--raw" in command):
            details = (error.stdout or "").strip()
        message = f"{command[0]} {command[1:3]} failed (exit {error.returncode})"
        if details:
            message += "\n" + details
        raise CommandError(message) from error


def lifecycle_input(command, cluster_name):
    if Path(command[0]).name != "paictl.py":
        return None
    confirmation = "Y\n" if command[1:3] == ["service", "delete"] else ""
    return confirmation + cluster_name + "\n"


def execution_kubeconfig(content):
    config = yaml.safe_load(content)
    if (not isinstance(config, dict) or not isinstance(config.get("contexts"), list)
            or not isinstance(config.get("current-context"), str)
            or any(not isinstance(item, dict) for item in config["contexts"])):
        raise ValueError("Invalid kubeconfig: contexts are missing")
    selected = [item for item in config["contexts"] if item.get("name") == config.get("current-context")]
    if len(selected) != 1 or not isinstance(selected[0].get("context"), dict):
        raise ValueError("Invalid kubeconfig: selected context is missing or ambiguous")
    selected[0]["context"]["namespace"] = "default"
    return yaml.safe_dump(config, sort_keys=False)


class Updater:
    def __init__(self, root, args, state_dir):
        self.root, self.args, self.directory = root, args, state_dir
        self.path = state_dir / (hashlib.sha256(args.cluster_name.encode()).hexdigest() + ".json")
        self.operation_lock = self.path.with_suffix(".operation.lock")
        self.state = None
        self.manifest = root / "contrib/aks/k8s-deploy/cilium.yaml"
        self.kubeconfig = None

    def save(self):
        self.state["updated_at"] = time.time()
        atomic_json(self.path, self.state)

    def gate(self):
        result = run_command([str(self.root / "paictl.py"), "config", "get-id",
                              "-c", str(self.kubeconfig)], cwd=self.root, timeout=self.args.timeout)
        ids = {value.strip() for value in re.findall(
            r"Cluster-id is: ([^\r\n]+)", result.stdout + "\n" + result.stderr)}
        if ids != {self.args.cluster_name}:
            raise RuntimeError(f"PAI cluster ID does not match {self.args.cluster_name!r}; no mutation allowed")
        print(f"[CLUSTER] {self.args.cluster_name}: ID check passed")

    def selections(self):
        existing = None
        if self.path.exists():
            existing = json.loads(self.path.read_text())
            if (not isinstance(existing, dict) or existing.get("schema_version") not in (1, SCHEMA)
                    or existing.get("cluster_name") != self.args.cluster_name
                    or not isinstance(existing.get("run_id"), str) or not existing["run_id"]):
                raise RuntimeError("Invalid journal; refusing to abandon unfinished services")
            if (existing.get("phase") not in ("planned", "stopping", "starting", "complete", *OPTIONAL_STAGES)
                    or not isinstance(existing.get("selected"), dict)
                    or any(type(existing["selected"].get(stage)) is not bool for stage in OPTIONAL_STAGES)
                    or not isinstance(existing.get("service_order"), list)
                    or any(name not in SERVICE_ORDER for name in existing["service_order"])
                    or len(set(existing["service_order"])) != len(existing["service_order"])
                    or not isinstance(existing.get("steps"), list)):
                raise RuntimeError("Invalid journal structure; manual recovery required")
            planned = self.make_steps(existing["service_order"], existing["selected"])
            if (len(planned) != len(existing["steps"])
                    or any(not isinstance(step, dict)
                           or (step.get("service"), step.get("action")) != (expected["service"], expected["action"])
                           or step.get("state") not in ("pending", "running", "failed", "succeeded")
                           for step, expected in zip(existing["steps"], planned))):
                raise RuntimeError("Invalid journal steps; refusing incomplete recovery")
            if existing["phase"] == "complete" and any(step["state"] != "succeeded" for step in existing["steps"]):
                raise RuntimeError("Complete journal contains unfinished steps; refusing to abandon them")
            for step in existing["steps"]:
                execution = step.get("execution")
                if execution is not None and (
                        not isinstance(execution, dict)
                        or any(not isinstance(execution.get(name), str) for name in ("host", "boot", "start"))
                        or type(execution.get("pid")) is not int or execution["pid"] <= 0
                        or execution.get("pgid") != execution["pid"] or execution.get("session") != execution["pid"]):
                    raise RuntimeError("Invalid execution ownership; manual recovery required")
                if "attempt" in step and (
                        not isinstance(step["attempt"], str) or not re.fullmatch(r"[0-9a-f]{32}", step["attempt"])):
                    raise RuntimeError("Invalid command attempt in journal")
                if "exit_code" in step and type(step["exit_code"]) is not int:
                    raise RuntimeError("Invalid command exit code in journal")
                if "command_error" in step and (
                        not isinstance(step["command_error"], str) or not step["command_error"]):
                    raise RuntimeError("Invalid command failure in journal")
                if ("exit_code" in step and "command_error" in step
                        or step["state"] == "succeeded" and step.get("exit_code", 0) != 0):
                    raise RuntimeError("Conflicting command result in journal")
            if existing["phase"] == "complete":
                for step in existing["steps"]:
                    ensure_ended(step.get("execution"), self.operation_lock)
                existing = None
        choices = {}
        for stage in OPTIONAL_STAGES:
            supplied = getattr(self.args, stage.replace("-", "_"))
            saved = existing["selected"][stage] if existing else False
            if existing and supplied is not None and supplied != saved:
                raise RuntimeError(f"Explicit {stage} option conflicts with unfinished plan")
            choices[stage] = saved if supplied is None else supplied
        return existing, choices

    def discover(self):
        result = run_command(["kubectl", "get", "deployment,statefulset,daemonset", "-A", "-o", "json"],
                             cwd=self.root, timeout=self.args.timeout)
        services = set()
        for resource in json.loads(result.stdout)["items"]:
            meta, kind = resource["metadata"], resource["kind"]
            name, namespace = meta["name"], meta.get("namespace", "default")
            service = CONTROLLERS.get((kind, name)) if namespace == "default" else None
            if namespace == "default" and kind == "StatefulSet":
                for prefix, owner in (("cluster-local-storage-sts-", "cluster-local-storage"),
                                      ("hivedscheduler-ds-", "hivedscheduler")):
                    if (name.startswith(prefix) and len(name) > len(prefix)
                            and resource.get("spec", {}).get("selector", {}).get("matchLabels", {}).get("app") == name):
                        service = owner
            if service:
                services.add(service)
            else:
                print(f"[UNMAPPED] {namespace}/{kind}/{name}")
        return [name for name in SERVICE_ORDER if name in services]

    def prepare(self, existing, selected):
        ensure_ended(None, self.operation_lock)
        if existing:
            for step in existing["steps"]:
                ensure_ended(step.get("execution"), self.operation_lock)
            self.state = {name: existing[name] for name in
                          ("run_id", "cluster_name", "selected", "service_order", "phase")}
            self.state["schema_version"] = SCHEMA
            self.state["steps"] = [
                {name: step[name] for name in
                 ("service", "action", "state", "execution", "attempt", "exit_code", "command_error", "error")
                 if name in step} for step in existing["steps"]]
            print(f"[RESUME] {existing['run_id']}, phase {existing['phase']}")
            return
        services = self.discover()
        self.state = {"schema_version": SCHEMA, "run_id": str(uuid.uuid4()),
                      "cluster_name": self.args.cluster_name, "selected": selected,
                      "service_order": services, "phase": "planned",
                      "steps": self.make_steps(services, selected)}

    @staticmethod
    def make_steps(services, selected):
        steps = []
        for stage in OPTIONAL_STAGES:
            if selected[stage]:
                steps += [{"service": stage, "action": action, "state": "pending"}
                          for action in (("delete", "apply") if stage == "cilium" else
                                         ("delete", "start") if stage == "device-plugin" else ("stop", "start"))]
        steps += [{"service": service, "action": "stop", "state": "pending"}
                  for service in reversed(services)]
        steps += [{"service": service, "action": "start", "state": "pending"}
                  for service in services if service not in STOP_ONLY_SERVICES]
        return steps

    def result_path(self, step):
        return self.path.with_name(self.path.stem + "." + step["attempt"] + ".result.json")

    def collect_result(self, step):
        if "attempt" not in step:
            return
        path = self.result_path(step)
        try:
            result = json.loads(path.read_text())
        except FileNotFoundError:
            return
        if (not isinstance(result, dict) or result.get("execution") != step.get("execution")
                or not ((type(result.get("exit_code")) is int and result.get("error") is None)
                        or (result.get("exit_code") is None and isinstance(result.get("error"), str)
                            and result["error"]))):
            raise RuntimeError("Invalid command receipt; manual recovery required")
        if result["exit_code"] is not None:
            step["exit_code"] = result["exit_code"]
        else:
            step["command_error"] = result["error"]
        self.save()
        path.unlink()

    def execute(self, step, command):
        ensure_ended(step.get("execution"), self.operation_lock)
        for field in ("execution", "exit_code", "command_error", "error"):
            step.pop(field, None)
        step.update(state="running", attempt=uuid.uuid4().hex)
        self.save()
        read_fd, write_fd = os.pipe()
        supervisor = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--supervise",
             str(self.operation_lock), str(write_fd)], pass_fds=(write_fd,),
            stdin=subprocess.PIPE, text=True, start_new_session=True, cwd=self.root)
        os.close(write_fd)
        try:
            with os.fdopen(read_fd) as pipe:
                if not select.select([pipe], [], [], 15)[0]:
                    raise RuntimeError("Supervisor identity handshake timed out")
                line = pipe.readline()
            if not line:
                raise RuntimeError("Supervisor could not acquire execution ownership")
            step["execution"] = json.loads(line)
            self.save()
            request = {"command": command, "cwd": str(self.root),
                       "input": lifecycle_input(command, self.args.cluster_name),
                       "timeout": self.args.timeout, "result_file": str(self.result_path(step))}
            supervisor.communicate(json.dumps(request) + "\n", timeout=self.args.timeout + 15)
        finally:
            if supervisor.poll() is None:
                supervisor.terminate()
                try:
                    supervisor.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    supervisor.kill()
                    supervisor.wait()
            ensure_ended(step.get("execution"), self.operation_lock)
            self.collect_result(step)
        if "command_error" in step:
            raise RuntimeError(f"{step['service']} {step['action']} failed ({step['command_error']})")
        if "exit_code" not in step:
            raise RuntimeError(f"{step['service']} {step['action']} has no recorded command result "
                               f"(supervisor exit {supervisor.returncode})")
        if step["exit_code"] != 0:
            raise RuntimeError(f"{step['service']} {step['action']} failed "
                               f"(exit {step['exit_code']})")

    def perform(self, step, manifest_copy):
        ensure_ended(step.get("execution"), self.operation_lock)
        if step["state"] == "succeeded":
            return
        self.collect_result(step)
        if step.get("exit_code") == 0:
            step["state"] = "succeeded"
            step.pop("error", None)
            self.save()
            return
        service, action = step["service"], step["action"]
        if (action == "delete" and step.get("execution") and "exit_code" not in step
                and "command_error" not in step):
            raise RuntimeError(f"Unknown outcome of {service} delete; manual recovery required. "
                               "No destructive retry performed; do not delete the journal.")
        print(f"[{action.upper()}] {service}")
        if service == "cilium":
            if not manifest_copy.exists():
                manifest_copy.write_bytes(self.manifest.read_bytes())
                manifest_copy.chmod(0o600)
            command = ["kubectl", action, "-f", str(manifest_copy)]
            if action == "delete":
                command += ["--ignore-not-found", "--wait=true", f"--timeout={self.args.timeout}s"]
        else:
            command = [str(self.root / "paictl.py"), "service", action,
                       "-n", service, "-c", str(self.kubeconfig)]
        self.execute(step, command)
        step["state"] = "succeeded"
        self.save()

    def summary(self):
        if self.state and isinstance(self.state.get("steps"), list):
            for step in self.state["steps"]:
                print(f"[{step['state'].upper()}] {step['service']} {step['action']}")
            pending = [step["service"] for step in self.state["steps"]
                       if step["action"] in ("start", "apply") and step["state"] != "succeeded"]
            if pending:
                print("Still needing startup commands: " + ", ".join(pending))
                print("Rerun the same command to resume; do not delete the journal.")

    def run(self):
        existing, selected = self.selections()
        with tempfile.TemporaryDirectory(prefix="pai-update-") as temporary:
            directory = Path(temporary)
            self.kubeconfig = directory / "kubeconfig"
            content = run_command(["kubectl", "config", "view", "--minify", "--flatten", "--raw"],
                                  cwd=self.root, timeout=self.args.timeout).stdout
            self.kubeconfig.write_text(execution_kubeconfig(content))
            self.kubeconfig.chmod(0o600)
            original_kubeconfig = os.environ.get("KUBECONFIG")
            os.environ["KUBECONFIG"] = str(self.kubeconfig)
            try:
                self.gate()
                self.prepare(existing, selected)
                if self.args.plan:
                    print(json.dumps({"cluster_name": self.args.cluster_name, "selected": selected,
                                      "service_order": self.state["service_order"],
                                      "phase": self.state["phase"],
                                      "steps": [{k: step[k] for k in ("service", "action", "state")}
                                                for step in self.state["steps"]]}, indent=2))
                    return
                manifest_copy = directory / "cilium.yaml"
                self.save()
                for step in self.state["steps"]:
                    if step["state"] != "succeeded":
                        self.state["phase"] = (step["service"] if step["service"] in OPTIONAL_STAGES else
                                               "stopping" if step["action"] == "stop" else "starting")
                        self.save()
                    try:
                        self.perform(step, manifest_copy)
                    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
                        step["state"] = "failed"
                        step["error"] = f"{type(error).__name__}: operation failed; see console"
                        self.save()
                        raise
                self.state["phase"] = "complete"
                self.save()
                print("All planned service commands completed successfully.")
            finally:
                if original_kubeconfig is None:
                    os.environ.pop("KUBECONFIG", None)
                else:
                    os.environ["KUBECONFIG"] = original_kubeconfig


def parse_args():
    parser = argparse.ArgumentParser(description="Run PAI service commands with durable progress.")
    parser.add_argument("--cluster-name", required=True)
    for stage in OPTIONAL_STAGES:
        parser.add_argument("--with-" + stage, dest=stage.replace("-", "_"),
                            action="store_true", default=None)
    parser.add_argument("--plan", action="store_true", help="Show the new or resumed plan without mutation")
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help="Command timeout in seconds")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    return args


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--supervise":
        try:
            return supervise(sys.argv[2], int(sys.argv[3]))
        except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired, InterruptedError) as error:
            print(f"[SUPERVISOR ERROR] {error}", file=sys.stderr)
            return 1
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    updater = None
    try:
        git_dir = run_command(["git", "rev-parse", "--git-common-dir"], cwd=root).stdout.strip()
        directory = (root / git_dir).resolve() / "ltp-service-update"
        directory.mkdir(parents=True, exist_ok=True)
        updater = Updater(root, args, directory)

        def interrupted(signum, frame):
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, interrupted)
        with locked(updater.path.with_suffix(".lock")):
            updater.run()
        return 0
    except (RuntimeError, OSError, ValueError, KeyError, TypeError, yaml.YAMLError,
            subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        print(f"[ERROR] {error or 'Interrupted; progress preserved'}", file=sys.stderr)
        if updater:
            updater.summary()
        return 1


if __name__ == "__main__":
    sys.exit(main())

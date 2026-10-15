#!/bin/bash
# Push the complete Cilium image group and offer to update its fixed manifest.
# Python uses the existing PyYAML dependency to preserve YAML source formatting.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Preserve caller input separately from Python's source on stdin.
exec python3 - "$SCRIPT_DIR" "$@" 3<&0 <<'PY'
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid

import yaml

BUILD = Path(sys.argv[1])
ROOT = BUILD.parents[2]
MANIFEST = ROOT / "contrib/aks/k8s-deploy/cilium.yaml"
ROLES = {"agent": "cilium", "operator": "operator-generic", "envoy": "cilium-envoy"}


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def atomic_write(path, text, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w") as output:
            os.fchmod(output.fileno(), mode)
            output.write(text)
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


def command(args, capture=False):
    return subprocess.run(args, check=True, text=True,
                          stdout=subprocess.PIPE if capture else sys.stderr,
                          stderr=subprocess.PIPE if capture else None)


def inspect(name):
    try:
        value = command(["docker", "image", "inspect", "--format", "{{.Id}}", name],
                        capture=True).stdout.strip()
    except subprocess.CalledProcessError as error:
        raise ValueError(f"Cannot inspect required image {name}: {error.stderr.strip()}") from error
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise ValueError(f"Invalid image ID returned for {name}")
    return value


def image_nodes(text):
    found = []
    visited = set()

    def walk(node):
        if node is None:
            return
        if id(node) in visited:
            raise ValueError("YAML aliases are not supported in the Cilium manifest")
        visited.add(id(node))
        if isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                if key.value == "image" and isinstance(value, yaml.ScalarNode):
                    repository = value.value.rsplit("/", 1)[-1].split(":")[0]
                    for role, name in ROLES.items():
                        if repository == name:
                            found.append((role, value))
                walk(value)
        elif isinstance(node, yaml.SequenceNode):
            for child in node.value:
                walk(child)

    for document in yaml.compose_all(text):
        # Node IDs can be reused after an earlier document is released.
        visited.clear()
        walk(document)
    if {role for role, _ in found} != set(ROLES):
        raise ValueError("Manifest must contain Agent, Operator and Envoy image references")
    return found


def context(args, selected_date=None):
    text = MANIFEST.read_text()
    nodes = image_nodes(text)
    date = selected_date or args.date
    if date is None:
        dates = set()
        for _, node in nodes:
            match = re.search(r"-([0-9]{8})$", node.value)
            if not match:
                raise ValueError(f"No date suffix on manifest image {node.value}")
            dates.add(match.group(1))
        if len(dates) != 1:
            raise ValueError("Cilium manifest contains conflicting image dates")
        date = dates.pop()
    if not re.fullmatch(r"[0-9]{8}", date):
        raise ValueError("Date must have YYYYMMDD format")
    datetime.datetime.strptime(date, "%Y%m%d")
    with open(Path(args.config) / "services-configuration.yaml") as source:
        registry_config = yaml.safe_load(source)["cluster"]["docker-registry"]
    registry = registry_config["domain"]
    namespace = registry_config["namespace"] if args.namespace == "@config" else args.namespace
    if not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]+)?", registry):
        raise ValueError("Invalid registry domain")
    if not re.fullmatch(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*", namespace):
        raise ValueError("Invalid image namespace")
    versions, guards = {}, {"manifest": digest(text)}
    for role in ROLES:
        file = BUILD / f"cilium-{role}.common.dockerfile"
        source = file.read_text()
        variable = "CILIUM_ENVOY_TAG" if role == "envoy" else "CILIUM_VERSION"
        match = re.search(rf"^ARG {variable}=([^\s]+)$", source, re.MULTILINE)
        if not match:
            raise ValueError(f"Missing {variable} in {file.name}")
        versions[role] = match.group(1)
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", versions[role]):
            raise ValueError(f"Invalid {role} version")
        guards[file.name] = digest(source)
    if versions["agent"] != versions["operator"]:
        raise ValueError("Agent and Operator CILIUM_VERSION must match: "
                         f"agent={versions['agent']}, operator={versions['operator']}")
    versions = {role: re.sub(r"-[a-f0-9]{40}$", "", version) for role, version in versions.items()}
    targets = {role: f"{registry}/{namespace}/{name}:{versions[role]}-{date}"
               for role, name in ROLES.items()}
    guards["targets"] = digest(json.dumps(targets, sort_keys=True))
    return text, nodes, date, registry, targets, guards


def identity(images):
    return digest(json.dumps(images, sort_keys=True, separators=(",", ":")))


def make_plan(args):
    text, nodes, date, registry, targets, guards = context(args)
    images = [{"role": role, "local_name": f"cilium-{role}:latest",
               "image_id": inspect(f"cilium-{role}:latest"), "destination": targets[role]}
              for role in ROLES]
    return {"schema_version": 1, "operation_id": str(uuid.uuid4()),
            "date": date, "date_source": "argument" if args.date else "manifest",
            "registry": registry, "images": images, "input_guards": guards,
            "publication_identity": identity(images),
            "manifest_matches_targets": all(node.value == targets[role] for role, node in nodes)}


def publish(args, plan):
    if (not isinstance(plan, dict) or plan.get("schema_version") != 1
            or plan.get("date_source") not in ("argument", "manifest")
            or not isinstance(plan.get("operation_id"), str)
            or not isinstance(plan.get("date"), str)
            or not isinstance(plan.get("images"), list)
            or any(not isinstance(item, dict) for item in plan["images"])):
        raise ValueError("Unsupported publication plan")
    uuid.UUID(plan["operation_id"])
    if args.date and args.date != plan["date"]:
        raise ValueError("Date conflicts with saved plan")
    text, nodes, date, registry, targets, guards = context(args, plan["date"])
    if guards != plan["input_guards"] or registry != plan["registry"]:
        raise ValueError("Publication inputs changed since planning; create a new plan")
    images = plan["images"]
    if len(images) != 3 or [item["role"] for item in images] != list(ROLES):
        raise ValueError("Invalid publication role inventory")
    for item in images:
        if not isinstance(item.get("image_id"), str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", item["image_id"]):
            raise ValueError("Invalid planned image ID")
        if item["destination"] != targets[item["role"]] or item["local_name"] != f"cilium-{item['role']}:latest":
            raise ValueError("Publication target does not match current inputs")
        if inspect(item["image_id"]) != item["image_id"]:
            raise ValueError("Planned image ID is no longer available")
    if identity(images) != plan["publication_identity"]:
        raise ValueError("Publication identity mismatch")
    if args.result_file and Path(args.result_file).exists():
        raise ValueError("Result path must be fresh; refusing stale success")
    print(f"Cilium date: {date} ({plan['date_source']}); republishing may replace tags",
          file=sys.stderr)
    for item in images:
        print(f"{item['image_id']} -> {item['destination']}", file=sys.stderr)
    published = []
    try:
        acr_name = registry[:-len(".azurecr.io")] if registry.endswith(".azurecr.io") else registry
        command(["az", "acr", "login", "--name", acr_name])
        for item in images:
            command(["docker", "tag", item["image_id"], item["destination"]])
            command(["docker", "push", item["destination"]])
            published.append(item["destination"])
    except subprocess.CalledProcessError:
        print(f"Publication failed; published so far: {published}. Manifest unchanged.",
              file=sys.stderr)
        raise
    if context(args, date)[5] != guards:
        raise ValueError("Images published, but inputs changed; manifest was not overwritten")
    replacements = {(node.start_mark.index, node.end_mark.index): json.dumps(targets[role])
                    for role, node in nodes if node.value != targets[role]}
    updated = text
    for (start, end), replacement in sorted(replacements.items(), reverse=True):
        updated = updated[:start] + replacement + updated[end:]
    changed = updated != text
    manifest_status = "unchanged"
    if changed:
        for old, new in sorted({(node.value, targets[role]) for role, node in nodes if node.value != targets[role]}):
            print(f"Manifest: {old} -> {new}", file=sys.stderr)
        print("All images published. Do not edit the manifest concurrently.", file=sys.stderr)
        print(f"Update {MANIFEST.relative_to(ROOT)}? [y/N]", file=sys.stderr, flush=True)
        with os.fdopen(3) as confirmation:
            answer = confirmation.readline()
        if not answer:
            raise ValueError("No confirmation input available; images are published, but the manifest "
                             "was not updated. Rerun with confirmation input.")
        answer = answer.strip().lower()
        if answer in ("y", "yes"):
            if context(args, date)[5] != guards:
                raise ValueError("Images published, but inputs changed while awaiting confirmation; "
                                 "manifest was not overwritten")
            try:
                atomic_write(MANIFEST, updated, MANIFEST.stat().st_mode & 0o777)
            except OSError:
                print("All images published, but manifest update failed.", file=sys.stderr)
                raise
            manifest_status = "changed"
            print(f"Changed {MANIFEST.relative_to(ROOT)}; review and check in this change.",
                  file=sys.stderr)
        elif answer in ("", "n", "no"):
            manifest_status = "skipped"
            print("Images published; manifest update declined. Deployment references remain unchanged.",
                  file=sys.stderr)
        else:
            raise ValueError("Expected y/yes or n/no; images are published, but the manifest was not updated")
    else:
        print("Images republished; manifest references unchanged.", file=sys.stderr)
    result = {key: plan[key] for key in
              ("schema_version", "operation_id", "publication_identity", "images")}
    result["manifest_status"] = manifest_status
    if args.result_file:
        try:
            atomic_write(args.result_file, json.dumps(result, sort_keys=True) + "\n")
        except OSError:
            print("All images published and manifest handled, but success-result persistence failed. "
                  "Batch completion must not be recorded.", file=sys.stderr)
            raise
    return result


def main():
    parser = argparse.ArgumentParser(description="Publish all Cilium images and offer to update the fixed manifest.")
    parser.add_argument("-c", "--config", required=True)
    parser.add_argument("-d", "--date", help="YYYYMMDD; defaults to the manifest date")
    parser.add_argument("-n", "--namespace", default="cilium", help='Namespace, or "@config"')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan-json", action="store_true", help="Read-only machine plan")
    mode.add_argument("--publish-plan", type=Path, help="Publish a previously resolved machine plan")
    parser.add_argument("--result-file", type=Path, help="Fresh machine success-result path")
    args = parser.parse_args(sys.argv[2:])
    if args.plan_json and args.result_file:
        parser.error("--result-file is only valid for publication")
    if args.plan_json:
        print(json.dumps(make_plan(args), sort_keys=True))
        return
    plan = json.loads(args.publish_plan.read_text()) if args.publish_plan else make_plan(args)
    publish(args, plan)


try:
    main()
except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError,
        subprocess.CalledProcessError) as error:
    print(f"Error: {error}", file=sys.stderr)
    sys.exit(1)
PY

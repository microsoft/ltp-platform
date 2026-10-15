# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]


class CiliumPublicationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.build = self.repo / "src/cilium/build"
        self.build.mkdir(parents=True)
        self.script = self.build / "push.sh"
        shutil.copy2(ROOT / "src/cilium/build/push.sh", self.script)
        self.manifest = self.repo / "contrib/aks/k8s-deploy/cilium.yaml"
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text(
            '# preserved comment\nkind: List\nitems:\n'
            '  - image: "registry.azurecr.io/cilium/cilium:v1.20.2-20261008"\n'
            '  - image: "registry.azurecr.io/cilium/cilium:v1.20.2-20261008"\n'
            '  - image: "registry.azurecr.io/cilium/operator-generic:v1.20.2-20261008"\n'
            '  - image: "registry.azurecr.io/cilium/cilium-envoy:v1.37.6-123-20261008"\n'
        )
        for role in ("agent", "operator", "envoy"):
            variable = "CILIUM_ENVOY_TAG" if role == "envoy" else "CILIUM_VERSION"
            version = "v1.37.6-123-" + "f" * 40 if role == "envoy" else "v1.20.2"
            (self.build / f"cilium-{role}.common.dockerfile").write_text(
                f"ARG {variable}={version}\nFROM scratch\n"
            )
        self.config = self.root / "config"
        self.config.mkdir()
        (self.config / "services-configuration.yaml").write_text(
            "cluster:\n  docker-registry:\n    domain: registry.azurecr.io\n    namespace: cilium\n"
        )
        subprocess.run(["git", "init", "--quiet", str(self.repo)], check=True)
        self.images = self.root / "images.json"
        self.images.write_text(json.dumps({
            f"cilium-{role}:latest": "sha256:" + letter * 64
            for role, letter in (("agent", "a"), ("operator", "b"), ("envoy", "c"))
        }))
        self.log = self.root / "commands.jsonl"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.executable(self.bin / "docker", """#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
path = Path(os.environ["IMAGES"])
images = json.loads(path.read_text())
args = sys.argv[1:]
with open(os.environ["COMMANDS"], "a") as log:
    log.write(json.dumps(["docker"] + args) + "\\n")
if args[:2] == ["image", "inspect"]:
    name = args[-1]
    value = name if name in images.values() else images.get(name)
    if not value:
        print("inspect failed", file=sys.stderr)
        sys.exit(1)
    print(value)
elif args[0] == "tag":
    images[args[2]] = args[1]
    path.write_text(json.dumps(images))
elif args[0] == "push":
    if os.environ.get("FAIL_PUSH") and os.environ["FAIL_PUSH"] in args[1]:
        sys.exit(2)
    if os.environ.get("CHANGE_MANIFEST"):
        with open(os.environ["CHANGE_MANIFEST"], "a") as manifest:
            manifest.write("# concurrent edit\\n")
""")
        self.executable(self.bin / "az", """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["COMMANDS"], "a") as log:
    log.write(json.dumps(["az"] + sys.argv[1:]) + "\\n")
""")
        self.env = dict(os.environ, PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                        IMAGES=str(self.images), COMMANDS=str(self.log))

    def tearDown(self):
        self.temporary.cleanup()

    def executable(self, path, content):
        path.write_text(content)
        path.chmod(0o755)

    def run_helper(self, *options, input="yes\n", **env):
        return subprocess.run([str(self.script), "-c", str(self.config), *options],
                              env=dict(self.env, **env), input=input, text=True, capture_output=True)

    def commands(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_default_republication_keeps_manifest_unchanged(self):
        before = self.manifest.read_text()
        output = self.root / "result.json"
        result = self.run_helper("--result-file", str(output), input="")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.manifest.read_text())
        self.assertEqual(3, sum(command[1] == "push" for command in self.commands()))
        self.assertIn("manifest references unchanged", result.stderr)
        self.assertNotIn("Update contrib/", result.stderr)
        self.assertEqual("unchanged", json.loads(output.read_text())["manifest_status"])

    def test_repository_multidocument_manifest_publication(self):
        shutil.copy2(ROOT / "contrib/aks/k8s-deploy/cilium.yaml", self.manifest)
        for role in ("agent", "operator", "envoy"):
            name = f"cilium-{role}.common.dockerfile"
            shutil.copy2(ROOT / "src/cilium/build" / name, self.build / name)
        before = self.manifest.read_text().replace(
            "luciaopenpai.azurecr.io/", "registry.azurecr.io/"
        )
        self.manifest.write_text(before)
        result = self.run_helper(input="")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.manifest.read_text())
        self.assertIn("manifest references unchanged", result.stderr)
        image_count = before.count("image:")
        self.assertEqual(9, image_count)
        result = self.run_helper("-d", "20261015")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(image_count, self.manifest.read_text().count("-20261015"))
        self.assertEqual(
            before.replace("-20261008", "-20261015"), self.manifest.read_text()
        )
        self.assertEqual(6, sum(command[1] == "push" for command in self.commands()))

    def test_publication_does_not_acquire_the_previous_publication_lock(self):
        lock = self.repo / ".git/ltp-image-tools/cilium-publish.lock"
        lock.parent.mkdir()
        with lock.open("a") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_helper()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(3, sum(command[1] == "push" for command in self.commands()))

    def test_preflight_failure_has_no_publication(self):
        for missing in ("agent", "operator", "envoy"):
            with self.subTest(missing=missing):
                initial = {f"cilium-{role}:latest": "sha256:" + letter * 64
                           for role, letter in (("agent", "a"), ("operator", "b"), ("envoy", "c"))
                           if role != missing}
                self.images.write_text(json.dumps(initial))
                self.log.unlink(missing_ok=True)
                result = self.run_helper()
                self.assertNotEqual(0, result.returncode)
                self.assertFalse(any(command[0] == "az" or command[1] in ("tag", "push")
                                     for command in self.commands()))

    def test_mismatched_agent_operator_versions_fail_before_inspect_or_publication(self):
        before = self.manifest.read_text()
        output = self.root / "result.json"
        for role, version in (("agent", "v1.20.3"), ("operator", "v1.20.3"),
                              ("agent", "v1.20.2-" + "a" * 40)):
            dockerfile = self.build / f"cilium-{role}.common.dockerfile"
            original = dockerfile.read_text()
            for options in (("--plan-json",), ("-d", "20261014", "--result-file", str(output))):
                with self.subTest(role=role, version=version, options=options):
                    dockerfile.write_text(original.replace("v1.20.2", version))
                    try:
                        result = self.run_helper(*options)
                        self.assertNotEqual(0, result.returncode)
                        self.assertIn("Agent and Operator", result.stderr)
                        self.assertEqual([], self.commands())
                        self.assertEqual(before, self.manifest.read_text())
                        self.assertFalse(output.exists())
                    finally:
                        dockerfile.write_text(original)
                        self.manifest.write_text(before)
                        self.log.unlink(missing_ok=True)
                        output.unlink(missing_ok=True)

    def test_all_roles_strip_source_hash_and_republish_same_tags(self):
        before = self.manifest.read_text()
        expected = {
            "agent": "registry.azurecr.io/cilium/cilium:v1.20.2-20261008",
            "operator": "registry.azurecr.io/cilium/operator-generic:v1.20.2-20261008",
            "envoy": "registry.azurecr.io/cilium/cilium-envoy:v1.37.6-123-20261008",
        }
        for index, commit in enumerate(("d" * 40, "e" * 40)):
            with self.subTest(commit=commit):
                for role in ("agent", "operator", "envoy"):
                    variable = "CILIUM_ENVOY_TAG" if role == "envoy" else "CILIUM_VERSION"
                    version = "v1.37.6-123" if role == "envoy" else "v1.20.2"
                    (self.build / f"cilium-{role}.common.dockerfile").write_text(
                        f"ARG {variable}={version}-{commit}\nFROM scratch\n"
                    )
                self.images.write_text(json.dumps({
                    f"cilium-{role}:latest": "sha256:" + letter * 64
                    for role, letter in zip(("agent", "operator", "envoy"),
                                            ("a", "b", "c") if index == 0 else ("d", "e", "f"))
                }))
                planned = self.run_helper("--plan-json")
                self.assertEqual(0, planned.returncode, planned.stderr)
                plan = json.loads(planned.stdout)
                self.assertEqual(expected, {
                    image["role"]: image["destination"] for image in plan["images"]
                })
                self.assertTrue(plan["manifest_matches_targets"])
                output = self.root / f"normalized-result-{index}.json"
                result = self.run_helper("--result-file", str(output), input="")
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(before, self.manifest.read_text())
                self.assertEqual("unchanged", json.loads(output.read_text())["manifest_status"])
        tagged = [command for command in self.commands() if command[1] == "tag"]
        self.assertEqual(6, len(tagged))
        self.assertEqual([image[3] for image in tagged[:3]],
                         [image[3] for image in tagged[3:]])
        self.assertNotEqual([image[2] for image in tagged[:3]],
                            [image[2] for image in tagged[3:]])
        self.assertEqual(6, sum(command[1] == "push" for command in self.commands()))

    def test_explicit_date_updates_every_occurrence_and_result(self):
        output = self.root / "result.json"
        result = self.run_helper("-d", "20261014", "--result-file", str(output), input="Y\n")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(4, self.manifest.read_text().count("-20261014"))
        self.assertTrue(self.manifest.read_text().startswith("# preserved comment"))
        record = json.loads(output.read_text())
        self.assertEqual("changed", record["manifest_status"])
        self.assertEqual(3, len(record["images"]))

    def test_declining_manifest_update_records_publication_without_writing(self):
        before = self.manifest.read_text()
        for index, answer in enumerate(("no\n", "n\n", "\n")):
            with self.subTest(answer=answer):
                output = self.root / f"result-{index}.json"
                result = self.run_helper("-d", "20261014", "--result-file", str(output), input=answer)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(before, self.manifest.read_text())
                self.assertIn("Update contrib/aks/k8s-deploy/cilium.yaml? [y/N]", result.stderr)
                self.assertIn("manifest update declined", result.stderr)
                self.assertEqual("skipped", json.loads(output.read_text())["manifest_status"])
        self.assertEqual(9, sum(command[1] == "push" for command in self.commands()))

    def test_missing_or_invalid_confirmation_does_not_write_manifest_or_result(self):
        before = self.manifest.read_text()
        output = self.root / "result.json"
        for answer, error in (("", "No confirmation input available"), ("maybe\n", "Expected y/yes or n/no")):
            with self.subTest(answer=answer):
                result = self.run_helper("-d", "20261014", "--result-file", str(output), input=answer)
                self.assertNotEqual(0, result.returncode)
                self.assertIn(error, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(before, self.manifest.read_text())
                self.assertFalse(output.exists())
        self.assertEqual(6, sum(command[1] == "push" for command in self.commands()))

    def test_edit_while_awaiting_confirmation_is_not_overwritten(self):
        output = self.root / "result.json"
        prompt = self.root / "prompt.log"
        before = self.manifest.read_text()
        with prompt.open("w") as log, subprocess.Popen(
                [str(self.script), "-c", str(self.config), "-d", "20261014", "--result-file", str(output)],
                env=self.env, text=True, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log) as process:
            try:
                deadline = time.monotonic() + 5
                while ("Update contrib/aks/k8s-deploy/cilium.yaml? [y/N]" not in prompt.read_text()
                       and process.poll() is None and time.monotonic() < deadline):
                    time.sleep(0.02)
                self.assertIn("Update contrib/aks/k8s-deploy/cilium.yaml? [y/N]", prompt.read_text())
                self.manifest.write_text(before + "# edit while awaiting confirmation\n")
                process.communicate(input="y\n", timeout=10)
            finally:
                if process.poll() is None:
                    process.communicate(input="no\n", timeout=10)
        self.assertNotEqual(0, process.returncode)
        self.assertIn("changed while awaiting confirmation", prompt.read_text())
        self.assertEqual(before + "# edit while awaiting confirmation\n", self.manifest.read_text())
        self.assertFalse(output.exists())

    def test_saved_plan_pins_ids_even_if_latest_changes(self):
        planned = self.run_helper("--plan-json")
        self.assertEqual(0, planned.returncode, planned.stderr)
        plan = self.root / "plan.json"
        plan.write_text(planned.stdout)
        images = json.loads(self.images.read_text())
        images["old-agent"] = images["cilium-agent:latest"]
        images["cilium-agent:latest"] = "sha256:" + "d" * 64
        self.images.write_text(json.dumps(images))
        result = self.run_helper("--publish-plan", str(plan))
        self.assertEqual(0, result.returncode, result.stderr)
        tagged = [command for command in self.commands() if command[1] == "tag"]
        self.assertEqual("sha256:" + "a" * 64, tagged[0][2])

    def test_push_failure_does_not_edit_manifest_or_write_result(self):
        before = self.manifest.read_text()
        output = self.root / "result.json"
        result = self.run_helper("--result-file", str(output), FAIL_PUSH="operator-generic")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(before, self.manifest.read_text())
        self.assertFalse(output.exists())

    def test_manifest_conflict_after_push_preserves_user_edit(self):
        result = self.run_helper("-d", "20261014", CHANGE_MANIFEST=str(self.manifest))
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("20261014", self.manifest.read_text())
        self.assertIn("concurrent edit", self.manifest.read_text())

    def test_invalid_and_conflicting_dates_fail_before_inspect(self):
        for date in ("20261301", "2026100"):
            result = self.run_helper("-d", date)
            self.assertNotEqual(0, result.returncode)
        self.manifest.write_text(self.manifest.read_text().replace(
            "operator-generic:v1.20.2-20261008", "operator-generic:v1.20.2-20261009"))
        result = self.run_helper()
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], self.commands())

    def test_aliases_and_malformed_plans_fail_without_publication(self):
        original = self.manifest.read_text()
        self.manifest.write_text(original.replace(
            'image: "registry.azurecr.io/cilium/cilium:v1.20.2-20261008"',
            'image: &agent "registry.azurecr.io/cilium/cilium:v1.20.2-20261008"', 1)
            .replace('  - image: "registry.azurecr.io/cilium/cilium:v1.20.2-20261008"',
                     '  - image: *agent', 1))
        self.assertNotEqual(0, self.run_helper().returncode)
        self.assertEqual([], self.commands())
        self.manifest.write_text(original)
        plan = self.root / "plan.json"
        for value in ([], {"schema_version": 1}, {"images": ["bad"]}):
            plan.write_text(json.dumps(value))
            result = self.run_helper("--publish-plan", str(plan))
            self.assertNotEqual(0, result.returncode)
            self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(any(command[0] == "az" for command in self.commands()))

    def test_stale_result_and_changed_inputs_block_publication(self):
        plan = self.root / "plan.json"
        plan.write_text(self.run_helper("--plan-json").stdout)
        output = self.root / "result.json"
        output.write_text("old success")
        result = self.run_helper("--publish-plan", str(plan), "--result-file", str(output))
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("old success", output.read_text())
        self.manifest.write_text(self.manifest.read_text() + "# changed after planning\n")
        result = self.run_helper("--publish-plan", str(plan))
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(any(command[0] == "az" for command in self.commands()))

    def prepare_batch(self):
        (self.repo / "tools").mkdir()
        tool = self.repo / "tools/build_and_push_images.sh"
        shutil.copy2(ROOT / "tools/build_and_push_images.sh", tool)
        (self.repo / "build").mkdir()
        self.executable(self.repo / "build/pai_build.py", """#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
with open(os.environ["COMMANDS"], "a") as log:
    log.write(json.dumps(["pai_build"] + sys.argv[1:]) + "\\n")
if os.environ.get("BLOCK_BATCH_PHASE") == sys.argv[1]:
    Path(os.environ["BATCH_STARTED"]).write_text("started")
    deadline = time.monotonic() + 15
    while not Path(os.environ["BATCH_RELEASE"]).exists():
        if time.monotonic() >= deadline:
            sys.exit(9)
        time.sleep(0.02)
""")
        return tool

    def run_batch(self, tool, *args, input="yes\n"):
        return subprocess.run([str(tool), *args], env=self.env, input=input, text=True, capture_output=True)

    def test_batch_out_of_range_from_does_not_reset_progress_or_execute(self):
        tool = self.prepare_batch()
        demo = self.repo / "src/demo/build"
        demo.mkdir(parents=True)
        (demo / "demo.common.dockerfile").write_text("FROM scratch\n")
        progress = self.repo / ".git/ltp-image-tools"
        progress.mkdir()
        for name in ("build.progress", "push.progress", "cilium-push.json"):
            (progress / name).write_text("preserve historical progress\n")
        before = {path.name: path.read_bytes() for path in progress.iterdir()}
        for action in ("build", "push", "all"):
            for skip, count in (([], 4), (["--skip-cilium"], 1)):
                for start in (str(count + 1), "18446744073709551617"):
                    with self.subTest(action=action, skip=skip, start=start):
                        result = self.run_batch(tool, action, "-c", str(self.config),
                                                "--from", start, "--reset", *skip)
                        self.assertNotEqual(0, result.returncode)
                        self.assertIn("--from", result.stderr)
                        self.assertIn(str(count), result.stderr)
                        self.assertEqual([], self.commands())
                        self.assertEqual(before, {path.name: path.read_bytes() for path in progress.iterdir()})

    def test_batch_from_accepts_first_and_last_filtered_task(self):
        tool = self.prepare_batch()
        demo = self.repo / "src/demo/build"
        demo.mkdir(parents=True)
        (demo / "demo.common.dockerfile").write_text("FROM scratch\n")
        for skip, start, expected in (([], "1", 4), ([], "4", 1), (["--skip-cilium"], "1", 1)):
            with self.subTest(skip=skip, start=start):
                self.log.unlink(missing_ok=True)
                result = self.run_batch(tool, "build", "-c", str(self.config), "--from", start, *skip)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(expected, len(self.commands()))
                self.assertTrue(all(command[:2] == ["pai_build", "build"] for command in self.commands()))

    def test_batch_declined_manifest_continues_and_resumes_without_republishing(self):
        tool = self.prepare_batch()
        demo = self.repo / "src/demo/build"
        demo.mkdir(parents=True)
        (demo / "demo.common.dockerfile").write_text("FROM scratch\n")
        options = ["push", "-c", str(self.config), "--cilium-date", "20261014"]
        before = self.manifest.read_text()
        result = self.run_batch(tool, *options, input="no\n")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.manifest.read_text())
        self.assertTrue(any(command[:2] == ["pai_build", "push"] for command in self.commands()))
        saved = self.repo / ".git/ltp-image-tools/cilium-push.json"
        self.assertEqual("skipped", json.loads(saved.read_text())["manifest_status"])
        result = self.run_batch(tool, *options, input="")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("[SKIP] Cilium group", result.stdout)
        self.assertIn("manifest update was previously declined", result.stderr)
        self.assertEqual(3, sum(command[:2] == ["docker", "push"] for command in self.commands()))
        result = self.run_batch(tool, *options, "--from", "1")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(6, sum(command[:2] == ["docker", "push"] for command in self.commands()))
        self.assertEqual(4, self.manifest.read_text().count("-20261014"))
        self.assertEqual("changed", json.loads(saved.read_text())["manifest_status"])

    def test_batch_missing_confirmation_does_not_record_completion(self):
        tool = self.prepare_batch()
        result = self.run_batch(tool, "push", "-c", str(self.config),
                                "--cilium-date", "20261014", input="")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("No confirmation input available", result.stderr)
        self.assertFalse((self.repo / ".git/ltp-image-tools/cilium-push.json").exists())
        self.assertEqual(3, sum(command[1] == "push" for command in self.commands()))

    def test_batch_concurrent_invocations_are_not_locked(self):
        tool = self.prepare_batch()
        demo = self.repo / "src/demo/build"
        demo.mkdir(parents=True)
        (demo / "demo.common.dockerfile").write_text("FROM scratch\n")
        progress = self.repo / ".git/ltp-image-tools"
        progress.mkdir()
        options = ["all", "-c", str(self.config), "--skip-cilium"]
        for phase in ("build", "push"):
            with self.subTest(phase=phase):
                for name in ("build.progress", "push.progress", "cilium-push.json"):
                    (progress / name).write_text("preserve historical progress\n")
                started, release = self.root / f"{phase}.started", self.root / f"{phase}.release"
                env = dict(self.env, BLOCK_BATCH_PHASE=phase,
                           BATCH_STARTED=str(started), BATCH_RELEASE=str(release))
                with subprocess.Popen([str(tool), *options, "--from", "1"], env=env,
                                      text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as first:
                    try:
                        deadline = time.monotonic() + 5
                        while not started.exists() and first.poll() is None and time.monotonic() < deadline:
                            time.sleep(0.02)
                        self.assertTrue(started.exists(), "First workflow did not reach the selected phase")
                        commands = self.commands()
                        for read_only in ("--status", "--list"):
                            result = self.run_batch(tool, "all", "--skip-cilium", read_only)
                            self.assertEqual(0, result.returncode, result.stderr)
                        result = subprocess.run([str(tool), *options, "--reset"], env=self.env,
                                                text=True, capture_output=True, timeout=3)
                        self.assertEqual(0, result.returncode, result.stderr)
                        self.assertGreater(len(self.commands()), len(commands))
                        self.assertFalse((progress / "workflow.lock").exists())
                    finally:
                        release.touch()
                        _, error = first.communicate(timeout=20)
                self.assertEqual(0, first.returncode, error)
                result = self.run_batch(tool, *options)
                self.assertEqual(0, result.returncode, result.stderr)

    def test_batch_skip_removes_tasks_and_mutations(self):
        tool = self.prepare_batch()
        demo = self.repo / "src/demo/build"
        demo.mkdir(parents=True)
        (demo / "demo.common.dockerfile").write_text("FROM scratch\n")
        progress = self.repo / ".git/ltp-image-tools"
        progress.mkdir()
        for phase in ("build", "push"):
            (progress / f"{phase}.progress").write_text("cilium/cilium-agent\ndemo/demo\n")
        saved = progress / "cilium-push.json"
        saved.write_text("preserved historical state")
        result = self.run_batch(tool, "all", "-c", str(self.config), "--skip-cilium", "--reset")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("docker", json.dumps(self.commands()))
        self.assertIn("Discovered images: 1", result.stdout)
        self.assertEqual("preserved historical state", saved.read_text())
        for phase in ("build", "push"):
            self.assertIn("cilium/cilium-agent", (progress / f"{phase}.progress").read_text())

    def test_batch_completion_tracks_destination_and_content(self):
        tool = self.prepare_batch()
        for expected_pushes, date, change in ((3, None, False), (3, None, False),
                                              (6, None, True), (9, "20261014", False)):
            if change:
                images = json.loads(self.images.read_text())
                images["cilium-agent:latest"] = "sha256:" + "d" * 64
                self.images.write_text(json.dumps(images))
            options = ["--cilium-date", date] if date else []
            result = self.run_batch(tool, "push", "-c", str(self.config), *options)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual(expected_pushes, sum(command[1] == "push" for command in self.commands()))
        record = json.loads((self.repo / ".git/ltp-image-tools/cilium-push.json").read_text())
        self.assertEqual(3, len(record["images"]))

    def test_batch_rejects_corrupt_group_state_and_ignores_legacy_completion(self):
        tool = self.prepare_batch()
        progress = self.repo / ".git/ltp-image-tools"
        progress.mkdir()
        (progress / "push.progress").write_text(
            "\n".join(f"cilium/cilium-{role}" for role in ("agent", "operator", "envoy")) + "\n")
        result = self.run_batch(tool, "push", "-c", str(self.config))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(3, sum(command[1] == "push" for command in self.commands()))
        (progress / "cilium-push.json").write_text("[]")
        result = self.run_batch(tool, "push", "-c", str(self.config))
        self.assertNotEqual(0, result.returncode)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(3, sum(command[1] == "push" for command in self.commands()))


if __name__ == "__main__":
    unittest.main()

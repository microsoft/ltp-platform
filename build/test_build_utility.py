# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import subprocess
import unittest
from unittest import mock

from build.core import build_utility


class DockerLoginTest(unittest.TestCase):
    def test_password_uses_stdin_without_shell_or_logging(self):
        password = "test password with spaces; 'quotes' & symbols"
        for registry in ("registry.example", "public"):
            with self.subTest(registry=registry):
                client = build_utility.DockerClient(
                    registry, "namespace", "test-user", password
                )
                command = [
                    "docker", "login", "--username", "test-user",
                    "--password-stdin",
                ]
                if registry != "public":
                    command.append(registry)
                with mock.patch.object(
                    build_utility.subprocess, "run"
                ) as run, mock.patch.object(
                    build_utility, "execute_shell"
                ) as shell, self.assertLogs(
                    build_utility.logger, level="INFO"
                ) as logs:
                    client.docker_login()

                run.assert_called_once_with(
                    command, input=password, text=True, check=True
                )
                shell.assert_not_called()
                self.assertNotIn(password, "\n".join(logs.output))

    def test_failed_login_exits_without_logging_password(self):
        password = "not-a-real-password"
        client = build_utility.DockerClient(
            "registry.example", "namespace", "test-user", password
        )
        failure = subprocess.CalledProcessError(1, ["docker", "login"])
        with mock.patch.object(
            build_utility.subprocess, "run", side_effect=failure
        ), self.assertLogs(
            build_utility.logger, level="INFO"
        ) as logs, self.assertRaises(SystemExit) as raised:
            client.docker_login()

        self.assertEqual(raised.exception.code, 1)
        self.assertNotIn(password, "\n".join(logs.output))
        self.assertTrue(any("login failed" in line for line in logs.output))

    def test_missing_docker_exits_with_an_explicit_error(self):
        client = build_utility.DockerClient(
            "registry.example", "namespace", "test-user", "test-password"
        )
        with mock.patch.object(
            build_utility.subprocess, "run",
            side_effect=FileNotFoundError("docker executable not found"),
        ), self.assertLogs(
            build_utility.logger, level="ERROR"
        ) as logs, self.assertRaises(SystemExit) as raised:
            client.docker_login()

        self.assertEqual(raised.exception.code, 1)
        self.assertIn("Unable to execute Docker login", "\n".join(logs.output))

    def test_azure_cli_login_remains_available_without_explicit_credentials(self):
        client = build_utility.DockerClient(
            "registry.azurecr.io", "namespace", "", ""
        )
        with mock.patch.object(
            build_utility.subprocess, "check_output"
        ) as account, mock.patch.object(
            build_utility.subprocess, "run"
        ) as run, self.assertLogs(build_utility.logger, level="INFO"):
            client.docker_login()

        account.assert_called_once_with(
            "az account show", shell=True, stderr=subprocess.STDOUT
        )
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                "az acr show --name registry",
                "az acr login --name registry",
            ],
        )


if __name__ == "__main__":
    unittest.main()

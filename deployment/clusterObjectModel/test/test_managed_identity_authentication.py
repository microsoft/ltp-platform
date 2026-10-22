# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import copy
import importlib.util
from pathlib import Path
import unittest

import jinja2
import yaml


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "authentication_config", ROOT / "src" / "authentication" / "config" / "authentication.py")
AUTHENTICATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUTHENTICATION)

TENANT_ID = "11111111-1111-4111-8111-111111111111"
APP_CLIENT_ID = "22222222-2222-4222-8222-222222222222"
MI_CLIENT_ID = "33333333-3333-4333-8333-333333333333"


def default_config(service):
    filename = ROOT / "src" / service / "config" / (service + ".yaml")
    return yaml.safe_load(filename.read_text(encoding="utf-8"))


class TestManagedIdentityAuthentication(unittest.TestCase):
    def setUp(self):
        self.authentication = default_config("authentication")
        self.authentication.update({
            "OIDC": True,
            "OIDC-type": "AAD",
            "AAD": {
                "tenantID": TENANT_ID,
                "clientID": APP_CLIENT_ID,
                "wellKnownURL": "https://idp.example/.well-known/openid-configuration",
                "credentialType": "managedIdentity",
                "managedIdentity": {"clientID": MI_CLIENT_ID},
            },
        })
        self.cluster = {
            "authentication": self.authentication,
            "cluster": {
                "common": {
                    "cluster-type": "k8s",
                    "k8s-rbac": "true",
                    "cluster-local-storage": "false",
                    "qos-switch": "true",
                    "az-rdma": "false",
                },
                "docker-registry": {
                    "prefix": "registry.example/",
                    "tag": "test",
                    "secret-name": "",
                },
            },
            "rest-server": default_config("rest-server"),
            "alert-manager": default_config("alert-manager"),
            "pylon": {
                "ssl": True,
                "uri": "http://portal.example",
                "uri-https": "https://portal.example",
            },
            "hivedscheduler": {"config": "", "webservice": "http://hived.example"},
            "log-manager": {"port": 9103},
            "layout": {"kubernetes": {"api-servers-url": "https://api.example"}},
            "postgresql": {"connection-str": "postgres://database.example/pai"},
            "database-controller": {"write-merger-url": "http://database.example"},
        }
        self.parser = AUTHENTICATION.Authentication({}, {}, self.authentication)

    def render(self, relative_path):
        source = (ROOT / "src" / relative_path).read_text(encoding="utf-8")
        return jinja2.Template(source).render(cluster_cfg=self.cluster)

    def use_legacy_credential(self, credential_type, explicit=False):
        aad = self.authentication["AAD"]
        aad.pop("credentialType", None)
        aad.pop("managedIdentity", None)
        if explicit:
            aad["credentialType"] = credential_type
        if credential_type == "certificate":
            aad["certificate"] = {
                "thumbprint": "0123456789abcdef",
                "keyPath": "/certs/private.pem",
                "certPath": "/certs/public.crt",
            }
        else:
            aad["clientSecret"] = "test-secret"

    def test_validates_managed_identity_without_legacy_credentials(self):
        self.assertEqual(self.parser.validation_pre(), (True, None))
        self.assertEqual(self.parser.validation_post(self.cluster), (True, None))

    def test_rejects_missing_or_invalid_managed_identity_client_id(self):
        for identity in (None, {}, {"clientID": ""}, {"clientID": 123},
                         {"clientID": "not-a-guid"}):
            with self.subTest(identity=identity):
                self.authentication["AAD"]["managedIdentity"] = identity
                self.assertFalse(self.parser.validation_pre()[0])

    def test_requires_guid_tenant_and_application_ids_in_managed_identity_mode(self):
        for field in ("tenantID", "clientID"):
            with self.subTest(field=field):
                original = self.authentication["AAD"][field]
                self.authentication["AAD"][field] = "not-a-guid"
                self.assertFalse(self.parser.validation_pre()[0])
                self.authentication["AAD"][field] = original

    def test_rejects_mixing_managed_identity_with_legacy_credentials(self):
        for field in ("clientSecret", "certificate"):
            with self.subTest(field=field):
                self.authentication["AAD"][field] = "legacy"
                self.assertFalse(self.parser.validation_pre()[0])
                del self.authentication["AAD"][field]

    def test_rejects_unknown_credential_type(self):
        self.authentication["AAD"]["credentialType"] = "invalid"
        self.assertFalse(self.parser.validation_pre()[0])

    def test_native_identity_does_not_require_workload_identity_service_account(self):
        self.cluster["cluster"]["common"]["k8s-rbac"] = "false"
        self.assertEqual(self.parser.validation_post(self.cluster), (True, None))
        pod = yaml.safe_load(self.render(
            "rest-server/deploy/rest-server.yaml.template"))["spec"]["template"]
        self.assertNotIn("serviceAccountName", pod["spec"])
        self.assertNotIn("azure.workload.identity/use", pod["metadata"]["labels"])
        self.assertNotIn("kubectl annotate serviceaccount",
                         self.render("rest-server/deploy/start.sh.template"))
        self.cluster["cluster"]["common"]["k8s-rbac"] = "true"
        self.cluster["cluster"]["common"]["cluster-type"] = "yarn"
        self.assertFalse(self.parser.validation_post(self.cluster)[0])

    def test_renders_managed_identity_oidc_config_without_secret_or_thumbprint(self):
        config = yaml.safe_load(self.render(
            "rest-server/deploy/auth-configmap/oidc.yaml.template"))
        self.assertEqual(config["credentialType"], "managedIdentity")
        self.assertEqual(config["clientID"], APP_CLIENT_ID)
        self.assertEqual(config["managedIdentity"]["clientID"], MI_CLIENT_ID)
        self.assertNotIn("clientSecret", config)
        self.assertNotIn("thumbprint", config)

    def test_uses_native_identity_and_removes_previous_workload_identity_annotations(self):
        manifest = yaml.safe_load(self.render(
            "rest-server/deploy/rest-server.yaml.template"))
        pod = manifest["spec"]["template"]
        self.assertNotIn("azure.workload.identity/use", pod["metadata"]["labels"])
        self.assertEqual(pod["spec"]["serviceAccountName"], "rest-server-account")
        script = self.render("rest-server/deploy/start.sh.template")
        self.assertIn("kubectl annotate serviceaccount rest-server-account --namespace default", script)
        self.assertIn("azure.workload.identity/client-id-", script)
        self.assertIn("azure.workload.identity/tenant-id-", script)
        self.assertNotIn('azure.workload.identity/client-id="', script)
        self.assertLess(script.index("kubectl annotate serviceaccount"),
                        script.index("-f rest-server.yaml"))

    def test_managed_identity_does_not_distribute_certificates(self):
        script = self.render("rest-server/deploy/configmap-create.sh.template")
        self.assertIn("configmap auth-configuration", script)
        self.assertNotIn("private.pem", script)
        self.assertNotIn("public.crt", script)

    def test_preserves_oidc_endpoints_and_nonce_configuration_for_every_credential(self):
        original = copy.deepcopy(self.authentication)
        for credential_type in ("managedIdentity", "clientSecret", "certificate"):
            with self.subTest(credential_type=credential_type):
                self.authentication.clear()
                self.authentication.update(copy.deepcopy(original))
                if credential_type != "managedIdentity":
                    self.use_legacy_credential(credential_type, explicit=True)
                self.authentication["AAD"].update({
                    "nonceLifetime": 600,
                    "nonceMaxAmount": 20,
                    "clockSkew": 30,
                })
                oidc = yaml.safe_load(self.render(
                    "rest-server/deploy/auth-configmap/oidc.yaml.template"))
                self.assertEqual(oidc["clientID"], APP_CLIENT_ID)
                self.assertEqual(oidc["tenantID"], TENANT_ID)
                self.assertEqual(oidc["wellKnownURL"],
                                 "https://idp.example/.well-known/openid-configuration")
                self.assertEqual(oidc["redirectUrl"],
                                 "https://portal.example/rest-server/api/v1/authn/oidc/return")
                self.assertEqual(oidc["destroySessionUrl"],
                                 "https://login.microsoftonline.com/common/oauth2/logout?"
                                 "post_logout_redirect_uri=http://portal.example")
                self.assertEqual(oidc["nonceLifetime"], 600)
                self.assertEqual(oidc["nonceMaxAmount"], 20)
                self.assertEqual(oidc["clockSkew"], 30)

    def test_rejects_explicit_legacy_modes_without_their_selected_credential(self):
        self.authentication["AAD"].pop("managedIdentity")
        for credential_type in ("clientSecret", "certificate"):
            with self.subTest(credential_type=credential_type):
                self.authentication["AAD"]["credentialType"] = credential_type
                self.assertFalse(self.parser.validation_pre()[0])

    def test_managed_identity_keeps_https_checker_without_oidc_certificate_mount(self):
        manifest = yaml.safe_load(self.render(
            "alert-manager/deploy/alert-manager-cert-expiration-check-cronjob.yaml.template"))
        pod = manifest["spec"]["jobTemplate"]["spec"]["template"]["spec"]
        container = pod["containers"][0]
        env = {entry["name"]: entry["value"] for entry in container["env"]}
        self.assertEqual(env["PAI_URI"], "https://portal.example")
        self.assertNotIn("OIDC_CERT_FILE_PATH", env)
        self.assertNotIn("volumeMounts", container)
        self.assertNotIn("volumes", pod)
        self.assertNotIn("configmap oidc-cert", self.render("alert-manager/deploy/start.sh.template"))

    def test_preserves_legacy_secret_and_certificate_deployments(self):
        original = copy.deepcopy(self.authentication)
        for credential_type in ("clientSecret", "certificate"):
            for explicit in (False, True):
                with self.subTest(credential_type=credential_type, explicit=explicit):
                    self.authentication.clear()
                    self.authentication.update(copy.deepcopy(original))
                    self.use_legacy_credential(credential_type, explicit)
                    self.assertEqual(self.parser.validation_pre(), (True, None))
                    oidc = yaml.safe_load(self.render(
                        "rest-server/deploy/auth-configmap/oidc.yaml.template"))
                    self.assertEqual(oidc["credentialType"], credential_type)
                    pod = yaml.safe_load(self.render(
                        "rest-server/deploy/rest-server.yaml.template"))["spec"]["template"]
                    self.assertNotIn("azure.workload.identity/use", pod["metadata"]["labels"])
                    self.assertNotIn("kubectl annotate serviceaccount",
                                     self.render("rest-server/deploy/start.sh.template"))
                    configmap_script = self.render("rest-server/deploy/configmap-create.sh.template")
                    checker = self.render(
                        "alert-manager/deploy/alert-manager-cert-expiration-check-cronjob.yaml.template")
                    if credential_type == "certificate":
                        self.assertIn("thumbprint", oidc)
                        self.assertIn("--from-file=\"private.pem\"", configmap_script)
                        self.assertIn("OIDC_CERT_FILE_PATH", checker)
                        checker_pod = yaml.safe_load(checker)["spec"]["jobTemplate"]["spec"]["template"]["spec"]
                        self.assertEqual(checker_pod["volumes"][0]["configMap"]["name"],
                                         "oidc-cert")
                        self.assertEqual(checker_pod["containers"][0]["volumeMounts"][0]["mountPath"],
                                         "/oidc-cert")
                    else:
                        self.assertEqual(oidc["clientSecret"], "test-secret")
                        self.assertNotIn("private.pem", configmap_script)
                        self.assertNotIn("OIDC_CERT_FILE_PATH", checker)

    def test_basic_authentication_does_not_require_aad_or_identity(self):
        self.authentication["OIDC"] = False
        del self.authentication["AAD"]
        self.assertEqual(self.parser.validation_pre(), (True, None))
        self.assertEqual(self.parser.validation_post(self.cluster), (True, None))
        self.assertFalse(self.render("rest-server/deploy/auth-configmap/oidc.yaml.template").strip())
        pod = yaml.safe_load(self.render(
            "rest-server/deploy/rest-server.yaml.template"))["spec"]["template"]
        self.assertNotIn("azure.workload.identity/use", pod["metadata"]["labels"])
        self.assertNotIn("configmap auth-configuration",
                         self.render("rest-server/deploy/configmap-create.sh.template"))
        checker = yaml.safe_load(self.render(
            "alert-manager/deploy/alert-manager-cert-expiration-check-cronjob.yaml.template"))
        checker_pod = checker["spec"]["jobTemplate"]["spec"]["template"]["spec"]
        checker_env = {entry["name"]: entry["value"]
                       for entry in checker_pod["containers"][0]["env"]}
        self.assertEqual(checker_env["PAI_URI"], "https://portal.example")
        self.assertNotIn("OIDC_CERT_FILE_PATH", checker_env)
        self.assertNotIn("volumes", checker_pod)
        self.assertNotIn("configmap oidc-cert",
                         self.render("alert-manager/deploy/start.sh.template"))


if __name__ == "__main__":
    unittest.main()

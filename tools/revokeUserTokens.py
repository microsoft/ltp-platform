# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# This tool is used to revoke all tokens in the cluster and restore the application token.
# Usage: python3 revokeUserTokens.py

import sys
import jwt
import base64
import uuid
from kubernetes import client, config


def get_application_token(namespace="default", deployment_name="alertmanager", container_name="job-status-change-notification"):
    """
    Retrieve PAI_BEARER_TOKEN from application deployment.

    Args:
        namespace: Kubernetes namespace (default: default)
        deployment_name: Name of the deployment (default: alertmanager)
        container_name: Name of the container (default: job-status-change-notification)

    Returns:
        The token string, or None if not found
    """
    try:
        config.load_kube_config()
        apps_v1 = client.AppsV1Api()

        # Get the deployment
        deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)

        # Find the container and get the PAI_BEARER_TOKEN env var
        for container in deployment.spec.template.spec.containers:
            if container.name == container_name:
                if container.env:
                    for env_var in container.env:
                        if env_var.name == "PAI_BEARER_TOKEN":
                            if env_var.value:
                                return env_var.value
                            elif env_var.value_from:
                                print(f"PAI_BEARER_TOKEN is from a secret/configmap, not a direct value")
                                return None

        print(f"PAI_BEARER_TOKEN not found in container {container_name}")
        return None

    except Exception as e:
        print(f"Error retrieving token from deployment: {e}")
        return None


def delete_all_token_secrets(namespace="pai-user-token"):
    """
    Delete all secrets in the token namespace.

    Args:
        namespace: Kubernetes namespace (default: pai-user-token)

    Returns:
        Number of secrets deleted, or -1 on error
    """
    try:
        config.load_kube_config()
        v1 = client.CoreV1Api()

        # List all secrets in the namespace
        secrets = v1.list_namespaced_secret(namespace=namespace)

        deleted_count = 0
        for secret in secrets.items:
            secret_name = secret.metadata.name
            try:
                v1.delete_namespaced_secret(name=secret_name, namespace=namespace)
                print(f"  Deleted secret: {secret_name}")
                deleted_count += 1
            except Exception as e:
                print(f"  Failed to delete secret {secret_name}: {e}")

        return deleted_count

    except Exception as e:
        print(f"Error deleting secrets: {e}")
        return -1


def add_token_to_k8s_secret(token_string, namespace="pai-user-token"):
    """
    Add a token to Kubernetes secret.

    Args:
        token_string: The JWT token to add
        namespace: Kubernetes namespace (default: pai-user-token)

    Returns:
        True if successful, False otherwise
    """
    try:
        config.load_kube_config()
        v1 = client.CoreV1Api()

        # Decode JWT to get username
        try:
            payload = jwt.decode(token_string, options={"verify_signature": False})
            username = payload.get('username')
            if not username:
                print("Username not found in token")
                return False
        except jwt.DecodeError as e:
            print(f"Failed to decode token: {e}")
            return False

        print(f"Token belongs to user: {username}")

        # Convert username to HEX for secret name
        secret_name = username.encode('utf-8').hex()
        print(f"Secret name (HEX): {secret_name}")

        # Generate UUID for the key
        key = str(uuid.uuid4())
        print(f"Generated UUID key: {key}")

        # Create the secret with the token
        encoded_data = {
            key: base64.b64encode(token_string.encode('utf-8')).decode('utf-8')
        }

        new_secret = client.V1Secret(
            metadata=client.V1ObjectMeta(name=secret_name, namespace=namespace),
            data=encoded_data
        )

        v1.create_namespaced_secret(namespace=namespace, body=new_secret)
        print(f"Created secret '{secret_name}' with token")

        return True

    except Exception as e:
        print(f"Error adding token to K8s secret: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Token Revocation and Restoration Tool")
    print("=" * 70)
    print("\nThis tool will delete all the user tokens but keep the application token.")
    print("\n⚠️  WARNING: This will cause service disruptions during execution!")
    print("=" * 70)

    confirm = input("\nType 'yes' to proceed: ")
    if confirm.lower() != 'yes':
        print("Operation cancelled.")
        sys.exit(0)

    # Step 1: Retrieve alert-manager token
    print("\n" + "=" * 70)
    print("Step 1: Retrieving PAI_BEARER_TOKEN from alert-manager")
    print("=" * 70)

    alert_namespace = "default"
    alert_deployment = "alertmanager"
    alert_container = "job-status-change-notification"

    alert_token = get_application_token(alert_namespace, alert_deployment, alert_container)

    if not alert_token:
        print("\n✗ Failed to retrieve alert-manager token.")
        print("Do you want to continue without it? (The alert-manager token will NOT be restored)")
        continue_choice = input("Type 'yes' to continue: ")
        if continue_choice.lower() != 'yes':
            print("Operation cancelled.")
            sys.exit(1)
    else:
        print(f"✓ Successfully retrieved alert-manager token")
        print(f"Token (truncated): {alert_token[:20]}...{alert_token[-20:]}")

    # Step 2: Delete all token secrets
    print("\n" + "=" * 70)
    print("Step 2: Deleting all token secrets")
    print("=" * 70)

    token_namespace = "pai-user-token"

    deleted_count = delete_all_token_secrets(token_namespace)
    if deleted_count >= 0:
        print(f"✓ Successfully deleted {deleted_count} secrets.")
    else:
        print(f"✗ Failed to delete secrets.")
        sys.exit(1)

    # Step 3: Add alert-manager token back
    if alert_token:
        print("\n" + "=" * 70)
        print("Step 3: Adding alert-manager token back")
        print("=" * 70)

        if add_token_to_k8s_secret(alert_token, token_namespace):
            print("✓ Alert-manager token has been restored successfully.")
        else:
            print("✗ Failed to restore alert-manager token.")
            sys.exit(1)

    print("\n" + "=" * 70)
    print("✓ Operation completed successfully!")
    print("=" * 70)

# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Authentication Manager."""

import os
import requests
import urllib.parse

from datetime import datetime, timezone

from ..config import AGENT_MODE_LOCAL
from ..utils.logger import logger

class AuthenticationManager:
    """Manages authentication state, expiration, and revocation for users."""
    def __init__(self, expiration_ms: int = 3600000):
        self.authenticate_state = {}  # username: {token, expires_at, groups}
        self.expiration_ms = expiration_ms
        self.restserver_url = os.getenv('RESTSERVER_URL', '')
        valid_vcs_env = os.getenv('COPILOT_VALID_GROUPS', 'admin,superuser')
        self.valid_vcs = [g.strip() for g in valid_vcs_env.split(',') if g.strip()]

    def sanitize_username(self, username: str) -> str:
        """Sanitize the username by URL-encoding it to prevent path traversal or injection attacks."""
        return urllib.parse.quote(username, safe='')

    def authenticate(self, username: str, token: str):
        """
        Authenticate a user with token and REST server URL.

        Args:
            username (str): The username of the user to authenticate.
            token (str): The authentication token provided by the user.

        Returns:
            tuple: (admin, virtualCluster)
        """
        if AGENT_MODE_LOCAL:
            if username == "gooduser":
                return True, ["admin"]
            if username == "baduser":
                return False, ["temp"]
            # For any other username in local mode, return empty list
            return False, []
        else:
            # This function should implement the logic to verify the user's token against the REST server (self.restserver_url).
            try:
                headers = {
                    'Authorization': f'Bearer {token}'
                }
                username_sanitized = self.sanitize_username(username)
                response = requests.get(f'{self.restserver_url}/api/v2/users/{username_sanitized}', headers=headers, timeout=5)
                
                if response.status_code == 200:
                    user_data = response.json()
                    # Extract groups from the response - adjust based on actual API response structure
                    is_admin = user_data.get('admin', False)
                    virtual_cluster = user_data.get('virtualCluster', [])
                    return is_admin, virtual_cluster
                else:
                    logger.error(f"Authentication failed for user {username}: {response.status_code}")
                    return False, []
            except Exception as e:
                logger.error(f"Error during authentication for user {username}: {e}")
                return False, []

    def set_authenticate_state(self, username: str, token: str) -> None:
        """Set the authentication state for a user, storing admin and virtualCluster info."""
        expires_at = int(datetime.now(timezone.utc).timestamp() * 1000) + self.expiration_ms
        is_admin, virtual_cluster = self.authenticate(username, token)
        if is_admin is not None and virtual_cluster is not None:
            self.authenticate_state[username] = {
                'token': token,
                'expires_at': expires_at,
                'is_admin': is_admin,
                'virtual_cluster': virtual_cluster
            }
        else:
            self.revoke(username)

    def is_authenticated(self, username: str) -> bool:
        state = self.authenticate_state.get(username)
        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        if not state:
            return False
        if state['expires_at'] < now:
            self.revoke(username)
            return False
        if "is_admin" not in state:
            return False
        if "virtual_cluster" not in state:
            return False
        if "is_admin" in state and "virtual_cluster" in state:
            if state["is_admin"]:
            # validate pass condition one: user is an admin
                return True
            elif not state["is_admin"] and self.get_membership(state["virtual_cluster"]):
            # validate pass condition two: user is not an admin, but it belongs to a valid virtualCluster
                return True
            else:
                return False
        return False

    def get_membership(self, groups: list) -> bool:
        return any(group in self.valid_vcs for group in groups)

    def revoke(self, username: str):
        if username in self.authenticate_state:
            del self.authenticate_state[username]

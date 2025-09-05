"""Authentication Manager."""

import os

from datetime import datetime, timezone

from ..config import AGENT_MODE_LOCAL

class AuthenticationManager:
    """Manages authentication state, expiration, and revocation for users."""
    def __init__(self, expiration_ms: int = 3600000):
        self.authenticate_state = {}  # username: {token, expires_at, groups}
        self.expiration_ms = expiration_ms
        self.restserver_url = os.getenv('RESTSERVER_URL', '')
        valid_groups_env = os.getenv('COPILOT_VALID_GROUPS', 'admin,superuser')
        self.valid_groups = [g.strip() for g in valid_groups_env.split(',') if g.strip()]

    def authenticate(self, username: str, token: str) -> list:
        """
        Authenticate a user with token and REST server URL.

        Args:
            username (str): The username of the user to authenticate.
            token (str): The authentication token provided by the user.

        Returns:
            list: A list of group names the user belongs to if authentication is successful.
            Returns an empty list if authentication fails.
        """
        if AGENT_MODE_LOCAL:
            if username == "gooduser":
                return ["admin"]
            if username == "baduser":
                return ["temp"]
        else:
            # TBD
            # This function should implement the logic to verify the user's token against the REST server (self.restserver_url).
            return []

    def set_authenticate_state(self, username: str, token: str) -> None:
        """Set the authentication state for a user."""
        expires_at = int(datetime.now(timezone.utc).timestamp() * 1000) + self.expiration_ms
        groups = self.authenticate(username, token)
        if groups:
            self.authenticate_state[username] = {
                'token': token,
                'expires_at': expires_at,
                'groups': groups
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
        if "groups" not in state:
            return False
        if "groups" in state and not self.get_membership(state["groups"]):
            return False
        return True

    def get_membership(self, groups: list) -> bool:
        return any(group in self.valid_groups for group in groups)

    def revoke(self, username: str):
        if username in self.authenticate_state:
            del self.authenticate_state[username]

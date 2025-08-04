"""Authentication utilities."""

import json
import os

from ..config import DATA_DIR


def authenticate_user(user_name):
    """Check if the user is authorized."""
    with open(os.path.join(DATA_DIR, 'authorized_users', 'authorized_users.json')) as f:
        authorized_users = json.load(f)
    for role, data in authorized_users['roles'].items():
        if user_name in data['users']:
            return True, role
    return False, None

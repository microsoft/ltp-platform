# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Utility functions for time-related operations."""

import time
from datetime import timedelta
from ..utils.logger import logger


def get_current_unix_timestamp():
    """Get the current Unix timestamp in seconds."""
    return int(time.time())


def parse_duration(duration_str):
    """Convert a Prometheus-style duration (e.g., '6h') to a timedelta object."""
    if duration_str.endswith('h') or duration_str.endswith('hours'):
        return timedelta(hours=int(duration_str.removesuffix('h').removesuffix('hours')))
    elif duration_str.endswith('m') or duration_str.endswith('minutes'):
        return timedelta(minutes=int(duration_str.removesuffix('m').removesuffix('minutes')))
    elif duration_str.endswith('s') or duration_str.endswith('seconds'):
        return timedelta(seconds=int(duration_str.removesuffix('s').removesuffix('seconds')))
    elif duration_str.endswith('d') or duration_str.endswith('days'):
        return timedelta(days=int(duration_str.removesuffix('d').removesuffix('days')))
    elif duration_str.endswith('w') or duration_str.endswith('weeks'):
        return timedelta(weeks=int(duration_str.removesuffix('w').removesuffix('weeks')))
    else:
        logger.info(f"Unsupported duration format: {duration_str}. The duration must end with 'h', 'm', 's', 'd', or 'w'.")
        return timedelta(0)

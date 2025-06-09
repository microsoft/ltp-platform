from datetime import timedelta
from datetime import datetime, timezone

import pandas as pd


def parse_duration(duration_str):
    """Convert a Prometheus-style duration (e.g., '6h') to a timedelta object."""
    if duration_str.endswith("h") or duration_str.endswith("hours"):
        return timedelta(hours=int(duration_str.strip("h").strip("hours")))
    elif duration_str.endswith("m") or duration_str.endswith("minutes"):
        return timedelta(minutes=int(duration_str.strip("m").strip("minutes")))
    elif duration_str.endswith("s") or duration_str.endswith("seconds"):
        return timedelta(seconds=int(duration_str.strip("s").strip("seconds")))
    elif duration_str.endswith("d") or duration_str.endswith("days"):
        return timedelta(days=int(duration_str.strip("d").strip("days")))
    elif duration_str.endswith("w") or duration_str.endswith("weeks"):
        return timedelta(weeks=int(duration_str.strip("w").strip("weeks")))
    else:
        raise ValueError(
            f"Unsupported duration format: {duration_str}. The duration must end with 'h', 'm', 's', 'd', or 'w'."
        )


def convert_timestamp(timestamp_str, format="timestamp"):
    """
    Converts various timestamp formats to epoch timestamp or formatted datetime.

    Args:
        timestamp_str: Input timestamp (int, float, str, or datetime)
        format: Output format ('timestamp', 'datetime', or 'str')

    Returns:
        Timestamp in requested format
    """
    # Step 1: Convert input to epoch timestamp (int)
    if isinstance(timestamp_str, (int, float)):
        # For numeric inputs, use directly as epoch timestamp
        epoch_timestamp = int(timestamp_str)
    elif isinstance(timestamp_str, datetime):
        # For datetime objects, convert to epoch
        epoch_timestamp = int(timestamp_str.timestamp())
    elif isinstance(timestamp_str, str):
        # For string inputs, handle different formats
        if timestamp_str.endswith("Z"):
            timestamp_str = timestamp_str[:-1] + "+00:00"
        elif "T" in timestamp_str:
            # Keep the T for ISO format which pd.to_datetime can handle
            pass

        # Convert string to epoch timestamp
        epoch_timestamp = int(pd.to_datetime(timestamp_str).timestamp())
    else:
        raise ValueError(f"Invalid timestamp type: {type(timestamp_str)}")

    # Step 2: Convert epoch timestamp to requested output format
    if format == "timestamp":
        return epoch_timestamp
    elif format == "datetime":
        return datetime.fromtimestamp(epoch_timestamp, tz=timezone.utc)
    elif format == "str":
        dt = datetime.fromtimestamp(epoch_timestamp, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    else:
        raise ValueError(f"Invalid format type: {format}")

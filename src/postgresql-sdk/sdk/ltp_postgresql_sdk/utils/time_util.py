# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Time utility functions."""

from datetime import datetime
from typing import Union


def convert_timestamp(
    timestamp: Union[str, datetime], output_format: str = "datetime"
) -> Union[str, datetime]:
    """
    Convert timestamp between string and datetime formats.

    Args:
        timestamp: Input timestamp (string or datetime)
        output_format: Desired output format ('datetime' or 'str')

    Returns:
        Converted timestamp in the requested format

    Raises:
        ValueError: If the timestamp format is invalid
    """
    if output_format == "datetime":
        if isinstance(timestamp, datetime):
            return timestamp
        elif isinstance(timestamp, str):
            # Try common ISO formats
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
            ]:
                try:
                    return datetime.strptime(timestamp, fmt)
                except ValueError:
                    continue
            # Try ISO format parsing
            try:
                return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError(f"Unable to parse timestamp: {timestamp}")
        else:
            raise ValueError(f"Invalid timestamp type: {type(timestamp)}")

    elif output_format == "str":
        if isinstance(timestamp, str):
            return timestamp
        elif isinstance(timestamp, datetime):
            return timestamp.isoformat()
        else:
            raise ValueError(f"Invalid timestamp type: {type(timestamp)}")

    else:
        raise ValueError(f"Invalid output_format: {output_format}")



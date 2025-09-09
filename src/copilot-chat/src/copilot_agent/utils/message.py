# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Utility functions for handling messages."""

from __future__ import annotations


def get_last_value(messages_list: list, keys: list, max_messages: int | None = None) -> (bool, str):
    """Extracts the last value from a list of messages based on a list of keys.

    :param messages_list: List of messages (dictionaries) to search through.
    :param keys: List of keys to navigate through each message.
    :param max_messages: Maximum number of messages to look into. If None, look into all messages.
    :return: A tuple (last_value_exist, last_value_str) where last_value_exist is a boolean indicating
    if the value was found, and last_value_str is the extracted value as a string.
    """
    last_value_exist = False
    last_value_str = ''

    # Determine the range of messages to look into
    messages_to_check = messages_list if max_messages is None else messages_list[-max_messages:]

    for message in reversed(messages_to_check):
        current_level = message
        for key in keys:
            if current_level is None:
                break
            if key in current_level:
                current_level = current_level[key]
            else:
                break
        else:
            if current_level is not None:
                last_value_exist = True
                last_value_str = current_level
                break

    return last_value_exist, last_value_str

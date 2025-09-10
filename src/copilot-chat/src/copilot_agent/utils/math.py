# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Utility functions for mathematical operations."""

import re


# generates a list of values starting from filter_min and doubling until reaching filter_max.
def gen_size_range(filter_min, filter_max):
    """Generate a list of values starting from filter_min and doubling until reaching filter_max."""
    values = []
    current_value = filter_min

    while current_value <= filter_max:
        values.append(current_value)
        current_value *= 2
    return values


# searches for a key in a JSON object that matches the provided regex and returns its value.
def find_value_in_json(regex, json_obj):
    """Search for a key in a JSON object that matches the provided regex and return its value."""
    pattern = re.compile(regex)
    for key in json_obj.keys():
        if pattern.match(key):
            return json_obj[key]
    return 'NA'

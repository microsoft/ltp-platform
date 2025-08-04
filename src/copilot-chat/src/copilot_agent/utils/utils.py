"""Utility functions for the Copilot Agent."""

import json
import os
import re


# reads and returns the content of a file at a given path.
def get_prompt_from(path: str) -> str:
    """Reads and returns the content of a file at a given path."""
    if not os.path.exists(path):
        raise FileNotFoundError(f'{path} not found.')
    with open(path) as f:
        return f.read()


# extracts all JSON objects from a given benchmark string, with an option to extract nested JSON objects.
def extract_all_json(benchmark, nested=False):
    """Extracts all JSON objects from a given benchmark string."""
    # two level json object
    if nested:
        pattern = r'(\{.*?\{?.*?\}?.*?\})'
        if '```json' in benchmark:
            pattern = r'```json\s*\n*(\{.*?\{?.*?\}?.*?\})\n*```'
        elif '```jsonl' in benchmark:
            pattern = r'```jsonl\s*\n*(\{.*?\{?.*?\}?.*?\})\n*```'
    # one level json object
    else:
        pattern = r'(\{.*?\})'
        if '```json' in benchmark:
            pattern = r'```json\s*\n*(\{.*?\})\n*```'
        elif '```jsonl' in benchmark:
            pattern = r'```jsonl\s*\n*(\{.*?\})\n*```'

    json_match = re.search(pattern, benchmark, re.DOTALL)

    if json_match:
        json_config = re.findall(pattern, benchmark, re.DOTALL)
        return json_config
    else:
        return None


# checks if a given string is a valid JSON.
def is_valid_json(json_str):
    """Checks if a given string is a valid JSON."""
    try:
        json.loads(json_str)
    except ValueError:
        return False
    return True


# extracts the last JSON object from a given benchmark string as a dictionary, with an option to extract nested JSON objects.
def extract_json_dict(benchmark, nested=True):
    """Extracts the last JSON object from a given benchmark string as a dictionary."""
    jsons = extract_all_json(benchmark, nested)
    if jsons:
        json_str = jsons[-1]
        if is_valid_json(json_str):
            return json.loads(json_str)
    return None


# retries a function with given arguments and keyword arguments for a specified number of times until it returns a truthy value.
def retry_function(func, max_retries, *args, **kwargs):
    """Retries a function with given arguments and keyword arguments for a specified number of times until it returns a truthy value."""
    return (
        (
            func(*args, **kwargs)
            if max_retries == 0
            else func(*args, **kwargs) or retry_function(func, max_retries - 1, *args, **kwargs)
        )
        if max_retries > 0
        else None
    )


# asynchronously retries a function with given arguments and keyword arguments for a specified number of times until it returns a non-None value.
async def retry_async(func, max_retries, *args, **kwargs):
    """Asynchronously retries a function with given arguments and keyword arguments for a specified number of times until it returns a non-None value."""
    if max_retries == 0:
        return await func(*args, **kwargs)

    result = await func(*args, **kwargs)
    if result is not None:
        return result

    return await retry_async(func, max_retries - 1, *args, **kwargs)

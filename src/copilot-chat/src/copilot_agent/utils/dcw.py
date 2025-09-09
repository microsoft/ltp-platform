# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""This module contains functions for generating, parsing, and aligning DCW objects."""

from __future__ import annotations

import copy
import json
import os

from ..utils.logger import logger

from ..config import PROMPT_DIR
from ..utils.llmsession import LLMSession
from ..utils.types import DCW, Customer, Design
from ..utils.utils import get_prompt_from

model = LLMSession()


# generate dcw (design, criteria, workload) from using question
def gen_dcw(user_prompt: str, map_existing: bool) -> DCW:
    """Generate a DCW object from the user's question."""
    sys_prompt = get_prompt_from(os.path.join(PROMPT_DIR, 'gen_dcw_prompt.txt'))
    resp = model.chat(sys_prompt, user_prompt)
    logger.info(f'gen_dcw, user_prompt, is {user_prompt}')
    logger.info(f'gen_dcw, resp, is {resp}')
    if 'target' not in resp.lower() and 'baseline' not in resp.lower():
        resp = None
        logger.info(f'gen_dcw, resp, is {resp}')
    dcw = dcw_parser(resp)

    # check if native dcw consists a precise description of a benchmark name, if not, revise it
    if map_existing:
        revise_json = json.loads(get_prompt_from(os.path.join(PROMPT_DIR, 'revise_dcw.json')))
        revise_sys_prompt = (
            revise_json['prompt'] + f"\n\nthe {{benchmark: workload}} mapping table is\n{revise_json['description']}\n"
        )
        revise_user_prompt = f'the user input workload is {dcw.Workload.lower()}'

        if all(item not in dcw.Workload.lower() for item in revise_json['list']):
            logger.info(f'before revise: {dcw}')
            dcw.Workload = model.chat(revise_sys_prompt, revise_user_prompt)
            logger.info(f'after revise: {dcw}')

    return dcw


# parse a dict like object into a DCW type
def dcw_parser(json_input: str | dict | None) -> DCW:
    """Parse a dictionary-like object into a DCW type."""
    logger.info(f'json_input: {json_input}')
    try:
        if json_input is None:
            raise ValueError('No input provided to dcw parser')

        if isinstance(json_input, dict):
            data = json_input
        elif isinstance(json_input, str):
            json_input = json_input.replace('```json', '').replace('```', '')
            if not json_input:
                raise ValueError('Empty JSON string provided to dcw parser')
            try:
                data = json.loads(json_input)
            except json.JSONDecodeError as e:
                raise ValueError(f'Invalid JSON string provided to dcw parser: {e}') from e
        else:
            raise TypeError('Input to dcw parser must be a string, dictionary, or None')

        return DCW(**data)
    except (ValueError, TypeError, json.JSONDecodeError) as e:
        logger.info(f'Error: {e}')
        return DCW(
            Design=Design(Target='', Baseline=''), Criterion='', Workload='', Customer=Customer(Target='', Baseline='')
        )


# extract DCW from chat history
def extract_dcw_from_history(messages_list: list) -> (bool, bool | DCW):
    """Extracts the DCW from the chat history."""
    message_list_len = len(messages_list)
    logger.info('starting to parse dcw structure from history')

    # no previous message
    if message_list_len == 1:
        last_dcw_exists = False
        last_dcw = None
    else:
        last_dcw_exists = False
        last_dcw = None
        # look for previous logged dcw
        for message in reversed(messages_list):
            if not isinstance(message, dict):
                continue
            if 'additional_info' in message and isinstance(message['additional_info'], dict):
                if 'dcw' in message['additional_info']:
                    last_dcw_str = message['additional_info']['dcw']
                    logger.info(f'last_dcw_str: {last_dcw_str}')
                    logger.info(f'type of last_dcw_str: {type(last_dcw_str)}')
                    if last_dcw_str is not None:
                        last_dcw_exists = True
                        if isinstance(last_dcw_str, DCW):
                            last_dcw = last_dcw_str
                        else:
                            last_dcw = dcw_parser(last_dcw_str)
                        break  # only extract the last dcw, stop traverse if found

    return last_dcw_exists, last_dcw


# parse and align dcw
def parse_and_align_dcw(user_prompt, map_existing, last_dcw=None):
    """Parses the DCW from the user's question and aligns the placement of target and baseline.

    if the previous DCW exists and the content is the same.

    :param user_prompt: The user's question or prompt.
    :param map_existing: A mapping function or data used in DCW generation.
    :param last_dcw: The last DCW object, if it exists.
    :return: The parsed and possibly aligned DCW object.
    """
    new_conversation = True

    # parse DCW from user's question
    full_dcw = gen_dcw(user_prompt, map_existing)
    if not isinstance(full_dcw, DCW):
        full_dcw = dcw_parser(full_dcw)
    dcw_before_alignment = copy.deepcopy(full_dcw)

    # check if previous DCW exists and is of type DCW
    if last_dcw and isinstance(last_dcw, DCW):
        this_design_list = [
            full_dcw.Design.Target.replace('GPU', '').replace(' ', ''),
            full_dcw.Design.Baseline.replace('GPU', '').replace(' ', ''),
        ]
        last_design_list = [
            last_dcw.Design.Target.replace('GPU', '').replace(' ', ''),
            last_dcw.Design.Baseline.replace('GPU', '').replace(' ', ''),
        ]

        # align the placement if the content of target and baseline are the same
        if sorted(this_design_list) == sorted(last_design_list):
            full_dcw.Design.Target = last_dcw.Design.Target
            full_dcw.Design.Baseline = last_dcw.Design.Baseline
            new_conversation = False
        elif this_design_list[0] == '':
            new_conversation = False
            return dcw_before_alignment, last_dcw, new_conversation

    return dcw_before_alignment, full_dcw, new_conversation


# updates the Kusto session DCW with the controller input
def update_kusto_session_dcw(this_dcw: DCW, controller_input: dict):
    """Update Kusto session DCW with controller input."""
    if isinstance(this_dcw, DCW):
        if 'type' in controller_input:
            this_dcw.Workload = controller_input['type']
        if 'input' in controller_input:
            this_dcw.Criterion = controller_input['input']

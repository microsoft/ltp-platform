"""This module contains functions for generating, parsing, and aligning DCW objects."""

from __future__ import annotations

import os

from ..utils.logger import logger

from ..config import TOKEN_LIMIT, PROMPT_DIR
from ..utils.llmsession import LLMSession
from ..utils.smart_help import gen_smart_help
from ..utils.utils import get_prompt_from

model = LLMSession()

def gen_summary(
    SUB_FEATURE, resp_total, resp_brief, question, gen_prompt_file, knowledge_prompt_file, help_msg, skip_summary=False
):
    """Generate a summary."""
    logger.info('Generating Response Report')
    if isinstance(resp_total, (dict, list)):
        logger.info(f'length of resp_total (# of tokens): {len(str(resp_total))}')
    if isinstance(resp_brief, (dict, list)):
        logger.info(f'length of resp_brief (# of tokens): {len(str(resp_brief))}')

    if isinstance(resp_total, (dict, list)):
        if len(str(resp_total)) < TOKEN_LIMIT:
            logger.info('using full data')
            user_prompt = f'<User question> is:\n{question}\n\n<Result> is\n{resp_total}\n\n'
        else:
            logger.info('using brief data')
            user_prompt = (
                f'<User question> is:\n{question}\n\n'
                + f'<Important Message to User> is: the result is too long to display. Please check the details, this is brief description of the result {resp_brief}\n'
            )
        gen_sum_prompt = get_prompt_from(os.path.join(PROMPT_DIR, SUB_FEATURE, gen_prompt_file))
        if knowledge_prompt_file:
            knowledge_prmpt = get_prompt_from(os.path.join(PROMPT_DIR, SUB_FEATURE, knowledge_prompt_file))
        else:
            knowledge_prmpt = ''
        sys_prompt = gen_sum_prompt + '\n\n' + knowledge_prmpt + '\n\n'
        if not skip_summary:
            logger.info('Bypass summary: False')
            summary = model.chat(sys_prompt, user_prompt)
        else:
            logger.info('Bypass summary: True')
            summary = handle_bypass_summary(resp_total, resp_brief)
    else:
        logger.info('generating smart help')
        help_keys = ['corrupted_data']
        summary = help_keys[0]
        summary = gen_smart_help(help_msg, question, help_keys)
    return summary


def handle_bypass_summary(resp_total, resp_brief):
    """Handle bypass summary logic."""
    if len(str(resp_total)) < TOKEN_LIMIT:
        logger.info('Outputing full data')
        return resp_total
    else:
        logger.info('Outputing brief data')
        return resp_brief

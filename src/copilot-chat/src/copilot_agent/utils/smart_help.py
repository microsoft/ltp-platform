# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Smart help method for CoPilot agent."""

import os

from ..config import COPILOT_VERSION, PROMPT_DIR
from ..utils.llmsession import LLMSession
from ..utils.utils import get_prompt_from



# generate help message for CoPilot agent
def gen_smart_help(help_msg, user_question: str, key_lst: list, SMART_HELP=True, llm_session=None) -> str:
    """Generate smart help message for CoPilot agent."""
    # dump help method
    dump_help = ''
    if isinstance(help_msg, dict):
        for key in key_lst:
            if key in help_msg:
                dump_help += help_msg[key]
                dump_help += '\n\n'
    # version
    _version = 'f0f1'
    if COPILOT_VERSION == 'f2':
        _version = 'f2'
    # capability
    if _version == 'f2':
        capability_str = help_msg['feature'] + help_msg['sku'] + help_msg['workload']
    elif _version == 'f0f1':
        capability_str = help_msg['feature']
    else:
        capability_str = help_msg['feature']

    sys_prompt = get_prompt_from(os.path.join(PROMPT_DIR, 'gen_smart_help_prompt.txt'))
    

    if SMART_HELP:
        # smart help method
        capability_promp = f'[features]\n {capability_str} \n\n'
        question_prompt = f'[user question]\n {user_question} \n\n'
        user_prompt = question_prompt + f'[reason to generate the help]\n str{key_lst} \n\n' + capability_promp
        # send to a LLM session to generate a smart help
        smart_help = llm_session.try_stream_fallback_chat(sys_prompt, user_prompt)
        final_help = smart_help
    else:
        dump_help_prompt = f'[reason to generate the help]\n {dump_help} \n\n'
        final_help = llm_session.try_stream_fallback_chat(sys_prompt, dump_help_prompt)

    return final_help

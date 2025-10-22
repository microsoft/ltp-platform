# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Smart help method for CoPilot agent."""

import os

from ..config import COPILOT_VERSION, PROMPT_DIR
from ..utils.llmsession import LLMSession
from ..utils.utils import get_prompt_from


class SmartHelp:
    """Smart help generator for CoPilot agent."""
    
    def __init__(self, help_msg: dict, llm_session: LLMSession):
        """Initialize with cached prompts."""
        self.help_msg = help_msg
        self.llm_session = llm_session
        self._version = 'f0f1' if COPILOT_VERSION != 'f2' else 'f2'
        
        # Load prompt once during initialization
        self.sys_prompt = get_prompt_from(
            os.path.join(PROMPT_DIR, 'gen_smart_help_prompt.txt')
        )
        
        # Prepare capability string based on version
        if self._version == 'f2':
            self.capability_str = (help_msg['feature'] + 
                                  help_msg['sku'] + 
                                  help_msg['workload'])
        else:
            self.capability_str = help_msg['feature']
    
    def generate(self, user_question: str, key_lst: list, 
                 smart_help: bool = True) -> str:
        """Generate smart help message."""
        # Build dump_help from keys
        dump_help = '\n\n'.join(
            self.help_msg[key] for key in key_lst 
            if key in self.help_msg
        )
        
        if smart_help:
            capability_prompt = f'[features]\n {self.capability_str} \n\n'
            question_prompt = f'[user question]\n {user_question} \n\n'
            user_prompt = (question_prompt + 
                          f'[reason to generate the help]\n {key_lst} \n\n' + 
                          capability_prompt)
            return self.llm_session.try_stream_fallback_chat(
                self.sys_prompt, user_prompt
            )
        else:
            dump_help_prompt = f'[reason to generate the help]\n {dump_help} \n\n'
            return self.llm_session.try_stream_fallback_chat(
                self.sys_prompt, dump_help_prompt
            )
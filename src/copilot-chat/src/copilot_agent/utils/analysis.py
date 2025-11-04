# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""General analysis class for CoPilot agent."""

import os

from ..config import COPILOT_VERSION, PROMPT_DIR
from ..utils.llmsession import LLMSession
from ..utils.utils import get_prompt_from
from ..utils.logger import logger


class GeneralAnalysis:
    """General analysis class for CoPilot agent."""

    def __init__(self, llm_session: LLMSession):
        """Initialize with cached prompts."""
        # Load prompt once during initialization
        self.sys_prompt = get_prompt_from(
            os.path.join(PROMPT_DIR, 'general_analysis.txt')
        )

    
    def generate(self, user_question: str, context_message: list | None) -> str:
        """Generate general analysis message."""

        question_prompt = f'[user question]\n {user_question} \n\n'
        logger.info(f'type of context_message: {type(context_message)}')
        if context_message:
            context_prompt = f'[context message]\n {" ".join(context_message)} \n\n'
        else:
            context_prompt = ''
        user_prompt = (question_prompt + context_prompt)
        return self.llm_session.try_stream_fallback_chat(
            self.sys_prompt, user_prompt
        )

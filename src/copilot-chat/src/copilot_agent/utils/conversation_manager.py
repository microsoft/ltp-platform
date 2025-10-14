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
from ..utils.utils import get_prompt_from, extract_json_dict

def contextualize_question(question: str, last_question: str | None, llm_session: LLMSession) -> str:
    """Contextualizes the current question based on the last question."""
    logger.info(f"Contextualizing question: '{question}' based on last question: '{last_question}'")
    if last_question is None:
        return question
    else:
        contextualize_prompt = get_prompt_from(os.path.join(PROMPT_DIR, 'dialouge_state_tracking', 'dst.txt'))
        user_prompt = str({
            'this_question': question,
            'last_question': last_question,
        })
        new_question_str = llm_session.chat(contextualize_prompt, user_prompt)
        new_question_dict = extract_json_dict(new_question_str, nested=False)
        if isinstance(new_question_dict, dict):
            new_question = new_question_dict.get('new_question', question)
        logger.info(f"Return: '{new_question}'")
        return new_question
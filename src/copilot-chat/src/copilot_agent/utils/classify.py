# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Question classification utilities."""

import os

from ..config import PROMPT_DIR

from ..utils.logger import logger
from ..utils.utils import get_prompt_from

class QuestionClassifier:
    def __init__(self, version, model):
        self.version = version
        self.model = model
        if self.version == 'f3':
            self.lv0_system_prompt = get_prompt_from(os.path.join(PROMPT_DIR, 'classification/f3/lv0.txt'))
            self.lv1_system_prompt = get_prompt_from(os.path.join(PROMPT_DIR, 'classification/f3/lv1.txt'))
        else:
            self.lv0_system_prompt = None
            self.lv1_system_prompt = None

    def classify_question(self, question: str) -> dict:
        """Classify the question and return a dictionary with the results."""
        question_type = {'lv0_object': None, 'lv1_concern': None}
        # classify the question, by 'Object'
        qc_resp = self.classifier_lv0(question)
        logger.info(f'Question Classification, object: {qc_resp}')
        question_type['lv0_object'] = qc_resp
        # classify the question, by 'Concern'
        qc_resp = self.classifier_lv1(question)
        logger.info(f'Question Classification, concern: {qc_resp}')
        question_type['lv1_concern'] = qc_resp
        return question_type

    def classifier_lv0(self, question: str) -> str:
        """Classify the user question into several categories."""
        if self.version == 'f3':
            resp = self.model.chat(self.lv0_system_prompt, question)
        else:
            resp = '3'  # default to 3
        return resp

    def classifier_lv1(self, question: str) -> str:
        """Classify the user question into several categories."""
        if self.version == 'f3':
            resp = self.model.chat(self.lv1_system_prompt, question)
        else:
            resp = '0'  # default to 0
        return resp

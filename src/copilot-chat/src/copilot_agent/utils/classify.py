"""Question classification utilities."""

import os

from ..config import PROMPT_DIR

from ..utils.logger import logger
from ..utils.utils import get_prompt_from

class QuestionClassifier:
    def __init__(self, version, model):
        self.version = version
        self.model = model

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
            sys_prompt = get_prompt_from(os.path.join(PROMPT_DIR, 'classification/f3/lv0.txt'))
        else:
            raise ValueError(f'Unsupported version: {self.version}')
        resp = self.model.chat(sys_prompt, question)
        return resp

    def classifier_lv1(self, question: str) -> str:
        """Classify the user question into several categories."""
        if self.version == 'f3':
            sys_prompt = get_prompt_from(os.path.join(PROMPT_DIR, 'classification/f3/lv1.txt'))
            resp = self.model.chat(sys_prompt, question)
        else:
            resp = '0'  # default to 0
        return resp

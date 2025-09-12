# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""CoPilot Turn."""

import json
import os

from .utils.logger import logger

from .config import COPILOT_VERSION, DATA_DIR, PROMPT_DIR
from .ltp import ltp_auto_reject, ltp_human_intervention, query_metadata, query_metrics, query_user_manual, query_powerbi
from .utils import (
    LLMSession,
    LTPReportProcessor,
    QuestionClassifier,
    contextualize_question,
    gen_smart_help,
    get_prompt_from,
    push_frontend_event,
)


class CoPilotTurn:
    """CoPilot Turn, handles each inquiry/response turn."""

    def __init__(self, model: LLMSession = None, verbose: bool = False) -> None:
        """Initialize."""
        if model is None:
            model = LLMSession()
        self.model = model
        self.verbose = verbose
        # Initialize version
        self._version = self._initialize_version()
        # Load help message
        self.help_msg = self.load_help_message()
        # Question Classifier
        self.classifier = QuestionClassifier(self._version, self.model)

    # entry function, processes the list of messages and returns a dictionary with the results
    def process_turn(self, messages_list: list, skip_summary: bool = False, debugging: bool = False) -> dict:
        """Process the list of messages and return a dictionary with the results."""
        if debugging:
            logger.info(f'DEBUGGING: {debugging}')
            return {'category': None, 'answer': 'DEBUGGING MODE ENABLED', 'debug': {'debugging': debugging}}

        # get contextualized question from this and last user inquiry
        push_frontend_event('<span class="text-gray-400 italic">🤔 Copilot is understanding your request...</span><br/>', replace=False)
        this_inquiry = messages_list[-1]['content']
        last_inquiry = messages_list[-3]['content'] if len(messages_list) > 2 else None
        question = contextualize_question(this_inquiry, last_inquiry)

        # classify the question to determine the solution source and method
        push_frontend_event('<span class="text-gray-400 italic">🔍 Copilot is finding the right the data source...</span><br/>', replace=False)
        question_type = self.classifier.classify_question(question)
        # objective, concern in the question
        obj, con = question_type.get('lv0_object', '3. [general]'), question_type.get('lv1_concern', '0. [others]')

        # verion f3, resolves objective 8 (Lucia Training Platform)
        if self._version == 'f3':
            if obj.count('8') > 0:
                answer, debug = self.query_ltp(question, con, skip_summary)
            elif obj.count('3') > 0:
                answer = self.gen_smart_help_general(question)
                debug = {}
            elif obj.count('9') > 0:
                help_keys = ['feature']
                answer = gen_smart_help(self.help_msg, question, help_keys)
                debug = {}
            else:
                help_keys = ['unsupported_question']
                answer = gen_smart_help(self.help_msg, question, help_keys)
                debug = {}
        else:
            # Placeholder for other version implementations
            help_keys = ['unsupported_question']
            answer = gen_smart_help(self.help_msg, question, help_keys)
            debug = {}
        return {'category': question_type, 'answer': answer, 'debug': debug}

    def query_ltp(self, question: str, con: str, skip_summary: bool) -> tuple[str, dict]:
        """Query about Lucia Training Platform."""
        # Mapping concern codes to handler functions
        handlers = {
            '1': lambda: query_metrics(question, self.help_msg, skip_summary),
            '2': lambda: query_metadata(question, self.help_msg, skip_summary),
            '3': lambda: query_user_manual(question, self.help_msg),
            '4': lambda: query_powerbi(question, self.help_msg),
            '5': lambda: ltp_auto_reject(question, self.help_msg),
            '6': lambda: ltp_human_intervention(question, self.help_msg),
        }
        for code, handler in handlers.items():
            if con.count(code) > 0:
                return handler()
        return 'unsupported concern.', {}

    # generate generic smart help message based on user input
    def gen_smart_help_general(self, question: str) -> str:
        """Generate smart help message based on user input."""
        system_prompt = get_prompt_from(os.path.join(PROMPT_DIR, 'gen_smart_help_prompt_general.txt'))
        if isinstance(self.help_msg, dict) and 'feature' in self.help_msg:
            system_prompt = system_prompt + '\n\n' + self.help_msg['feature']
        summary = self.model.try_stream_fallback_chat(system_prompt, f'question is: {question}')
        return summary

    def get_preload_dashboard(self):
        """Preload the LTP dashboard data."""
        # Configuration
        API_KEY = os.getenv("POWERBI_KEY", "")

        BASE_URL = "https://api.powerbi.com/v1.0/myorg/"
        GROUP_ID = "27c42671-0b1e-46d3-823c-acb236ff2170"  # [Workspace]: LTP_dev
        DATASET_ID = "ae03a5c8-86e2-4948-9676-9664e846de60"  # [Dataset]
        TABLES_DIRECTORY = os.path.join(DATA_DIR, "demoM3_LTP", "tables")
        OUTPUT_PATH = os.path.join(DATA_DIR, "demoM3_LTP", "report")

        # Initialize processor
        processor = LTPReportProcessor(API_KEY, BASE_URL, GROUP_ID, DATASET_ID)
        
        # Process report data
        processor.process_report_data(TABLES_DIRECTORY, OUTPUT_PATH)

    def load_help_message(self) -> dict:
        """Load the help message based on the version."""
        help_doc_path = os.path.join(PROMPT_DIR, 'help', f'infrawise_help_{self._version}.json')
        if not os.path.exists(help_doc_path):
            logger.error(f'Help doc not found: {help_doc_path}')
            raise FileNotFoundError(f'Help doc not found: {help_doc_path}')
        logger.info(f'Loading help doc: {help_doc_path}')
        with open(help_doc_path) as help_file:
            help_msg = json.load(help_file)
        return help_msg

    def _initialize_version(self) -> str:
        """Determine and set the version."""
        allowed_versions = {'f2', 'f3', 'f0f1'}
        version = COPILOT_VERSION if COPILOT_VERSION in allowed_versions else 'f3'
        logger.info(f'CoPilot - ver:{version}')
        return version

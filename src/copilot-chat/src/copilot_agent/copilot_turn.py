# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""CoPilot Turn."""

import json
import os

from .utils.logger import logger

from .config import COPILOT_VERSION, DATA_DIR, PROMPT_DIR
from .ltp import LTP
from .utils import (
    GeneralAnalysis,
    Contextualizer,
    LLMSession,
    LTPReportProcessor,
    QuestionClassifier,
    get_prompt_from,
    push_frontend_event,
    set_thread_llm_session,
    SmartHelp
)
from .agent_flow import AgentFlow, websearch_agent, story_agent, calculator_agent


class CoPilotTurn:
    """CoPilot Turn, handles each inquiry/response turn."""

    def __init__(self, llm_session: LLMSession, verbose: bool = False) -> None:
        """Initialize."""
        self.verbose = verbose
        self.llm_session = llm_session
        # Initialize version
        self._version = self._initialize_version()
        # Load help message
        self.help_msg = self.load_help_message()
        self.system_prompt_answer_general = get_prompt_from(os.path.join(PROMPT_DIR, 'gen_smart_help_prompt_general.txt'))
        self.classifier = QuestionClassifier(self._version, self.llm_session)
        self.contextualizer = Contextualizer(self.llm_session)
        self.processor = LTP(self.llm_session)
        self.smart_help = SmartHelp(self.help_msg, self.llm_session)
        self.analyzer = GeneralAnalysis(self.llm_session)
        self.agent_flow = AgentFlow([story_agent, websearch_agent, calculator_agent])

    # entry function, processes the list of messages and returns a dictionary with the results
    def process_turn(self, messages_list: list, skip_summary: bool = False, debugging: bool = False) -> dict:
        """Process the list of messages and return a dictionary with the results."""

        # Set thread-local session for push_frontend functions to use correct callback
        set_thread_llm_session(self.llm_session)

        # get from message list

        this_inquiry = messages_list[-1]['content']
        last_response = messages_list[-2]['content']['answer'] if len(messages_list) > 1 else None
        last_inquiry = messages_list[-3]['content'] if len(messages_list) > 2 else None

        # debug only
        
        if self._version == 'f4':
            push_frontend_event('<span class="text-gray-400 italic">🧠 Copilot is understanding your request...</span><br/>', replace=False)
            question_type = self.classifier.parse_question(this_inquiry, last_inquiry)
            question = question_type.get('new_question', this_inquiry)
            obj = question_type.get('lv0_object', '3. [general]')
            con = question_type.get('lv1_concern', '0. [others]')
        else:
            # get contextualized question from this and last user inquiry
            push_frontend_event('<span class="text-gray-400 italic">🤔 Copilot is understanding your request...</span><br/>', replace=False)
            question = self.contextualizer.contextualize(this_inquiry, last_inquiry)
            # classify the question to determine the solution source and method
            push_frontend_event('<span class="text-gray-400 italic">🔍 Copilot is finding the right the data source...</span><br/>', replace=False)
            question_type = self.classifier.classify_question(question)
            obj, con = question_type.get('lv0_object', '3. [general]'), question_type.get('lv1_concern', '0. [others]')

        # verion f3, f4, resolves objective 8 (Lucia Training Platform)
        push_frontend_event('<span class="text-gray-400 italic">⏳ Copilot is processing your inquiry...</span><br/>', replace=False)
        self.smart_help.llm_session = self.llm_session  # ensure processor uses the current llm_session
        self.analyzer.llm_session = self.llm_session  # ensure processor uses the current llm_session
        if self._version in ['f3', 'f4']:
            # If classification failed, treat as unsupported.
            if obj is None or con is None:
                help_keys = ['unsupported_question']
                answer = self.smart_help.generate(question, help_keys, True)
                debug = {}
            elif obj.count('8') > 0:
                answer, debug = self.query_ltp(question, con, skip_summary)
            elif obj.count('3') > 0:
                answer = self.gen_answer_general(question)
                debug = {}
            elif obj.count('9') > 0:
                help_keys = ['feature']
                answer = self.smart_help.generate(question, help_keys, True)
                debug = {}
            elif obj.count('5') > 0:
                push_frontend_event('<span class="text-gray-400 italic">🔬 Performing analysis...</span><br/>', replace=False)
                #answer = self.analyzer.generate(question, [last_response] if last_response else None)
                answer = self.agent_flow.async_execute_flow(question)
                debug = {}
            else:
                help_keys = ['unsupported_question']
                answer = self.smart_help.generate(question, help_keys, True)
                debug = {}
        else:
            # Placeholder for other version implementations
            help_keys = ['unsupported_question']
            answer = self.smart_help.generate(question, help_keys, True)
            debug = {}
        
        return {'category': question_type, 'answer': answer, 'debug': debug}

    def query_ltp(self, question: str, con: str, skip_summary: bool) -> tuple[str, dict]:
        """Query about Lucia Training Platform."""
        self.processor.llm_session = self.llm_session  # ensure processor uses the current llm_session
        # Mapping concern codes to handler functions  
        # Updated to pass llm_session to prevent singleton blocking
        handlers = {
            '1': lambda: self.processor.query_metrics(question, self.help_msg, skip_summary),
            '2': lambda: self.processor.query_metadata(question, self.help_msg, skip_summary),
            '3': lambda: self.processor.query_user_manual(question, self.help_msg),
            '4': lambda: self.processor.query_powerbi(question, self.help_msg),
            '5': lambda: self.processor.auto_reject(question, self.help_msg),
            '6': lambda: self.processor.human_intervention(question, self.help_msg),
        }
        for code, handler in handlers.items():
            if con.count(code) > 0:
                return handler()
        return 'unsupported concern.', {}

    # generate generic smart help message based on user input
    def gen_answer_general(self, question: str) -> str:
        """Generate smart help message based on user input."""
        system_prompt = self.system_prompt_answer_general
        if isinstance(self.help_msg, dict) and 'feature' in self.help_msg:
            system_prompt = system_prompt + '\n\n' + self.help_msg['feature']
        push_frontend_event('<span class="text-gray-400 italic">🌐 Accessing public information...</span><br/>', replace=False)
        summary = self.llm_session.try_stream_fallback_chat(system_prompt, f'question is: {question}')
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
        help_doc_path = os.path.join(PROMPT_DIR, 'help', f'infrawise_help.json')
        if not os.path.exists(help_doc_path):
            logger.error(f'Help doc not found: {help_doc_path}')
            raise FileNotFoundError(f'Help doc not found: {help_doc_path}')
        logger.info(f'Loading help doc: {help_doc_path}')
        with open(help_doc_path) as help_file:
            help_msg = json.load(help_file)
        return help_msg

    def _initialize_version(self) -> str:
        """Determine and set the version."""
        allowed_versions = {'f2', 'f3', 'f0f1', 'f4'}
        version = COPILOT_VERSION if COPILOT_VERSION in allowed_versions else 'f3'
        logger.info(f'CoPilot - ver:{version}')
        return version

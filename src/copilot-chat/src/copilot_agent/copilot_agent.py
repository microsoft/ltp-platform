"""CoPilot Agent."""

import json
import os

from .utils.logger import logger

from .config import COPILOT_VERSION, DATA_DIR, PROMPT_DIR
from .ltp import ltp_auto_reject, ltp_human_intervention, query_metadata, query_metrics, query_user_manual, query_powerbi
from .utils import (
    LLMSession,
    LTPReportProcessor,
    contextualize_question,
    gen_smart_help,
    get_prompt_from,
)


class CoPilotAgent:
    """CoPilot Agent."""

    def __init__(self, model: LLMSession = None, verbose: bool = False, debug: bool = False) -> None:
        """Initialize the agent."""
        if model is None:
            model = LLMSession()
        self.model = model
        self.verbose = verbose
        self._debug = debug

        # Initialize version
        self._version = self._initialize_version()

        # Load help message
        self.help_msg = self._load_help_message()

        # Preload LTP Dashboard
        self.ltp_dashboard_short, self.ltp_dashboard_long = self._initialize_dashboard()

    # entry function, processes the list of messages and returns a dictionary with the results
    def call(self, messages_list: list, skip_summary=False ,debugging=False) -> dict:
        """Process the list of messages and return a dictionary with the results."""
        call_output = {'catogory': None, 'answer': None, 'debug': None}
        
        # debugging
        if debugging:
            logger.info(f'DEBUGGING: {debugging}')
            call_output['answer'] = 'DEBUGGING MODE ENABLED'
            call_output['debug'] = {'debugging': debugging}
            return call_output

        # get the latest msg
        msg_str = messages_list[-1]
        question = msg_str['content']
        last_question = messages_list[-3]['content'] if len(messages_list) > 2 else None
        question = contextualize_question(question, last_question)

        # classify the question
        question_type = self.classify_question(question)
        obj = question_type['lv0_object']
        con = question_type['lv1_concern']
        call_output['catogory'] = question_type

        # f3: lucia training platform
        if self._version == 'f3' and obj.count('8') > 0:
            answer, debug_dict = self.query_ltp(question, con, skip_summary)
            call_output['answer'] = answer
            call_output['debug'] = debug_dict

        # general question
        elif obj.count('3') > 0:
            summary = self.gen_smart_help_general(question)
            call_output['answer'] = summary
            call_output['debug'] = None

        # ask for persona, feature
        elif obj.count('9') > 0:
            help_keys = ['feature']
            final_help = gen_smart_help(self.help_msg, question, help_keys)
            call_output['answer'] = final_help
            call_output['debug'] = None

        # else, question is classified as unsupported, go to here
        else:
            help_keys = ['unsupported_question']
            final_help = gen_smart_help(self.help_msg, question, help_keys)
            call_output['answer'] = final_help
            call_output['debug'] = None

        return call_output

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

    # classify the user question into several catogories
    def classifier_lv0(self, question: str) -> str:
        """Classify the user question into several catogories."""
        if self._version == 'f3':
            sys_prompt = get_prompt_from(os.path.join(PROMPT_DIR, 'classification/f3/lv0.txt'))
        else:
            raise ValueError(f'Unsupported version: {self._version}')
        resp = self.model.chat(sys_prompt, question)
        return resp

    # classifier lv 1: capacity or buildout
    def classifier_lv1(self, question: str) -> str:
        """Classify the user question into several catogories."""
        if self._version == 'f3':
            sys_prompt = get_prompt_from(os.path.join(PROMPT_DIR, 'classification/f3/lv1.txt'))
            resp = self.model.chat(sys_prompt, question)
        else:
            resp = '0'  # default to 0
        return resp

    def query_ltp(self, question, con, skip_summary):
        """Query about Lucia Training Platform."""
        # if DEBUG:
        #    return 'DEBUG', {}
        if con.count('1') > 0:  # solution_src: cluster_job_metrics
            answer, debug_dict = query_metrics(question, self.help_msg, skip_summary)
        elif con.count('2') > 0:  # solution_src: job_metadata
            answer, debug_dict = query_metadata(question, self.help_msg, skip_summary)
        elif con.count('3') > 0:  # solution_src: user manual
            answer, debug_dict = query_user_manual(question, self.help_msg)
        elif con.count('4') > 0:  # solution_src: dashboard
            answer, debug_dict = query_powerbi(question, self.ltp_dashboard_short, self.ltp_dashboard_long, self.help_msg)
        elif con.count('5') > 0:  # solution_src: auto reject
            answer, debug_dict = ltp_auto_reject(question, self.help_msg)
        elif con.count('6') > 0:  # solution_src: human intervention
            answer, debug_dict = ltp_human_intervention(question, self.help_msg)
        else:
            debug_dict = None
            answer = 'unsupported concern.'
        return answer, debug_dict

    # generate generic smart help message based on user input
    def gen_smart_help_general(self, question):
        """Generate smart help message based on user input."""
        system_prompt = get_prompt_from(os.path.join(PROMPT_DIR, 'gen_smart_help_prompt_general.txt'))
        if isinstance(self.help_msg, dict) and 'feature' in self.help_msg:
            system_prompt = system_prompt + '\n\n' + self.help_msg['feature']
        summary = self.model.chat(system_prompt, f'question is: {question}')
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

    def _initialize_version(self) -> str:
        """Determine and set the version."""
        version = 'f3'  # default version
        if COPILOT_VERSION == 'f2':
            version = 'f2'
        elif COPILOT_VERSION == 'f3':
            version = 'f3'
        elif COPILOT_VERSION == 'f0f1':
            version = 'f0f1'
        logger.info(f'CoPilot - ver:{version}')
        return version

    def _load_help_message(self) -> dict:
        """Load the help message based on the version."""
        help_doc_path = os.path.join(PROMPT_DIR, 'help', f'infrawise_help_{self._version}.json')
        if not os.path.exists(help_doc_path):
            logger.error(f'Help doc not found: {help_doc_path}')
            raise FileNotFoundError(f'Help doc not found: {help_doc_path}')
        logger.info(f'Loading help doc: {help_doc_path}')
        with open(help_doc_path) as help_file:
            help_msg = json.load(help_file)
        return help_msg

    def _initialize_dashboard(self) -> dict:
        """Preload the dashboard based on the version."""
        if self._version == 'f3':
            self.get_preload_dashboard() # will not replace the existing dashboard if retrieval fails
            # short version
            dashboard_file_short = os.path.join(DATA_DIR, 'demoM3_LTP', 'report', 'ltp_dashboard_data_model_short.json')
            if os.path.exists(dashboard_file_short):
                with open(dashboard_file_short, 'r') as f:
                    dashboard_short = json.load(f)
                    logger.info(f'Loaded dashboard data from {dashboard_file_short}')
            else:
                logger.error(f'Dashboard file not found: {dashboard_file_short}')
                dashboard_short = []
            # long version
            dashboard_file_long = os.path.join(DATA_DIR, 'demoM3_LTP', 'report', 'ltp_dashboard_data_model_long.json')
            if os.path.exists(dashboard_file_long):
                with open(dashboard_file_long, 'r') as f:
                    dashboard_long = json.load(f)
                    logger.info(f'Loaded dashboard data from {dashboard_file_long}')
            else:
                logger.error(f'Dashboard file not found: {dashboard_file_long}')
                dashboard_long = []

        return dashboard_short, dashboard_long

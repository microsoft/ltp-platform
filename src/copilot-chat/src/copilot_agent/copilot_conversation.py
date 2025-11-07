# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""CoPilot Conversation class, manages the inquiry/response turns for each user."""

import os
from collections import deque
import pandas as pd
from datetime import datetime, timezone
from typing import Union
import threading

from .utils.logger import logger
from .utils.authentication import AuthenticationManager
from .utils.kql_executor import KustoExecutor

from .config import AGENT_MINIMAL_ON, print_env_variables
from .copilot_turn import CoPilotTurn
from .utils.llmsession import LLMSession

HISTORY_DEPTH = int(os.getenv('COPILOT_HISTORY_DEPTH', 64))
if HISTORY_DEPTH <= 0:
    HISTORY_DEPTH = 1
elif HISTORY_DEPTH > 64:
    HISTORY_DEPTH = 64
logger.info(f'history depth is {HISTORY_DEPTH}')


class InParameters:
    """Input parameters of the agent."""
    def __init__(self, data: dict) -> None:
        """Constructor."""
        nested_data = data.get('data', {})  # Extract nested 'data' dictionary
        self.user = nested_data.get('user', None)
        self.feedback = nested_data.get('feedback', None)
        self.debugging = data.get('debugging', 'false').lower() == 'true'
        self.skip_summary = data.get('skip_summary', 'false').lower() == 'true'
        # Extract userInfo
        user_info = nested_data.get('userInfo', {})
        self.username = user_info.get('username', None)
        self.rest_token = user_info.get('restToken', None)
        # Extract messageInfo
        msg_info = nested_data.get('messageInfo', None)
        if isinstance(msg_info, dict) or msg_info is None:
            self.question_msg_info = msg_info
        else:
            self.question_msg_info = msg_info.__dict__ if hasattr(msg_info, '__dict__') else None


class OutParameters:
    """Out parameters of the agent."""
    def __init__(self, response: dict) -> None:
        """Constructor."""
        self.answer = response.get('answer', None)
        self.message_info = response.get('messageInfo', None)
        self.category = response.get('category', None)
        self.debug = response.get('debug', None)


# --- New CoPilot class (business logic only) ---
class CoPilotConversation:
    """CoPilot Conversation, manages the inquiry/response turns for each user."""
    def __init__(self, llm_session: LLMSession) -> None:
        """Initialize CoPilotConversation, message history, and authentication manager."""
        print_env_variables()
        self.copilot_turn = CoPilotTurn(llm_session=llm_session, verbose=False)
        self.msg_dict = {}  # Dictionary to store message deques per user
        self.auth_manager = AuthenticationManager()
        self.llm_session = llm_session

    def manage_conv_history(self, user_id: str, message: dict) -> None:
        """Append a message to the user's message history."""
        if user_id not in self.msg_dict:
            self.msg_dict[user_id] = deque(maxlen=HISTORY_DEPTH)
        self.msg_dict[user_id].append(message)

    def _log_message_history(self) -> None:
        """Log the length of each user's message history for auditing."""
        for user_id, messages in self.msg_dict.items():
            logger.info(f'[internal control word] [msg_dict audit]: user "{user_id}" msg_list length is {len(messages)}')

    def perform_operation(self, in_parameters: InParameters) -> OutParameters:
        """Main entry for performing an operation. Delegates to helpers for clarity."""
        logger.info('[CoPilot]: New Chat Round Started')
        user_prompt = in_parameters.user
        user_feedback = in_parameters.feedback
        skip_summary = in_parameters.skip_summary
        debugging = in_parameters.debugging
        question_msg_info = in_parameters.question_msg_info
        logger.info(f'skip_summary is {skip_summary}')
        username = in_parameters.username
        rest_token = in_parameters.rest_token

        _is_feedback = self._is_feedback_only(user_feedback, user_prompt)
        _is_question = self._is_user_question_only(user_feedback, user_prompt)

        # process
        if _is_feedback:
            user_id, conv_id, turn_id = self._extract_user_and_conv_id(question_msg_info)
            result = self._handle_feedback_only(user_id, conv_id, turn_id)
        elif _is_question:
            user_id, conv_id, turn_id = self._extract_user_and_conv_id(question_msg_info)
            # Authenticate only for user question
            if not self.auth_manager.is_authenticated(username):
                logger.info(f'User {username} not authenticated, attempting to authenticate...')
                self.auth_manager.set_authenticate_state(username, rest_token)
                if not self.auth_manager.is_authenticated(username):
                    logger.error(f'User {username} failed authentication twice. Aborting operation.')
                    result = self._handle_authenticate_failure(user_id, conv_id, turn_id)
                else:
                    logger.info(f'User {username} authenticated successfully.')
                    result = self._handle_user_question(user_id, conv_id, turn_id, user_prompt, skip_summary, debugging, question_msg_info)
            else:
                logger.info(f'User {username} authenticated successfully.')
                result = self._handle_user_question(user_id, conv_id, turn_id, user_prompt, skip_summary, debugging, question_msg_info)
        else:
            result = self._handle_empty_input()

        # collect data
        def log_message():
            if _is_feedback:
                self._log_message_data('feedback', in_parameters)
            elif _is_question:
                self._log_message_data('in', in_parameters)
            if isinstance(result, OutParameters):
                self._log_message_data('out', result)
            else:
                logger.warning(f"[CoPilot]: Skipping 'out' log; result is of type {type(result).__name__} and may not have expected attributes.")
        threading.Thread(target=log_message, daemon=True).start()
    
        return result

    def _extract_user_and_conv_id(self, question_msg_info):
        """Extract userId and convId from message info, or use defaults."""
        if question_msg_info is not None:
            user_id = question_msg_info.get('userId', 'unknown')
            conv_id = question_msg_info.get('convId', 'na')
            turn_id = question_msg_info.get('turnId', 'na')
        else:
            user_id = 'unknown'
            conv_id = 'na'
            turn_id = 'na'
        return user_id, conv_id, turn_id

    def _is_feedback_only(self, user_feedback, user_prompt):
        """Return True if only feedback is provided, not a user question."""
        return user_feedback and not user_prompt

    def _is_user_question_only(self, user_feedback, user_prompt):
        """Return True if only a user question is provided, not feedback."""
        return not user_feedback and user_prompt

    def _handle_feedback_only(self, user_id, conv_id, turn_id):
        """Handle the case where only feedback is provided."""
        logger.info('User feedback provided without a user question. No operation is required.')
        resp = self._make_skip_response(user_id, conv_id, turn_id, 'feedback_ack')
        out_parameters = OutParameters(resp)
        return out_parameters

    def _handle_empty_input(self):
        """Handle the case where both user question and feedback are empty."""
        logger.info('Both user question and feedback are empty. Aborting operation.')
        resp = {'answer': 'skip'}
        out_parameters = OutParameters(resp)
        return out_parameters

    def _handle_authenticate_failure(self, user_id, conv_id, turn_id):
        """Handle authentication failure case."""
        logger.info('User authentication failed. Aborting operation.')
        resp = self._make_skip_response(user_id, conv_id, turn_id, 'error')
        out_parameters = OutParameters(resp)

        # If LLM session is available, set up thread-local context and use push_frontend_event
        if self.llm_session:
            from .utils.push_frontend import set_thread_llm_session, push_frontend_event
            set_thread_llm_session(self.llm_session)
            error_message = '<span class="text-gray-400 italic">Unauthorized - Authentication failed</span>'
            push_frontend_event(error_message)
        
        return out_parameters

    def _handle_user_question(self, user_id, conv_id, turn_id, user_prompt, skip_summary, debugging, question_msg_info):
        """Handle the case where only a user question is provided."""
        if user_id not in self.msg_dict:
            self.msg_dict[user_id] = deque(maxlen=HISTORY_DEPTH)
        msg_user = {'role': 'user', 'content': user_prompt}
        self.manage_conv_history(user_id, msg_user)
        logger.info(f'[internal control word] [per user check] user "{user_id}" msg_list length is {len(self.msg_dict[user_id])}')
        resp = self.copilot_turn.process_turn(self.msg_dict[user_id], skip_summary, debugging)
        if not isinstance(resp, dict):
            logger.info('Unexpected response format from copilot.process_turn')
            return self.handle_unexpected_copilot_response(user_id, conv_id, turn_id)
        response_message_info = {
            'userId': user_id,
            'convId': conv_id,
            'turnId': turn_id,
            'timestamp': int(datetime.now(timezone.utc).timestamp() * 1000),
            'type': 'answer',
            'timestampUnit': 'ms',
        }
        resp['messageInfo'] = response_message_info
        debug_info = resp.get('debug')
        msg_add_kusto_resp = debug_info.get('kusto_response', None) if debug_info is not None else None
        msg_additional = {
            'benchmark_summary': resp.get('answer', None),
            'kusto_response': msg_add_kusto_resp,
        }
        msg_assistance = {'role': 'assistance', 'content': resp, 'additional_info': msg_additional}
        self.manage_conv_history(user_id, msg_assistance)
        logger.info('[CoPilot]: Chat Round Finished')
        logger.info(f'[internal control word] [per user check] user "{user_id}" msg_list length is {len(self.msg_dict[user_id])}')
        self._log_message_history()
        out_parameters = OutParameters(resp)
        return out_parameters

    def build_in_parameters(self, data: dict) -> InParameters:
        """Build and return an InParameters object from input data."""
        in_parameters = InParameters(data)
        return in_parameters

    def _log_message_data(self, inout: str, parameters: Union[InParameters, OutParameters]) -> None:
        """Log and collect data from the request or response for analytics/debugging."""
        if inout == 'in':
            user = parameters.user
            msg_info = parameters.question_msg_info
            if user:
                content = user
            else:
                content = 'na'
            meta = msg_info
            debug = 'na'
        elif inout == 'feedback':
            feedback = parameters.feedback
            msg_info = parameters.question_msg_info
            if feedback:
                content = feedback
            else:
                content = 'na'
            meta = msg_info
            debug = 'na'
        elif inout == 'out':
            content = parameters.answer
            meta = parameters.message_info
            debug = {
                'category': parameters.category,
                'debug': parameters.debug
            }
        else:
            content = 'na'
            meta = 'na'
            debug = 'na'
        endpoint = os.environ.get('CLUSTER_ID', 'empty')
        log_data = {
            'Timestamp': datetime.utcnow().isoformat() + 'Z',
            'Endpoint': endpoint,
            'Type': inout,
            'Content': content,
            'Meta': meta,
            'Debug': debug,
        }
        logger.info(f'[copilot data collection] {log_data}')
        if not AGENT_MINIMAL_ON:
            # ingest kusto table
            self.collect_data_to_kusto(log_data)

    def handle_unexpected_copilot_response(self, user_id: str, conv_id: str, turn_id: str) -> OutParameters:
        """Handle unexpected response format from copilot agent and log error."""
        error_resp = {
            'answer': 'Internal error: unexpected response format from copilot agent.',
            'messageInfo': {
                'userId': user_id,
                'convId': conv_id,
                'turnId': turn_id,
                'timestamp': int(datetime.now(timezone.utc).timestamp() * 1000),
                'type': 'error',
                'timestampUnit': 'ms',
            },
            'category': 'error',
            'debug': None
        }
        out_parameters = OutParameters(error_resp)
        return out_parameters

    def collect_data_to_kusto(self, log_data: dict):
        """Collect data to Kusto table for analytics."""
        try:
            k_cluster = os.getenv('COLLECT_DST_KUSTO_CLUSTER_URL', '')
            k_db = os.getenv('COLLECT_DST_KUSTO_DATABASE_NAME', '')
            # fixed table name to avoid causing accidental pollution of other tables
            k_table = 'CopilotAnalytics' 
            KQL = KustoExecutor(k_cluster, k_db, k_table)
            # Convert log_data dict to a single-row DataFrame
            df = pd.DataFrame([log_data])
            # Check if destination backup table exists, create if needed
            cache_exists = KQL.check_table_existence()
            logger.info(f"data collection: {k_table} table exists: {cache_exists}")
            if not cache_exists:
                # Create table with schema inferred from DataFrame
                logger.info(f"data collection: {k_table} does not exist, creating it.")
                KQL.create_table_from_dataframe(df)
            # Execute query and append results to backup table
            ingest_status = KQL.ingest_dataframe_to_kusto(df)
            logger.info(f"data collection: ingesting data into {k_table} table: {ingest_status}.")
        except Exception as e:
            logger.error(f"Exception during Kusto analytics collection: {e}")

    @staticmethod
    def _make_skip_response(user_id, conv_id, turn_id, type_str):
        """Create a standard skip/error response struct for feedback or authentication failure."""
        return {
            'answer': 'skip',
            'messageInfo': {
                'userId': user_id,
                'convId': conv_id,
                'turnId': turn_id,
                'timestamp': int(datetime.now(timezone.utc).timestamp() * 1000),
                'type': type_str,
                'timestampUnit': 'ms',
            }
        }
"""CoPilot.
version: f2
    feature:
    - query sku benchmark
    - perform RCA benchmark perf. bottleneck
version: f3
    feature:
    - Lucia Training Platform (LTP) admin/user support
"""

import os
from collections import deque
import uuid
from datetime import datetime, timezone
from typing import Union

from .utils.logger import logger
from .utils.authentication import AuthenticationManager

from .config import AGENT_MODE_LOCAL, print_env_variables
from .copilot_turn import CoPilotTurn

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
    def __init__(self):
        """Initialize CoPilotConversation, message history, and authentication manager."""
        print_env_variables()
        self.copilot = CoPilotTurn(verbose=False)
        self.msg_dict = {}  # Dictionary to store message deques per user
        self.auth_manager = AuthenticationManager()

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
        self._log_message_data('in', in_parameters)

        user_id, conv_id = self._extract_user_and_conv_id(question_msg_info)

        if self._is_feedback_only(user_feedback, user_prompt):
            return self._handle_feedback_only()

        if self._is_user_question_only(user_feedback, user_prompt):
            # Authenticate only for user question
            if not self.auth_manager.is_authenticated(username):
                logger.info(f'User {username} not authenticated, attempting to authenticate...')
                self.auth_manager.set_authenticate_state(username, rest_token)
                if not self.auth_manager.is_authenticated(username):
                    logger.error(f'User {username} failed authentication twice. Aborting operation.')
                    return self._handle_authenticate_failure()
            logger.info(f'User {username} authenticated successfully.')
            return self._handle_user_question(user_id, conv_id, user_prompt, skip_summary, debugging, question_msg_info)

        return self._handle_empty_input()

    def _extract_user_and_conv_id(self, question_msg_info):
        """Extract userId and convId from message info, or use defaults."""
        if question_msg_info is not None:
            user_id = question_msg_info.get('userId', 'unknown')
            conv_id = question_msg_info.get('convId', 'na')
        else:
            user_id = 'unknown'
            conv_id = 'na'
        return user_id, conv_id

    def _is_feedback_only(self, user_feedback, user_prompt):
        """Return True if only feedback is provided, not a user question."""
        return user_feedback and not user_prompt

    def _is_user_question_only(self, user_feedback, user_prompt):
        """Return True if only a user question is provided, not feedback."""
        return not user_feedback and user_prompt

    def _handle_feedback_only(self):
        """Handle the case where only feedback is provided."""
        logger.info('User feedback provided without a user question. No operation is required.')
        resp = {'answer': 'skip'}
        out_parameters = OutParameters(resp)
        return out_parameters

    def _handle_empty_input(self):
        """Handle the case where both user question and feedback are empty."""
        logger.info('Both user question and feedback are empty. Aborting operation.')
        resp = {'answer': 'skip'}
        return OutParameters(resp)

    def _handle_authenticate_failure(self):
        """Handle authentication failure case."""
        logger.info('User authentication failed. Aborting operation.')
        resp = {'answer': 'skip'}
        return OutParameters(resp)

    def _handle_user_question(self, user_id, conv_id, user_prompt, skip_summary, debugging, question_msg_info):
        """Handle the case where only a user question is provided."""
        if user_id not in self.msg_dict:
            self.msg_dict[user_id] = deque(maxlen=HISTORY_DEPTH)
        msg_user = {'role': 'user', 'content': user_prompt}
        self.manage_conv_history(user_id, msg_user)
        logger.info(f'[internal control word] [per user check] user "{user_id}" msg_list length is {len(self.msg_dict[user_id])}')
        resp = self.copilot.process_turn(self.msg_dict[user_id], skip_summary, debugging)
        if not isinstance(resp, dict):
            logger.info('Unexpected response format from copilot.process_turn')
            return self.handle_unexpected_copilot_response(user_id, conv_id)
        response_message_info = {
            'userId': user_id,
            'convId': conv_id,
            'turnId': str(uuid.uuid4())[:8],
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
        self._log_message_data('out', out_parameters)
        return out_parameters

    def build_in_parameters(self, data: dict) -> InParameters:
        """Build and return an InParameters object from input data."""
        in_parameters = InParameters(data)
        return in_parameters

    def _log_message_data(self, inout: str, parameters: Union[InParameters, OutParameters]) -> None:
        """Log and collect data from the request or response for analytics/debugging."""
        if inout == 'in':
            user = parameters.user
            feedback = parameters.feedback
            msg_info = parameters.question_msg_info
            if user and not feedback:
                content = user
            elif feedback and not user:
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
        log_data = {
            'inout': inout,
            'content': content,
            'meta': meta,
            'debug': debug
        }
        logger.info(f'[copilot data collection] {log_data}')

    def handle_unexpected_copilot_response(self, user_id: str, conv_id: str) -> OutParameters:
        """Handle unexpected response format from copilot agent and log error."""
        error_resp = {
            'answer': 'Internal error: unexpected response format from copilot agent.',
            'messageInfo': {
                'userId': user_id,
                'convId': conv_id,
                'turnId': str(uuid.uuid4())[:8],
                'timestamp': int(datetime.now(timezone.utc).timestamp() * 1000),
                'type': 'error',
                'timestampUnit': 'ms',
            },
            'category': 'error',
            'debug': None
        }
        out_parameters = OutParameters(error_resp)
        self._log_message_data('out', out_parameters)
        return out_parameters


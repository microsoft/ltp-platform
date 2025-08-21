"""CoPilot.

version: f0f1
    feature:
    - query cluster capacity
    - perform RCA for sub-optimal capacity
    - query new cluster buildout status
    - perform RCA for cluster buildout delay.
version: f2
    feature:
    - query sku benchmark
    - perform RCA benchmark perf. bottleneck
version: f3
    feature:
    - Lucia Training Platform (LTP) admin/user support
"""

import os
import uuid
from datetime import datetime, timezone
import argparse
from flask import Flask, jsonify, request
import threading

from .utils.logger import logger

from .config import AGENT_PORT, print_env_variables
from .copilot_agent import CoPilotAgent

HISTORY_DEPTH = int(os.getenv('COPILOT_HISTORY_DEPTH', 64))
if HISTORY_DEPTH <= 0:
    HISTORY_DEPTH = 1
elif HISTORY_DEPTH > 64:
    HISTORY_DEPTH = 64
logger.info(f'history depth is {HISTORY_DEPTH}')


class InParameters:
    """Input parameters of the agent."""

    def __init__(self, data) -> None:
        """Constructor."""
        nested_data = data.get('data', {})  # Extract nested 'data' dictionary
        self.user = nested_data.get('user', None)
        self.feedback = nested_data.get('feedback', None)
        self.debugging = data.get('debugging', 'false').lower() == 'true'
        self.skip_summary = data.get('skip_summary', 'false').lower() == 'true'
        self.question_msg_info = data.get('messageInfo', None)


class OutParameters:
    """Out parameters of the agent."""

    def __init__(self, response):
        """Constructor."""
        self.answer = response.get('answer', None)
        self.message_info = response.get('messageInfo', None)
        self.catogory = response.get('catogory', None)
        self.debug = response.get('debug', None)


def namespace_to_dict(obj):
    if isinstance(obj, argparse.Namespace):
        return {k: namespace_to_dict(v) for k, v in vars(obj).items()}
    elif hasattr(obj, '__dict__') and hasattr(obj, '__class__') and 'namespace' in str(type(obj)).lower():
        # Handle namespace objects (including those that aren't argparse.Namespace)
        return {k: namespace_to_dict(v) for k, v in vars(obj).items()}
    elif isinstance(obj, dict):
        return {k: namespace_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [namespace_to_dict(v) for v in obj]
    else:
        return obj


class CoPilot:
    """Agent's ApiServer class."""

    def __init__(self, args):
        """Constructor."""
        print_env_variables()
        self._args = args
        self.copilot = CoPilotAgent(verbose=False)
        self.msg_dict = {}  # Dictionary to store message lists per user
        
        # Configure host - use environment variable or default to localhost for security
        self.host: str = os.getenv('AGENT_HOST', '127.0.0.1')

        # Initialize Flask app
        self.app = Flask(__name__)
        self.app.add_url_rule('/copilot/api/status', view_func=self.status, methods=['GET'])
        self.app.add_url_rule('/copilot/api/operation', view_func=self.instance_operation, methods=['POST'])

    def append_message(self, user_id, message):
        """Append message into the user's message list."""
        if user_id not in self.msg_dict:
            self.msg_dict[user_id] = []
        
        self.msg_dict[user_id].append(message)
        if len(self.msg_dict[user_id]) > HISTORY_DEPTH:
            self.msg_dict[user_id] = self.msg_dict[user_id][-HISTORY_DEPTH:]

    def audit_msg_dict(self):
        """Audit the message dictionary."""
        for user_id, messages in self.msg_dict.items():
            logger.info(f'[internal control word] [msg_dict audit]: user "{user_id}" msg_lst length is {len(messages)}')

    def status(self):
        """Sample status endpoint."""
        return jsonify({"status": "running"})

    def run_http_server(self):
        """Launch HTTP server."""
        port = AGENT_PORT  # Default HTTP port
        logger.info(f'CoPilot HTTP server running on {self.host}:{port}')
        self.app.run(port=port, host=self.host)

    def perform_operation(self, in_parameters):
        """Perform operation."""
        # starting a chat round
        logger.info('[CoPilot]: New Chat Round Started')
        
        self._args = in_parameters
        user_prompt = self._args.user
        user_feedback = self._args.feedback
        skip_summary = self._args.skip_summary
        debugging = self._args.debugging
        question_msg_info = self._args.question_msg_info
        self.collect_data('in', in_parameters)
        logger.info(f'skip_summary is {skip_summary}')
        
        # read question message meta info
        user_id = question_msg_info.userId if question_msg_info is not None else 'unknown'
        conv_id = question_msg_info.convId if question_msg_info is not None else 'na'

        # if feedback, return received and end
        if user_feedback and not user_prompt:
            logger.info('User feedback provided without a user question. Aborting operation.')
            resp = {'answer': 'feedback received', 'message_info': question_msg_info}
            out_parameters = OutParameters(resp)
            return out_parameters

        elif not user_feedback and user_prompt:
            # Get or create message list for this user
            if user_id not in self.msg_dict:
                self.msg_dict[user_id] = []

            # append the user question into the user's msg_lst, as user role
            msg_user = {'role': 'user', 'content': user_prompt}
            self.append_message(user_id, msg_user)
            logger.info(f'[internal control word] [per user check] user "{user_id}" msg_lst length is {len(self.msg_dict[user_id])}')

            # call copilot with user's specific message history
            resp = self.copilot.call(self.msg_dict[user_id], skip_summary, debugging)
            # Check if response has expected structure
            if not isinstance(resp, dict):
                logger.info('Unexpected response format from copilot.call')
                return None
            response_message_info = {
                'userId': user_id,
                'convId': conv_id,
                'turnId': str(uuid.uuid4())[:8],
                'timestamp': int(datetime.now(timezone.utc).timestamp() * 1000),  # milliseconds
                'type': 'answer',
                'timestampUnit': 'ms',
            }
            resp['messageInfo'] = response_message_info

            # append the response into the user's msg_lst, as assistance role
            debug_info = resp.get('debug')
            msg_add_kusto_resp = debug_info.get('kusto_response', None) if debug_info is not None else None
            msg_additional = {
                'benchmark_summary': resp.get('answer', None),
                'kusto_response': msg_add_kusto_resp,
            }
            msg_assistance = {'role': 'assistance', 'content': resp, 'additional_info': msg_additional}
            self.append_message(user_id, msg_assistance)
        
            logger.info('[CoPilot]: Chat Round Finished')
            logger.info(f'[internal control word] [per user check] user "{user_id}" msg_lst length is {len(self.msg_dict[user_id])}')
            self.audit_msg_dict()
            # assemble output
            out_parameters = OutParameters(resp)
            self.collect_data('out', out_parameters)
            return out_parameters

        else:
            logger.info('Both user question and feedback are empty. Aborting operation.')
            resp = {
                'answer': 'Both user question and feedback are empty. Aborting operation.',
                'messageInfo': None,
            }
            return OutParameters(resp)

    def build_in_parameters(self, data):
        """Build input parameters."""
        in_parameters = InParameters(data)  # Pass the dictionary directly
        return in_parameters

    def collect_data(self, inout, parameters):
        """Collect data from the request."""
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
                'category': parameters.catogory,
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

    def instance_operation(self):
        """Handle the /copilot/api/operation endpoint."""
        logger.info("Received request at /copilot/api/operation")
        try:
            # Parse input parameters from the request
            data = request.get_json()
            in_parameters = self.build_in_parameters(data)

            # Call the perform_operation function
            out_parameters = self.perform_operation(in_parameters)

            # Return the data as a JSON response
            response = {
                "status": "success",
                "data": out_parameters.__dict__
            }
            return jsonify(response), 200
        except Exception as e:
            logger.info(f"Error handling copilot/api/operation: {e}")  # Use logger.exception for traceback
            return jsonify({"status": "error", "message": str(e)}), 500

    def run(self):
        """Run the SltCoPilot server."""
        http_thread = threading.Thread(target=self.run_http_server)
        http_thread.start()
        http_thread.join()

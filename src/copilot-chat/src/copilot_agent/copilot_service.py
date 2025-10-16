# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""CoPilot Service (Flask app and endpoints)"""

import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
from flask import Response, stream_with_context
import json
import queue

from .copilot_conversation import CoPilotConversation

from .utils.logger import logger
from .utils.llmsession import LLMSession

from .config import AGENT_PORT, AGENT_MODE_LOCAL


# --- New CoPilotAPI class (Flask app setup and endpoints) ---
class CoPilotService:
    """Flask app and endpoint manager for CoPilot."""
    def __init__(self):
        """
        Initialize the CoPilotAPI with a CoPilot instance, set up Flask app and endpoints.

        Args:
            copilot: Instance of CoPilot business logic class.
        """
        self.sessions = {}
        self.host = os.getenv('AGENT_HOST', '127.0.0.1')
        self.app = Flask(__name__)
        self.app.add_url_rule('/copilot/api/status', view_func=self.status, methods=['GET'])
        self.app.add_url_rule('/copilot/api/operation', view_func=self.instance_operation, methods=['POST'])
        self.app.add_url_rule('/copilot/api/operation/stream', view_func=self.stream_operation, methods=['POST'])

        # If running in local agent mode, enable CORS to allow local testing from dev frontends.
        if AGENT_MODE_LOCAL:
            try:
                CORS(self.app)
                logger.info('CORS enabled for local testing (AGENT_MODE_LOCAL)')
            except Exception as e:
                logger.warning(f'Failed to enable CORS for local testing: {e}')

    def status(self):
        """GET endpoint for health/status check."""
        return jsonify({"status": "running"})

    def get_or_create_session(self, user_id, conv_id, llm_session):
        """Retrieve or create a copilot_conversation for the given userId and convId."""
        session_key = f"{user_id}_{conv_id}"
        if session_key not in self.sessions:
            self.sessions[session_key] = CoPilotConversation(llm_session)
        return self.sessions[session_key]

    def instance_operation(self):
        """POST endpoint to handle copilot operations."""
        logger.info("Received request at /copilot/api/operation")
        try:
            data = request.get_json()
            user_id = data['data']['messageInfo']['userId']
            conv_id = data['data']['messageInfo']['convId']
            llm_session = LLMSession()
            copilot_conversation = self.get_or_create_session(user_id, conv_id, llm_session)

            
            in_parameters = copilot_conversation.build_in_parameters(data)
            out_parameters = copilot_conversation.perform_operation(in_parameters)
            response = {
                "status": "success",
                "data": out_parameters.__dict__
            }
            return jsonify(response), 200
        except Exception as e:
            logger.info(f"Error handling copilot/api/operation: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    def stream_operation(self):
        """POST endpoint to stream operation output as chunked text (SSE-like).

        The endpoint accepts the same JSON payload as the normal operation endpoint.
        It sets a module-level callback in the summary module so streaming chunks are
        forwarded to the HTTP response. This avoids changing many internal call chains.
        """
        logger.info("Received request at /copilot/api/operation/stream")

        # Create queue BEFORE the callback function
        q = queue.Queue()

        def on_chunk(chunk: str):
            # put chunk into queue for streaming response
            q.put(chunk)
        
        try:
            data = request.get_json()
            user_id = data['data']['messageInfo']['userId']
            conv_id = data['data']['messageInfo']['convId']
            llm_session = LLMSession()  # Create a new LLM session
            llm_session.set_instance_stream_callback(on_chunk)
            copilot_conversation = self.get_or_create_session(user_id, conv_id, llm_session)  # Pass llm_session
            
            # CRITICAL: Update the llm_session in the conversation for subsequent requests
            # The copilot_turn needs to use the NEW llm_session with the NEW callback
            copilot_conversation.llm_session = llm_session
            copilot_conversation.copilot_turn.llm_session = llm_session
        except KeyError as e:
            logger.error(f"Missing key in JSON body for stream_operation: {e}")
            return jsonify({"status": "error", "message": f"Missing key: {e}"}), 400
        except Exception as e:
            logger.error(f"Failed to parse JSON body for stream_operation: {e}")
            return jsonify({"status": "error", "message": "invalid json"}), 400



        def worker():
            # Use the llm_session from the copilot_conversation
            try:
                in_parameters = copilot_conversation.build_in_parameters(data)
                # Reuse the llm_session passed to the conversation
                copilot_conversation.perform_operation(in_parameters)
            except Exception as e:
                logger.error(f"Error during streaming operation worker: {e}")
                import traceback
                logger.error(traceback.format_exc())
                q.put(json.dumps({'error': str(e)}))
            finally:
                # signal end of stream
                q.put(None)

        def event_stream():
            # start worker thread
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            # yield chunks as they arrive
            while True:
                item = q.get()
                if item is None:
                    break
                # SSE-style framing: prefix each line with 'data:' to support multi-line payloads
                text = str(item)
                lines = text.splitlines()
                if len(lines) == 0:
                    yield "data: \n\n"
                else:
                    for ln in lines:
                        yield f"data: {ln}\n"
                    # event delimiter
                    yield "\n"
            # final event
            yield "event: done\n\n"

        return Response(stream_with_context(event_stream()), mimetype='text/event-stream')

    def run_http_server(self):
        """Start the Flask HTTP server."""
        port = AGENT_PORT
        logger.info(f'CoPilot HTTP server running on {self.host}:{port}')
        self.app.run(port=port, host=self.host)

    def run(self):
        """Start the HTTP server in a separate thread."""
        http_thread = threading.Thread(target=self.run_http_server)
        http_thread.start()
        http_thread.join()

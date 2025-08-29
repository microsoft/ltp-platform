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
from flask import Flask, jsonify, request
import threading

from .copilot_conversation import CoPilotConversation

from .utils.logger import logger

from .config import AGENT_PORT


# --- New CoPilotAPI class (Flask app setup and endpoints) ---
class CoPilotService:
    """Flask app and endpoint manager for CoPilot."""
    def __init__(self, copilot_conversation: CoPilotConversation):
        """
        Initialize the CoPilotAPI with a CoPilot instance, set up Flask app and endpoints.

        Args:
            copilot: Instance of CoPilot business logic class.
        """
        self.copilot_conversation = copilot_conversation
        self.host = os.getenv('AGENT_HOST', '127.0.0.1')
        self.app = Flask(__name__)
        self.app.add_url_rule('/copilot/api/status', view_func=self.status, methods=['GET'])
        self.app.add_url_rule('/copilot/api/operation', view_func=self.instance_operation, methods=['POST'])

    def status(self):
        """GET endpoint for health/status check."""
        return jsonify({"status": "running"})

    def instance_operation(self):
        """POST endpoint to handle copilot operations."""
        logger.info("Received request at /copilot/api/operation")
        try:
            data = request.get_json()
            in_parameters = self.copilot_conversation.build_in_parameters(data)
            out_parameters = self.copilot_conversation.perform_operation(in_parameters)
            response = {
                "status": "success",
                "data": out_parameters.__dict__
            }
            return jsonify(response), 200
        except Exception as e:
            logger.info(f"Error handling copilot/api/operation: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

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

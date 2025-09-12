import json

from ..utils.logger import logger
from ..utils.llmsession import LLMSession

def push_frontend_event(content: str, replace: bool = False):
    """Push an event to the frontend."""
    # If streaming is active, push only the appended content as a JSON "append" event
    try:
        cb = LLMSession._global_stream_callback
        if cb:
            if replace:
                cb(content)
            else:
                cb(json.dumps({"type": "append", "text": content}))
    except Exception as e:
        logger.debug(f"Failed to stream appended content: {e}")


def push_frontend_meta(message_info: dict):
    """Push a metadata event (messageInfo) to the frontend so client can attach turnId before answer arrives."""
    try:
        cb = LLMSession._global_stream_callback
        if cb:
            cb(json.dumps({"type": "meta", "messageInfo": message_info}))
    except Exception as e:
        logger.debug(f"Failed to stream meta event: {e}")
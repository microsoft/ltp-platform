import json
import threading

from ..utils.logger import logger
from ..utils.llmsession import LLMSession

# Thread-local storage to track the current LLM session for this request
_thread_local = threading.local()

def set_thread_llm_session(llm_session):
    """Set the LLM session for the current thread (for streaming context)."""
    _thread_local.llm_session = llm_session

def get_thread_llm_session():
    """Get the LLM session for the current thread."""
    return getattr(_thread_local, 'llm_session', None)

def push_frontend_event(content: str, replace: bool = False):
    """Push an event to the frontend."""
    # Try to use thread-local LLM session first (for per-user streaming)
    # Fall back to global callback for backward compatibility
    try:
        cb = None
        thread_session = get_thread_llm_session()
        if thread_session and hasattr(thread_session, '_instance_stream_callback'):
            cb = thread_session._instance_stream_callback
        
        if not cb:
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
        cb = None
        thread_session = get_thread_llm_session()
        if thread_session and hasattr(thread_session, '_instance_stream_callback'):
            cb = thread_session._instance_stream_callback
        
        if not cb:
            cb = LLMSession._global_stream_callback
            
        if cb:
            cb(json.dumps({"type": "meta", "messageInfo": message_info}))
    except Exception as e:
        logger.debug(f"Failed to stream meta event: {e}")
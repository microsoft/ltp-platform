# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Language model session class."""

import os
import time
import openai
from ..utils.logger import logger

class LLMSession:
    """A class to interact with the Azure OpenAI model."""
    # Global stream callback that external code (server endpoint) can set
    _global_stream_callback = None

    def __init__(self):
        # Env Var to set the LLM provider, accepted values are 'openai' or 'azure'
        self.provider = os.environ.get("COPILOT_LLM_PROVIDER")
        logger.info(f'COPILOT LLM Endpoint Provider: {self.provider}')
        self.azure_api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.endpoint = os.environ.get("COPILOT_LLM_ENDPOINT")
        self.embedding_url = os.environ.get("COPILOT_EMBEDDING_URL")
        self.model_name = os.environ.get("COPILOT_LLM_MODEL")
        self.model_version = os.environ.get("COPILOT_LLM_VERSION")
        self.embedding_model_name = os.environ.get("COPILOT_EMBEDDING_MODEL")
        if self.provider == "openai":
            self.model = openai.OpenAI(
                base_url=self.endpoint,
                api_key=self.openai_api_key
            )
            self.embedding_model = openai.OpenAI(
                base_url=self.embedding_url,
                api_key=self.openai_api_key
            )
        elif self.provider == "azure":
            self.model = openai.AzureOpenAI(
                azure_endpoint=self.endpoint,
                api_key=self.azure_api_key,
                api_version=self.model_version
            )
            self.embedding_model = openai.AzureOpenAI(
                azure_endpoint=self.embedding_url,
                api_key=self.azure_api_key,
                api_version=self.model_version
            )
        else:
            logger.error(f'Unsupported LLM provider: {self.provider}')
            raise ValueError(f'Unsupported LLM provider: {self.provider}')

    def chat(self, system_prompt, user_prompt):
        """Chat with the language model."""
        msg = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        max_retries = 5
        backoff = 2  # Initial backoff in seconds

        for attempt in range(max_retries):
            try:
                if self.provider == "azure":
                    response = self.model.chat.completions.create(
                        model=self.model_name,
                        messages=msg,
                        max_completion_tokens=10000
                    )
                    return response.choices[0].message.content
                elif self.provider == "openai":
                    response = self.model.chat.completions.create(
                        model=self.model_name,
                        messages=msg,
                        max_tokens=10000
                    )
                    return response.choices[0].message.content
                else:
                    logger.error(f"Unsupported LLM provider in chat: {self.provider}")
                    break
            except Exception as e:
                if "429" in str(e):
                    logger.warning(f"429 Too Many Requests: Retrying in {backoff} seconds (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(backoff)
                    backoff *= 2  # Exponential backoff
                else:
                    logger.error(f"Unexpected error: {e}")
                    break

        # If retries are exhausted, return a meaningful fallback string
        logger.error("Exceeded maximum retries for chat request.")
        return "The system is currently overloaded. Please try again later."

    def get_embedding(self, text):
        """Get embedding for the given text using the embedding model."""
        if not self.embedding_model:
            logger.error("Embedding model is not configured.")
            raise ValueError("Embedding model is not configured.")

        try:
            if self.provider == "azure":
                response = self.embedding_model.embeddings.create(
                    model=self.embedding_model_name,
                    input=text
                )
                return response.data[0].embedding
            elif self.provider == "openai":
                response = self.embedding_model.embeddings.create(
                    model=self.embedding_model_name,
                    input=text
                )
                return response.data[0].embedding
            else:
                logger.error(f"Unsupported LLM provider in get_embedding: {self.provider}")
                raise ValueError(f"Unsupported LLM provider: {self.provider}")
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            raise

    def stream_chat(self, system_prompt, user_prompt):
        """Stream chat responses from the language model as a generator yielding text chunks.

        This method works with both the OpenAI and Azure OpenAI clients used in this project.
        It yields incremental text chunks as they arrive from the SDK's streaming API. Callers
        can iterate over the generator to provide a streaming UX. If streaming fails after
        retries, a single fallback message chunk will be yielded.
        """
        msg = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        max_retries = 5
        backoff = 2  # Initial backoff in seconds

        for attempt in range(max_retries):
            try:
                # Start streaming from the provider. The SDK returns an iterator of events.
                if self.provider == "azure":
                    stream = self.model.chat.completions.create(
                        model=self.model_name,
                        messages=msg,
                        max_completion_tokens=10000,
                        stream=True
                    )
                elif self.provider == "openai":
                    stream = self.model.chat.completions.create(
                        model=self.model_name,
                        messages=msg,
                        max_tokens=10000,
                        stream=True
                    )
                else:
                    logger.error(f"Unsupported LLM provider in stream_chat: {self.provider}")
                    break

                # Iterate over streaming events and yield text increments.
                # The exact shape of events can vary between SDK versions, so try a few access patterns.
                full = ''
                for event in stream:
                    chunk = None
                    try:
                        # event may be a mapping-like object or an SDK object with attributes
                        # Try dict-style access first
                        if isinstance(event, dict):
                            choices = event.get('choices')
                        else:
                            choices = getattr(event, 'choices', None)

                        if choices:
                            # Support both mapping and attribute access for choice and delta
                            choice = choices[0]

                            # choice might be a dict or an object
                            if isinstance(choice, dict):
                                delta = choice.get('delta', {})
                                chunk = delta.get('content')
                            else:
                                # object-like access
                                delta = getattr(choice, 'delta', None)
                                if delta is not None:
                                    # delta could be a mapping or an object
                                    if isinstance(delta, dict):
                                        chunk = delta.get('content')
                                    else:
                                        chunk = getattr(delta, 'content', None)
                    except Exception:
                        # Be resilient to unexpected event shapes
                        chunk = None

                    if chunk:
                        # accumulate to reconstruct full text and yield the full snapshot
                        full += chunk
                        # call global callback if configured (external subscribers)
                        try:
                            cb = LLMSession._global_stream_callback
                            if cb:
                                cb(full)
                        except Exception:
                            logger.debug('Global stream callback failed')
                        yield full

                # If stream finishes without exception, stop generator normally
                return

            except Exception as e:
                if "429" in str(e):
                    logger.warning(f"429 Too Many Requests: Retrying in {backoff} seconds (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(backoff)
                    backoff *= 2  # Exponential backoff
                else:
                    logger.error(f"Unexpected error in stream_chat: {e}")
                    break

        # If retries are exhausted, yield a meaningful fallback chunk so callers can display something
        logger.error("Exceeded maximum retries for chat stream request.")
        yield "The system is currently overloaded. Please try again later."

    @classmethod
    def set_global_stream_callback(cls, cb):
        cls._global_stream_callback = cb

    @classmethod
    def clear_global_stream_callback(cls):
        cls._global_stream_callback = None

    def try_stream_fallback_chat(self, system_prompt: str, user_prompt: str) -> str:
        """Try streaming the response (if a global stream callback is set) and fall back to the blocking chat call.

        Returns the final aggregated text.
        """
        try:
            if getattr(LLMSession, '_global_stream_callback', None):
                logger.info('LLMSession: streaming via try_stream_fallback_chat')
                last = ''
                for snapshot in self.stream_chat(system_prompt, user_prompt):
                    if snapshot:
                        last = snapshot
                return last
            else:
                logger.info('LLMSession: non-streaming via try_stream_fallback_chat')
                return self.chat(system_prompt, user_prompt)
        except Exception as e:
            logger.error(f"try_stream_fallback_chat failed: {e}. Falling back to non-streaming chat.")
            return self.chat(system_prompt, user_prompt)
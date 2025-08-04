"""Language model session class."""

import os
import time
from openai import AzureOpenAI
from ..utils.logger import logger

class LLMSession:
    """A class to interact with the Azure OpenAI model."""

    def __init__(self):
        logger.info(f'using env var: AZURE_OPENAI_API_KEY')
        self.api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = os.environ.get("COPILOT_LLM_ENDPOINT")
        self.model_name = os.environ.get("COPILOT_LLM_MODEL")
        self.model_version = os.environ.get("COPILOT_LLM_VERSION")
        self.model = AzureOpenAI(
            azure_endpoint=self.azure_endpoint,
            api_key=self.api_key,
            api_version=self.model_version
        )

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
                response = self.model.chat.completions.create(
                    model=self.model_name,
                    messages=msg,
                    max_completion_tokens=10000
                )
                return response.choices[0].message.content
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
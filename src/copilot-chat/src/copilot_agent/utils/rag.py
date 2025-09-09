# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""A generic RAG system for query generation (e.g., KQL, DAX) using LlamaIndex and a custom LLM."""

from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.llms import LLM
from llama_index.core.llms.llm import ChatMessage, MessageRole 
from llama_index.core.base.llms.types import ChatResponse, LLMMetadata
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.core.readers.base import Document
from typing import List, Optional
from ..utils.logger import logger

# --- 1. Import your Custom Model ---
from ..utils.llmsession import LLMSession

# --- 2. Custom LlamaIndex Wrappers for your LLMSession Methods ---
# These classes adapt your LLMSession's methods to LlamaIndex's expected interfaces.

class MyEmbedding(BaseEmbedding):
    """
    Adapts LLMSession's 'get_embedding' method to LlamaIndex's 'BaseEmbedding' interface.
    This class can be reused as embeddings are generally language-agnostic.
    """
    model: LLMSession 

    def __init__(self, model_instance: LLMSession, **kwargs):
        super().__init__(model=model_instance, **kwargs)

    def _get_query_embedding(self, query: str) -> List[float]:
        return self.model.get_embedding(query)

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self.model.get_embedding(text)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embedding(text)

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [self.model.get_embedding(t) for t in texts]

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._get_text_embeddings(texts)


class QueryGeneratingChatLLM(LLM):
    """
    Adapts LLMSession's 'chat' method to LlamaIndex's 'LLM' interface for chat responses.
    This version is parameterized to accept a specific system prompt for query generation.
    """
    # Define fields at the class level for Pydantic to handle initialization
    model: LLMSession 
    specific_system_prompt: str 

    def __init__(self, model_instance: LLMSession, specific_system_prompt: str, **kwargs):
        super().__init__(model=model_instance, specific_system_prompt=specific_system_prompt, **kwargs)

    @property
    def metadata(self) -> LLMMetadata: # Return type changed to LLMMetadata
        # Now return an instance of LLMMetadata with required fields
        return LLMMetadata(
            context_window=4096, # Example value, adjust as per your model's actual context window
            num_output=256, # Example value, adjust based on typical output length
            is_chat_model=True, # Assuming your LLMSession is a chat model
            model_name=self.model.__class__.__name__ if self.model else "CustomQueryGenerator",
            # prompt_token_cost_per_1k and completion_token_cost_per_1k are optional in LLMMetadata
            # and can be omitted or set if you have specific cost tracking.
            # prompt_token_cost_per_1k=0.0, 
            # completion_token_cost_per_1k=0.0,
        )

    @property
    def tokenizer(self):
        return None

    def chat(self, messages: List[ChatMessage], **kwargs) -> ChatResponse:
        system_prompt = self.specific_system_prompt 
        user_prompt = next((m.content for m in messages if m.role == MessageRole.USER), "")
        response_text = self.model.chat(system_prompt, user_prompt)
        return ChatResponse(message=ChatMessage(role=MessageRole.ASSISTANT, content=response_text))

    async def achat(self, messages: List[ChatMessage], **kwargs) -> ChatResponse:
        return self.chat(messages, **kwargs)

    def complete(self, prompt: str, **kwargs) -> str:
        return self.model.chat(self.specific_system_prompt, prompt)

    async def acomplete(self, prompt: str, **kwargs) -> str:
        return self.complete(prompt, **kwargs)

    def _raise_streaming_not_supported(self, operation: str):
        raise NotImplementedError(f"{operation} not supported with this implementation.")

    def stream_chat(self, messages: List[ChatMessage], **kwargs):
        self._raise_streaming_not_supported("Streaming chat")
    
    async def astream_chat(self, messages: List[ChatMessage], **kwargs):
        self._raise_streaming_not_supported("Asynchronous streaming chat")

    def stream_complete(self, prompt: str, **kwargs):
        self._raise_streaming_not_supported("Streaming complete")

    async def astream_complete(self, prompt: str, **kwargs):
        self._raise_streaming_not_supported("Asynchronous streaming complete")


# --- 3. The QueryGeneratorRAG Class ---

class QueryGeneratorRAG:
    """
    A class to encapsulate a generic RAG system for query generation,
    handling initialization and query generation for various languages.
    """
    def __init__(self, 
                 llm_session_instance: LLMSession, 
                 query_language_system_prompt: str,
                 data_source_schema_description: List[str]):
        """
        Initializes the Query Generator RAG System.
        
        Args:
            llm_session_instance: An instance of your LLMSession model.
            query_language_system_prompt: The system prompt to guide the LLM
                                          to generate the desired query language (e.g., KQL, DAX).
            data_source_schema_description: A list of strings describing the data source's schema
                                            and relevant operations for the target query language.
        """
        self.llm_session = llm_session_instance
        self.query_language_system_prompt = query_language_system_prompt
        self.data_source_schema_description = data_source_schema_description
        
        logger.info(f"\n===== Initializing Query Generator RAG for a new language =====")

        # Configure LlamaIndex to use your custom models globally
        Settings.llm = QueryGeneratingChatLLM(
            model_instance=self.llm_session, 
            specific_system_prompt=self.query_language_system_prompt
        )
        Settings.embed_model = MyEmbedding(model_instance=self.llm_session)
        logger.info("LlamaIndex configured with custom LLM and Embedding models.")

        # Load and index the data source schema descriptions
        self._load_and_index_data()
        logger.info("Query Generator RAG initialized and ready!")

    def _load_and_index_data(self):
        """Internal method to load documents and create the vector index."""
        documents = [Document(text=desc) for desc in self.data_source_schema_description]
        logger.info(f"Loaded {len(documents)} source documents (describing data schema/operations).")
        
        logger.info("Creating vector index from data source descriptions...")
        self.index = VectorStoreIndex.from_documents(documents)
        logger.info("Vector index created successfully!")
        
        self.query_engine = self.index.as_query_engine()
        logger.info("Query engine for query generation ready!")

    def generate_query(self, user_question: str) -> str:
        """
        Generates a query (e.g., KQL, DAX) based on the user's natural language question.
        """
        logger.info(f"\n===== Generating Query for: '{user_question}' =====")
        response = self.query_engine.query(user_question)
        
        generated_query = str(response)
        return generated_query

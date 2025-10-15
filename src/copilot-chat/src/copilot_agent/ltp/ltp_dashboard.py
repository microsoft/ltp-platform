# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""LTP Dashboard module for LTP component, handling dashboard related inquiries."""

from __future__ import annotations

import os
import json
import re

from ..utils.llmsession import LLMSession
from ..utils.rag import QueryGeneratorRAG
from ..utils.logger import logger

from ..config import DATA_DIR, AGENT_MINIMAL_ON


# Document preparation utilities
class DocPrepare:
    @staticmethod
    def get_txt_as_string(filepath):
        try:
            with open(filepath, 'r') as file:
                return file.read()
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
            return ''
        except Exception as e:
            logger.error(f"Error reading file {filepath}: {e}")
            return ''

    @staticmethod
    def get_txt_as_list_hashtag(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            sections = content.split('##')
            # Keep only sections not starting with '#' (do not strip whitespace)
            result = [s for s in sections if s and not s.startswith('#')]
            return result
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
            return []
        except Exception as e:
            logger.error(f"Error reading file {filepath}: {e}")
            return []

    @staticmethod
    def get_json_as_list(folder):
        try:
            json_files = [f for f in os.listdir(folder) if f.endswith('.json')]
        except FileNotFoundError:
            logger.error(f"Folder not found: {folder}")
            return []
        except Exception as e:
            logger.error(f"Error listing folder {folder}: {e}")
            return []
        json_data = []
        for json_file in json_files:
            json_path = os.path.join(folder, json_file)
            try:
                with open(json_path, 'r') as file:
                    # Read the file as a string
                    content = file.read()
                    json_data.append(content)
            except FileNotFoundError:
                logger.error(f"File not found: {json_path}")
            except Exception as e:
                logger.error(f"Error reading file {json_path}: {e}")
        return json_data

    @staticmethod
    def get_txt_as_list(filepath):
        try:
            with open(filepath, 'r') as file:
                return file.readlines()
        except FileNotFoundError:
            logger.error(f"File not found: {filepath}")
            return []
        except Exception as e:
            logger.error(f"Error reading file {filepath}: {e}")
            return []

# Singleton class for KQL RAG instance
class KQLRAGSingleton:

    _instance = None

    @classmethod
    def get_instance(cls):
        return cls._instance

    @classmethod
    def _init_instance(cls):
        KUSTO_SAMPLE_FILE = os.path.join(DATA_DIR, 'LTP/rag/kusto/_examples.txt')
        KUSTO_SAMPLE_DATA_FILE = os.path.join(DATA_DIR, 'LTP/rag/kusto/_examples_from_data.txt')
        KUSTO_TABLE_DIR = os.path.join(DATA_DIR, 'LTP/rag/kusto')
        KUSTO_OPERATOR_FILE = os.path.join(DATA_DIR, 'LTP/rag/kusto/_operators.txt')
        KUSTO_RELATIONSHIP_FILE = os.path.join(DATA_DIR, 'LTP/rag/kusto/_relationships.txt')
        KUSTO_KNOWLEDGE_FILE = os.path.join(DATA_DIR, 'LTP/rag/kusto/_knowledge.txt')
        my_llm_session = LLMSession()
        # prompt
        kql_sample_prompt = DocPrepare.get_txt_as_string(KUSTO_SAMPLE_FILE)
        kql_system_prompt = f"You are a KQL query generator. Based on the user's question and the provided context about available data, generate a Kusto Query Language (KQL) query. Only output the KQL query, nothing else. If you cannot generate a KQL query, output a comment indicating that.\n\n{kql_sample_prompt}\n\n"
        
        # doc
        kql_table_docs = DocPrepare.get_json_as_list(KUSTO_TABLE_DIR)
        kql_operator_docs = DocPrepare.get_txt_as_list(KUSTO_OPERATOR_FILE)
        kql_relationship_docs = DocPrepare.get_txt_as_list(KUSTO_RELATIONSHIP_FILE)
        kql_sample_docs = DocPrepare.get_txt_as_list_hashtag(KUSTO_SAMPLE_FILE)
        kql_sample_docs_data = DocPrepare.get_txt_as_list_hashtag(KUSTO_SAMPLE_DATA_FILE)
        kql_knowledge_docs = DocPrepare.get_txt_as_list(KUSTO_KNOWLEDGE_FILE)
        kql_schema_docs = kql_table_docs + kql_operator_docs + kql_sample_docs + kql_sample_docs_data + kql_knowledge_docs
        if AGENT_MINIMAL_ON:
            kql_schema_docs = []
        logger.info(f'length of kql_schema_docs: {len(kql_schema_docs)}')
        for doc in kql_schema_docs:
            logger.info(doc[:50])
        return QueryGeneratorRAG(
            llm_session_instance=my_llm_session,
            query_language_system_prompt=kql_system_prompt,
            data_source_schema_description=kql_schema_docs
        )

# Eagerly initialize the singleton instance at module load
KQLRAGSingleton._instance = KQLRAGSingleton._init_instance()

def query_generation_kql(question):
    logger.info("Setting up KQL Query Generator...")
    kql_generator = KQLRAGSingleton.get_instance()
    output = kql_generator.generate_query(question)
    query, status = clean_query(output)
    return query, status

def clean_query(query):
    if not isinstance(query, str):
        return '', -2

    # Check for code block with language (kql or dax)
    code_block_match = re.search(r'```(?:kql|dax)?\s*([\s\S]*?)\s*```', query, re.IGNORECASE)
    if code_block_match:
        query_clean = code_block_match.group(1).strip()
        return query_clean, 0

    # Check if starts with comment
    if query.strip().startswith('//'):
        return query, -1

    return query, -3
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Init file for utils module."""

from .authentication import AuthenticationManager
from .classify import QuestionClassifier
from .conversation_manager import Contextualizer
from .dcw import dcw_parser, extract_dcw_from_history, gen_dcw, parse_and_align_dcw
from .kql_executor import KustoExecutor
from .logger import (
    logger,
)
from .llmsession import (
    LLMSession,
)
from .math import (
    find_value_in_json,
    gen_size_range,
)
from .message import (
    get_last_value,
)
from .openpai import (
    execute_openpai_query,
)
from .powerbi import (
    LTPReportProcessor,
    PowerBIClient,
)
from .promql import (
    execute_promql_query,
)
from .push_frontend import(
    push_frontend_event,
    set_thread_llm_session,
)
from .query import (
    gen_kusto_query_fallback_pseudo,
    gen_kusto_query_pseudo,
    gen_sql_query,
)
from .rag import (
    QueryGeneratorRAG,
)
from .restapi import (
    RestAPIClient,
)
from .smart_help import (
    SmartHelp,
)
from .sql import (
    SQLManager,
    save_to_csv,
)
from .summary import gen_summary
from .time import get_current_unix_timestamp
from .types import DCW, Customer, Design
from .utils import (
    extract_all_json,
    extract_json_dict,
    get_prompt_from,
    is_valid_json,
    retry_function,
)

__all__ = [
    'DCW',
    'AuthenticationManager',
    'Contextualizer',
    'Customer',
    'Design',
    'KustoExecutor',
    'LLMSession',
    'LTPReportProcessor',
    'PowerBIClient',
    'QuestionClassifier',
    'QueryGeneratorRAG',
    'SmartHelp',
    'SQLManager',
    'RestAPIClient',
    'dcw_parser',
    'execute_openpai_query',
    'execute_promql_query',
    'extract_all_json',
    'extract_dcw_from_history',
    'extract_json_dict',
    'find_value_in_json',
    'gen_dcw',
    'gen_kusto_query_fallback_pseudo',
    'gen_kusto_query_pseudo',
    'gen_size_range',
    'gen_sql_query',
    'gen_summary',
    'get_current_unix_timestamp',
    'get_last_value',
    'get_prompt_from',
    'is_valid_json',
    'logger',
    'parse_and_align_dcw',
    'push_frontend_event',
    'retry_function',
    'save_to_csv',
    'set_thread_llm_session',
]

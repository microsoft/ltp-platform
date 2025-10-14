# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""This module contains functions for generating, parsing, and aligning DCW objects."""

from __future__ import annotations

import os
import re

from ..utils.logger import logger

from ..config import PROMPT_DIR
from ..utils.llmsession import LLMSession
from ..utils.promql import get_accepted_values
from ..utils.sql import SQLManager
from ..utils.time import get_current_unix_timestamp
from ..utils.utils import extract_json_dict, get_prompt_from


def gen_kusto_query_pseudo(SUB_FEATURE: str, gen_prompt_file: str, user_prompt: str, llm_session: LLMSession) -> dict:
    """Generate controller input."""
    sys_prompt = get_prompt_from(os.path.join(PROMPT_DIR, SUB_FEATURE, gen_prompt_file))
    resp = llm_session.chat(sys_prompt, user_prompt)
    controller_input = extract_json_dict(benchmark=resp, nested=False)
    return controller_input


def gen_kusto_query_fallback_pseudo(question, SUB_FEATURE, gen_fallback_prompt, llm_session: LLMSession) -> str:
    """Generate fallback query from RCA to status."""
    logger.info('Generate a fall back status query')
    system_prompt = get_prompt_from(os.path.join(PROMPT_DIR, SUB_FEATURE, gen_fallback_prompt))
    user_prompt = f'<user input> is\n{question}'
    resp = llm_session.chat(system_prompt, user_prompt)
    fall_back_question = resp.replace('```', '')
    return fall_back_question


def gen_sql_query(SUB_FEATURE: str, database: SQLManager, question: str, llm_session: LLMSession) -> str:
    """Generate a general SQL query."""
    logger.info('Generate a SQL query')
    generation_prompt = get_prompt_from(os.path.join(PROMPT_DIR, SUB_FEATURE, 'gen_query_sql_general.txt'))
    accepeted_value_prompt = database.get_unique_values()
    system_prompt = generation_prompt + f'<accepted values> are\n{accepeted_value_prompt}'
    user_prompt = f'<user input> is\n{question}'
    resp = llm_session.chat(system_prompt, user_prompt)
    logger.info(f'resp {resp}')
    matches = re.findall(r'[`\']{3}(.*?)[`\']{3}', resp, re.DOTALL)
    if not matches:
        logger.error('No query found in the response')
        raise ValueError('Failed to extract SQL query from the response')
    query = matches[0].strip()
    return query


def _convert_to_boolean(parallel):
    if parallel == 'true' or parallel == 'True':
        parallel = True
    else:
        parallel = False
    return parallel


def _convert_to_timestamp(end_time_stamp):
    if end_time_stamp == 'now' or end_time_stamp == 'Now':
        end_time_stamp = get_current_unix_timestamp()
    else:
        end_time_stamp = get_current_unix_timestamp()
    return end_time_stamp


def _construct_promql_query(param):
    # Extract parameters from the dictionary
    aggregation_function = param.get('aggregation_function', '')
    grouping_labels = param.get('grouping_labels', '')
    operation_function = param.get('operation_function', '')
    metric_name = param.get('metric_name', '')
    filters = param.get('filters', '')
    time_offset = param.get('time_offset', '')
    scrape_interval = param.get('scrape_interval', '')
    end_time_stamp = param.get('end_time_stamp', '')
    parallel = param.get('parallel', False)
    # convert
    parallel = _convert_to_boolean(parallel)
    end_time_stamp = _convert_to_timestamp(end_time_stamp)

    # 0, aggregation
    aggregation_segments = aggregation_function.split(',')
    # 1, grouping
    grouping_segment = f'by ({grouping_labels}) ' if grouping_labels else ''
    # 2, interval
    if scrape_interval:
        if 'm' in scrape_interval:
            interval_segment = f':{scrape_interval}'
        else:
            interval_segment = f':{scrape_interval}s'
    else:
        interval_segment = ''
    # 3, filter
    filter_segment = f'{{{filters}}}' if filters else ''
    # 4, time offset
    time_offset_segment = f'{filter_segment}[{time_offset}{interval_segment}]'
    # 5, operation
    if operation_function:
        metric_segment = f'{metric_name}{time_offset_segment} @ {end_time_stamp}'
        operation_segment = f'({operation_function}({metric_segment}))'
    else:
        metric_segment = f'({metric_name}) {time_offset_segment} @ {end_time_stamp}'
        operation_segment = f'{metric_segment}'

    # Assemble the final query
    if len(aggregation_segments) == 2:
        query = (
            f'query?query={aggregation_segments[0]}({aggregation_segments[1]} {grouping_segment}{operation_segment})'
        )
    else:
        query = f'query?query={aggregation_segments[0]} {grouping_segment}{operation_segment}'

    return [query, end_time_stamp, parallel]


def _get_promql_param():
    """Get matching column names."""
    param = {
        'aggregation_function': '',
        'grouping_labels': '',
        'operation_function': '',
        'metric_name': '',
        'filters': '',
        'time_offset': '',
        'scrape_interval': '',
        'end_time_stamp': False,
    }
    return param


def _gen_promql_query_param(SUB_FEATURE: str, question: str, llm_session: LLMSession) -> dict:
    """Generate a general PromQL query."""
    logger.info('Generate a PromQL query')
    generation_prompt = get_prompt_from(os.path.join(PROMPT_DIR, SUB_FEATURE, 'gen_query_promql_metrics.txt'))
    accepeted_value_prompt = get_accepted_values()
    # logger.info(f'accepeted_value_prompt:\n{accepeted_value_prompt}')
    system_prompt = generation_prompt + f'<accepted values> are\n{accepeted_value_prompt}'
    user_prompt = f'<user input> is\n{question}'
    resp = llm_session.chat(system_prompt, user_prompt)
    logger.info(f'resp:\n{resp}')
    params = extract_json_dict(benchmark=resp, nested=False)
    logger.info(f'params:\n{params}')
    return params


def gen_promql_query(SUB_FEATURE: str, question: str, llm_session: LLMSession) -> tuple[str, bool]:
    """Generate a general PromQL query."""
    params = _gen_promql_query_param(SUB_FEATURE, question, llm_session)
    if not isinstance(params, dict):
        logger.info(f'No query found in the response, params is {params}')
        return None, None, None, None
    query, end_time_stamp, parallel = _construct_promql_query(params)
    logger.info(f'query: {query}')
    logger.info(f'parallel: {parallel}')
    return query, end_time_stamp, parallel, params

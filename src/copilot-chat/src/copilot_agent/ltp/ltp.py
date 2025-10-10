# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""LTP module for CoPilot Agent."""

from __future__ import annotations

import os
import datetime

from ..utils.logger import logger

from ..config import PROMPT_DIR
from ..utils.kql_executor import KustoExecutor
from ..utils.llmsession import LLMSession
from ..utils.openpai import execute_openpai_query
from ..utils.powerbi import LTPReportProcessor
from ..utils.promql import execute_promql_query, execute_promql_query_step, retrive_promql_response_value
from ..utils.query import gen_promql_query
from ..utils.summary import gen_summary
from ..utils.time import get_current_unix_timestamp
from ..utils.types import DCW
from ..utils.utils import get_prompt_from
from .ltp_dashboard import query_generation_kql

model = LLMSession()

SUB_FEATURE = 'ltp'

SKIP_LUCIA_CONTROLLER_EXECUTION = True

# session: query cluster or job metrics from Prometheus REST API
def query_metrics(question: str, help_msg, skip_summary: bool = False):
    """Query cluster or job metrics from Prometheus backend."""
    
    if SKIP_LUCIA_CONTROLLER_EXECUTION:
        logger.info('Skipping PromQL query generation.')
        query, end_time_stamp, parallel, param = None, None, None, {'scrape_interval': None, 'time_offset': None}
        logger.info('Skipping PromQL query execution.')
        resp = f'Skipping PromQL query execution due to lack of support, this will be enabled in the next release.'
        resp_parser_param = resp
        value = {'result': resp}
    else:
        # generate query
        logger.info('Generating Query: LTP, Metrics')
        query, end_time_stamp, parallel, param = gen_promql_query(SUB_FEATURE, question)

        if not query:
            logger.info(f'No query found in the response, query is {query}')
            answer = 'Query generation failed, no query found.'
            return answer, None
        # execute
        logger.info('Executing Query: LTP, Metrics')
        if not parallel:
            resp = execute_promql_query(query, {})
        else:
            resp = execute_promql_query_step(query, {}, end_time_stamp, f"{param['time_offset']}")
        resp_parser_param, value = retrive_promql_response_value(resp, param)

    # generate answer
    logger.info('Generating Answer: LTP, Metrics')
    summary = gen_summary(
        SUB_FEATURE,
        {'cluster_job_metrics': value},
        {'cluster_job_metrics': value},
        question,
        'gen_result_summary_metrics.txt',
        None,
        help_msg,
        skip_summary,
    )

    # generate additional info dict
    info_dict = {}
    info_dict['query_promql'] = query
    info_dict['query_param_promql'] = param
    info_dict['resp_promql'] = resp
    info_dict['value_promql'] = value
    info_dict['__debug:f1_query'] = query
    info_dict['__debug:f2_execution_method'] = parallel
    info_dict['__debug:f3_scrape_interval_in_execution'] = param.get('scrape_interval', None)
    info_dict['__debug:f4_resp_parser_param'] = resp_parser_param
    info_dict['__debug:r0_type_resp_promql'] = type(resp).__name__

    return summary, info_dict


# session: query job metadata from OpenPAI backend
def query_metadata(question: str, help_msg, skip_summary: bool = False):
    """Query job metadata from OpenPAI backend."""
    # generate query
    logger.info('Generating Query: LTP, Metadata')
    query = 'restserver/jobs?offset=0&limit=49999&withTotalCount=true&order=completionTime'

    if SKIP_LUCIA_CONTROLLER_EXECUTION:
        logger.info('Skipping job metadata query execution.')
        resp = f'Skipping job metadata query execution due to lack of support, this will be enabled in the next release.'
        job_metadata = {'result': resp}
        job_metadata_brief = {'result': resp}
    else:
        # extract
        logger.info('Executing Query: LTP, Metadata')
        resp = execute_openpai_query(query, {})
        job_metadata = extract_job_metadata(resp)
        job_metadata_brief = get_brief_job_metadata(resp)

    # generate answer
    logger.info('Generating Answer: LTP, Metadata')
    summary = gen_summary(
        SUB_FEATURE,
        {'job_metadata': job_metadata},
        {'job_metadata_only_the_first_1000_jobs': job_metadata_brief},
        question,
        'gen_result_summary_metadata.txt',
        None,
        help_msg,
        skip_summary,
    )

    # generate additional info dict
    info_dict = {}
    info_dict['query_promql'] = query
    info_dict['resp_brief_promql'] = job_metadata_brief
    return summary, info_dict


# session: query user manual from LTP documentation
def query_user_manual(question: str, help_msg):
    """Query user manual."""
    # read documentation
    documentation = get_prompt_from(os.path.join(PROMPT_DIR, SUB_FEATURE, 'ltp_documentation.txt'))
    ltp_doc = {'lucia training platform documentation': documentation}

    # generate answer
    logger.info('Generating Answer: LTP, User Manual')
    summary = gen_summary(SUB_FEATURE, ltp_doc, None, question, 'gen_result_summary_doc.txt', None, help_msg)

    info_dict = {}
    return summary, info_dict


def extract_job_metadata(resp):
    """Extract job metadata from OpenPAI response."""
    if isinstance(resp, dict) and 'data' in resp:
        resp_data = resp['data']
        job_metadatas = {
            f'{job["username"]}~{job["name"]}': {
                k: v for k, v in job.items() if k not in ['debugId', 'subState', 'executionType', 'appExitCode']
            }
            for job in resp_data
        }
    else:
        job_metadatas = None
    return job_metadatas


def get_brief_job_metadata(resp):
    """Get brief job metadata."""
    if isinstance(resp, dict) and 'data' in resp:
        resp_data = resp['data']
        job_metadatas = [f'{job["username"]}~{job["name"]}' for job in resp_data]
        job_metadatas = job_metadatas[:1000]
    else:
        job_metadatas = None
    return job_metadatas


def query_powerbi(question: str, help_msg):
    """Query PowerBI data."""

    query_gen_res, query_gen_status = query_generation_kql(question)
    logger.info(f'KQL Query generation result: {query_gen_res}, status: {query_gen_status}')
    k_cluster = os.environ.get('DATA_SRC_KUSTO_CLUSTER_URL', '')
    k_db = os.environ.get('DATA_SRC_KUSTO_DATABASE_NAME', '')
    k_table = ''
    if query_gen_status == 0:
        KQL = KustoExecutor(k_cluster, k_db, k_table)
        # Replace placeholders
        query_gen_res = query_gen_res.format(
            cluster_url=k_cluster,
            database_name=k_db
        )
        response, response_status = KQL.execute_return_data(query_gen_res)
        response_long = {"query_generated": query_gen_res, "response_from_query_execution": response}
        logger.info(f'Kusto Query execution result: {response}')
    else:
        response = {}
        response_long = {"query_generated": "query generation failed, please perform manual investigation", "response_from_query_execution": response}
        response_status = -1

    logger.info('Generating Answer: LTP, Dashboard')
    summary = gen_summary(
        SUB_FEATURE,
        response_long,
        response,
        question,
        'gen_result_summary_dashboard.txt',
        None,
        help_msg,
        False,
    )

    if response_status == 0:
        reference = f'\n\n >Reference: the generated KQL query used to get the data:\n\n```\n{query_gen_res}\n```'
        summary += reference

    info_dict = {}
    info_dict["s0_query_gen"] = {"res": query_gen_res, "status": query_gen_status}
    info_dict["s1_query_exe"] = {"res": make_json_serializable(response), "status": response_status}
    return summary, info_dict


def ltp_auto_reject(question: str, help_msg):
    """Auto rejected, unsupported by design."""

    logger.info('Generating Answer: LTP, Auto Rejection')
    summary = gen_summary(
        SUB_FEATURE,
        {},
        {},
        question,
        'gen_result_summary_rejection.txt',
        None,
        help_msg,
        False,
    )

    info_dict = {}
    return summary, info_dict


def ltp_human_intervention(question: str, help_msg):
    """Handle human intervention for LTP auto rejection."""

    logger.info('Generating Answer: LTP, Human Intervention')
    summary = gen_summary(
        SUB_FEATURE,
        {},
        {},
        question,
        'gen_result_summary_human.txt',
        None,
        help_msg,
        False,
    )

    info_dict = {}
    return summary, info_dict

def make_json_serializable(data):
    """
    Recursively converts non-JSON serializable objects within a data structure.
    """
    if isinstance(data, (list, tuple)):
        return [make_json_serializable(item) for item in data]
    elif isinstance(data, dict):
        return {key: make_json_serializable(value) for key, value in data.items()}
    elif isinstance(data, datetime.timedelta):
        # Convert timedelta to total seconds (a float)
        return data.total_seconds()
    else:
        # Return the object as is if it's already serializable
        return data
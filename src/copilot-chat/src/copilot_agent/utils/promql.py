# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Prometheus Query."""

import json
from copy import deepcopy

from joblib import Parallel, delayed

from ..utils.logger import logger

from ..utils.time import parse_duration

class FakeControllerClient:
    def request_controller(self, method, api, data):
        """Simulates a response from the controller."""
        # Example fake response
        if "prometheus" in api:
            return type("Response", (object,), {"ok": True, "content": json.dumps({"data": {"result": []}})})()
        return type("Response", (object,), {"ok": False, "content": "{}"})()

# Replace the real ControllerClient with the fake one
controller = FakeControllerClient()


def execute_promql_query(query, data, retry=1):
    """Executes a PromQL (Prometheus Query Language) query and retrieves the result."""

    while retry > 0:
        response = controller.request_controller(
            method='GET',
            api=f'prometheus/{query}',
            data=data,
        )
        if response and response.ok:
            return json.loads(response.content)['data']
        logger.error(f'Prometheus query failed. Query: {query} Response:{response.content}')
        retry -= 1
    return None


def execute_promql_query_step(query, data, end_time, time_offset, step='6h'):
    """Executes a PromQL query in parallel over specified time intervals."""
    start_time = end_time - parse_duration(time_offset).total_seconds()
    step_timedelta = parse_duration(step).total_seconds()
    logger.info(f'Querying from {start_time} to {end_time} with step_timedelta {step_timedelta}')

    time_intervals = []
    current_time = start_time

    # Prepare time intervals for parallel queries
    while current_time < end_time:
        next_time = min(current_time + step_timedelta, end_time)
        time_intervals.append((int(float(current_time)), int(float(next_time))))
        current_time = next_time

    def query_interval(start, end):
        # Create the query with the specific time range
        time_offset = f'{int(end - start)}s'
        query_with_time = query.replace('{time_offset}', time_offset).replace('{end_time_stamp}', str(int(end)))
        # print(query_with_time)
        # Query Prometheus
        # print(query_with_time)
        result = execute_promql_query(query_with_time, data)
        return (
            start,
            end,
            deepcopy(result['result']) if result and result['result'] else [],
        )

    # Execute queries in parallel using joblib
    final_value = Parallel(n_jobs=4, backend='threading')(
        delayed(query_interval)(start, end) for start, end in time_intervals
    )

    return final_value


def get_all_metrics():
    """Fetch all available Prometheus metrics from the specified API."""
    response = controller.request_controller(
        method='GET',
        api='prometheus/api/v1/label/name/values',
        data=None,
    )
    if response and response.ok:
        return json.loads(response.content)['data']
    logger.error(f'Failed to fetch metrics. Response: {response.content}')
    return []


def get_all_labels():
    """Fetches all labels from the Prometheus API."""
    response = controller.request_controller(
        method='GET',
        api='prometheus/api/v1/labels',
        data=None,
    )
    if response and response.ok:
        return json.loads(response.content)['data']
    logger.error(f'Failed to fetch labels. Response: {response.content}')
    return []


def get_label_values(label_name):
    """Fetches all values for a specific label from the Prometheus API."""
    response = controller.request_controller(
        method='GET',
        api=f'prometheus/api/v1/label/{label_name}/values',
        data=None,
    )
    if response and response.ok:
        return json.loads(response.content)['data']
    logger.error(f'Failed to fetch label values for {label_name}. Response: {response.content}')
    return []


def get_metric_metadata(metric_name):
    """Fetches metadata for a specific metric from the Prometheus API."""
    response = controller.request_controller(
        method='GET',
        api='prometheus/api/v1/series',
        data={'match[]': metric_name},
    )
    if response and response.ok:
        return json.loads(response.content)['data']
    logger.error(f'Failed to fetch metadata for metric {metric_name}. Response: {response.content}')
    return []


def get_all_aggregation_functions():
    """Fetches all aggregation functions from the Prometheus API."""
    from_doc = [
        'avg',
        'sum',
        'min',
        'max',
        'count',
        'stddev',
        'stdvar',
        'topk',
        'bottomk',
        'quantile',
    ]
    from_self = ['sum_over_time']
    return from_doc + from_self


def get_all_operation_functions():
    """Fetches all operation functions from the Prometheus API."""
    from_doc = [
        'rate',
        'irate',
        'increase',
        'delta',
        'deriv',
        'predict_linear',
        'histogram_quantile',
    ]
    from_self = ['count_over_time', 'sum_over_time', 'avg_over_time', '']
    return from_doc + from_self


def get_all_gilters(lables):
    """Fetches all filters for the specified labels from the Prometheus API."""
    for label in lables:
        accepted_values = get_label_values(label)
        if not accepted_values:
            logger.error(f'Failed to fetch label values for {label}.')
            return []
        accepted_values[label] = accepted_values
    return accepted_values


def get_accepted_values():
    """Fetches all accepted values for metrics, labels, aggregation functions, and operation functions."""
    accepted_values = {}
    accepted_values['accepted_metrics'] = get_all_metrics()
    accepted_values['accepted_labels'] = get_all_labels()
    accepted_values['accepted_aggregation_functions'] = get_all_aggregation_functions()
    accepted_values['accepted_operation_functions'] = get_all_operation_functions()
    # accepted_values['accepted_filters'] = get_all_gilters(accepted_values['accepted_labels'])
    return accepted_values


def clean_metric_name(metric_name):
    """Cleans the metric name by removing unwanted characters."""
    metric_name_original = metric_name
    metric_name = metric_name.replace('(', '').replace(')', '')
    if '<=' in metric_name:
        metric_name = metric_name.split('<')[0]
    if '>=' in metric_name:
        metric_name = metric_name.split('>')[0]
    if '==' in metric_name:
        metric_name = metric_name.split('==')[0]
    logger.info(f"Original metric name: {metric_name_original}, Cleaned metric name: {metric_name}")
    return metric_name


def get_metric_sampling_interval(metric_name):
    """Get the sampling interval for a given metric."""
    logger.info(f"Getting sampling interval for metric: {metric_name}")
    metric_name = clean_metric_name(metric_name)
    attempt = 1
    max_attempts = 10000000000000  # Set a maximum number of attempts to prevent infinite loop
    while attempt <= max_attempts:
        query = f"query?query={metric_name}[{attempt}m]"
        output = execute_promql_query(query, {})
        if output and "result" in output and len(output["result"]) > 0:
            values = output["result"][0]["values"]
            logger.info(f"Attempt {attempt}: Retrieved values: {values}")
            return int(float(values[1][0]) - float(values[0][0]))
        else:
            logger.info(f"Attempt {attempt}: Query: {query}, Output: {output}")
        attempt = attempt * 10
    
    # If the loop completes without returning, raise an exception or handle the error
    logger.info(f"Unable to determine sampling interval for metric: {metric_name}")
    return None


def _retrieve_non_parallel(response, interval):
    """Retrieves the non-parallel response."""
    if (
        not response 
        or not isinstance(response, dict) 
        or 'result' not in response 
        or not response['result']
    ):
        logger.error(f"Invalid response format: {response}")
        return None
    else:
        return float(response['result'][0]['value'][1]) * interval / 3600


def _retrieve_parallel(response, interval):
    """Retrieves the parallel response."""
    print(f"Response: {response}")
    if isinstance(response, list):
        total = 0
        for item in response:
            if item[2]:
                # Check if 'value' key exists
                if 'value' in item[2][0]:
                    total += float(item[2][0]["value"][1])
                # Check if 'values' key exists
                elif 'values' in item[2][0]:
                    total += sum(float(value[1]) for value in item[2][0]["values"])
        return total * interval / 3600
    else:
        logger.error(f"Invalid response format: {response}")
        return None


def _aggregate_result(response, response_structure_type, aggregation_method):
    """
    Calculate the aggregated result based on the response, response structure type, and aggregation method.

    :param response: The response data (JSON-like structure).
    :param response_structure_type: The type of response structure (e.g., "single:vector", "segmented:vector", "single:matrix", "segmented:matrix").
    :param aggregation_method: The aggregation method to apply ("average", "sum", "append_to_list", "list_metric").
    :return: The aggregated result.
    """
    def extract_values_vector(data):
        """Extract values from a vector response."""
        return [float(item["value"][1]) for item in data["result"]]

    def extract_values_matrix(data):
        """Extract values from a matrix response."""
        values = []
        for item in data["result"]:
            values.extend([float(value[1]) for value in item["values"]])
        return values

    def extract_values_segmented_vector(data):
        """Extract values from a segmented vector response."""
        values = []
        for segment in data:
            for item in segment[2]:
                values.append(float(item["value"][1]))
        return values

    def extract_values_segmented_matrix(data):
        """Extract values from a segmented matrix response."""
        values = []
        for segment in data:
            for item in segment[2]:
                values.extend([float(value[1]) for value in item["values"]])
        return values

    def extract_metrics_vector(data):
        """Extract metric dictionaries from a vector response."""
        return [item["metric"] for item in data["result"]]

    def extract_metrics_matrix(data):
        """Extract metric dictionaries from a matrix response."""
        return [item["metric"] for item in data["result"]]

    def extract_metrics_segmented_vector(data):
        """Extract metric dictionaries from a segmented vector response."""
        metrics = []
        for segment in data:
            for item in segment[2]:
                metrics.append(item["metric"])
        return metrics

    def extract_metrics_segmented_matrix(data):
        """Extract metric dictionaries from a segmented matrix response."""
        metrics = []
        for segment in data:
            for item in segment[2]:
                metrics.append(item["metric"])
        return metrics

    # Determine the extraction function based on the response structure type
    if response_structure_type == "single:vector":
        metrics = extract_metrics_vector(response)
        values = extract_values_vector(response)
    elif response_structure_type == "single:matrix":
        metrics = extract_metrics_matrix(response)
        values = extract_values_matrix(response)
    elif response_structure_type == "segmented:vector":
        metrics = extract_metrics_segmented_vector(response)
        values = extract_values_segmented_vector(response)
    elif response_structure_type == "segmented:matrix":
        metrics = extract_metrics_segmented_matrix(response)
        values = extract_values_segmented_matrix(response)
    else:
        logger.info(f"Unsupported response structure type: {response_structure_type}")
        return response

    # Perform the aggregation based on the aggregation method
    if aggregation_method == "average":
        return sum(values) / len(values) if values else 0
    elif aggregation_method == "sum":
        return sum(values)
    elif aggregation_method == "append_to_list":
        return values
    elif aggregation_method == "list_metric":
        return metrics
    else:
        raise ValueError(f"Unsupported aggregation method: {aggregation_method}")


def retrive_promql_response_value(response, promql_param):
    """Retrieves the value from the Prometheus response based on the provided PromQL parameter."""
    if not response or not isinstance(promql_param, dict):
        return None, None

    metric_name = promql_param.get('metric_name')
    parallel = promql_param.get('parallel')
    if not metric_name or parallel is None:
        return None, None

    # get interval
    scrape_interval = get_metric_sampling_interval(metric_name)

    # identify the response structure
    response_structure = identify_promql_resp_structure(response)

    if scrape_interval is None:
        return scrape_interval, response

    resp_parser_param = {"scrape_interval": scrape_interval, "response_structure": response_structure}
    logger.info(f"Response as: {response}")
    logger.info(f"Response structure identified as: {response_structure}")
    
    aggregated_result = {}
    aggregated_result['avg'] = _aggregate_result(response, response_structure, 'average')
    aggregated_result['sum'] = _aggregate_result(response, response_structure, 'sum')
    aggregated_result['tolist'] = _aggregate_result(response, response_structure, 'append_to_list')
    aggregated_result['metric'] = _aggregate_result(response, response_structure, 'list_metric')
    return resp_parser_param, aggregated_result


def identify_promql_resp_structure(response):
    """Identifies the structure of a PromQL response.
    Args:
        response (dict): The PromQL response as a Python dictionary.
    Returns:
        str: The name of the structure (e.g., 'single:vector', 'segmented:vector', 'single:matrix', 'segmented:matrix', or 'unsupported').
    """
    # Check for single:vector
    if isinstance(response, dict) and "resultType" in response and response["resultType"] == "vector":
        if "result" in response and isinstance(response["result"], list):
            if len(response["result"]) > 0 and "value" in response["result"][0]:
                return "single:vector"

    # Check for segmented:vector
    if isinstance(response, list):
        if all(isinstance(segment, (list, tuple)) and len(segment) == 3 for segment in response):
            if all(isinstance(segment[2], list) and len(segment[2]) > 0 and "value" in segment[2][0] for segment in response):
                return "segmented:vector"

    # Check for single:matrix
    if isinstance(response, dict) and "resultType" in response and response["resultType"] == "matrix":
        if "result" in response and isinstance(response["result"], list):
            if len(response["result"]) > 0 and "values" in response["result"][0]:
                return "single:matrix"

    # Check for segmented:matrix
    if isinstance(response, list):
        if all(isinstance(segment, (list, tuple)) and len(segment) == 3 for segment in response):
            if all(isinstance(segment[2], list) and len(segment[2]) > 0 and "values" in segment[2][0] for segment in response):
                return "segmented:matrix"

    # If none of the structures match
    return "unsupported"


# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from ..utils.logger import logger

import os
import json
import re
from datetime import datetime
from ..utils.restapi import RestAPIClient


class PowerBIClient:
    def __init__(self, base_url, api_key):
        """Initialize the PBI API client."""
        # base_url: Base URL of the PBI REST API server.
        # api_key: API key for authentication.
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.client = RestAPIClient(base_url, headers)

    def get_report(self, group_id=None, report_id=None):
        """Fetch a specific report from the PBI server."""
        if group_id is None or report_id is None:
            return {"status_code": -99, "content": "Group ID and Report ID must be specified."}
        else:
            endpoint = f"groups/{group_id}/reports/{report_id}"
            response = self.client.get(endpoint)
            return self.parse_response(response)

    def execute_dax_query(self, group_id, dataset_id, query):
        """Execute a DAX query on a dataset."""
        if group_id is None or dataset_id is None or query is None:
            return {"status_code": -99, "content": "Group ID, Dataset ID and Query must be specified."}
        else:
            endpoint = f"groups/{group_id}/datasets/{dataset_id}/executeQueries"
            querybody = {
                "queries": [
                    {
                        "query": query
                    }
                ]
            }
            response = self.client.post(endpoint, json=querybody)
            return self.parse_response(response)

    @staticmethod
    def parse_response(response):
        if response.status_code == 200:
            parsed = {"status_code": response.status_code, "content": response.json()}
        else:
            parsed = {"status_code": response.status_code, "content": response.text}
        return parsed


class LTPReportProcessor:
    """Class to process LTP report data."""

    def __init__(self, api_key: str, base_url: str, group_id: str, dataset_id: str):
        self.api_key = api_key
        self.base_url = base_url
        self.group_id = group_id
        self.dataset_id = dataset_id
        self.client = self._initialize_powerbi_client()

    def _initialize_powerbi_client(self) -> PowerBIClient:
        """Initialize the PowerBI client."""
        return PowerBIClient(base_url=self.base_url, api_key=self.api_key)

    @staticmethod
    def get_current_week_number() -> int:
        """Get the current ISO week number."""
        return datetime.now().isocalendar()[1]

    @staticmethod
    def get_files_with_extension(directory: str, extension: str) -> list[str]:
        """Get all file names in a directory with a specific extension."""
        return sorted([f for f in os.listdir(directory) if f.endswith(extension)])

    @staticmethod
    def remove_file_extension(file_names: list[str], extension: str) -> list[str]:
        """Remove a specific extension from file names."""
        return [f.replace(extension, "") for f in file_names]

    @staticmethod
    def filter_tables(tables: list[str], patterns: list[str]) -> list[str]:
        """Remove tables that match specific regex patterns."""
        regexes = [re.compile(p) for p in patterns]
        return [t for t in tables if not any(r.match(t) for r in regexes)]

    @staticmethod
    def get_week_key(table_name: str) -> str:
        """Get the key for the week number in the table."""
        return f"{table_name}[WeekNum]" if table_name == "A-r0-na" else f"{table_name}[Week]"

    @staticmethod
    def filter_rows_by_week(table: list[dict], table_name: str, current_week: int, offset: int) -> list[dict]:
        """Filter rows to include only those from the last 4 weeks."""
        filtered_rows = []
        week_key = LTPReportProcessor.get_week_key(table_name)
        for row in table:
            if week_key in row and isinstance(row[week_key], int):
                if row[week_key] >= current_week - offset:
                    filtered_rows.append(row)
        return filtered_rows

    def filter_recent_weeks(self, table_data: dict, table_name: str, current_week: int, offset: int) -> list[dict]:
        """Filter table data to include only rows from the last few weeks."""
        if 'content' in table_data:
            if 'results' in table_data['content']:
                if 'tables' in table_data['content']['results'][0]:
                    if 'rows' in table_data['content']['results'][0]['tables'][0]:
                        table = table_data['content']['results'][0]['tables'][0]['rows']
                        filtered_table = self.filter_rows_by_week(table, table_name, current_week, offset)
                        return filtered_table
        logger.info("No valid data found in the table.")
        return []

    def process_report_data(self, tables_directory: str, output_path: str):
        """Process the LTP report data and save the results."""
        current_week = self.get_current_week_number()
        logger.info(f"Current week number: {current_week}")

        # Get and filter table names
        table_files = self.get_files_with_extension(tables_directory, ".tmdl")
        table_names = self.remove_file_extension(table_files, ".tmdl")
        table_names = self.filter_tables(
            table_names,
            [
                r"^LocalDateTable",
                r"^RDim",
                r"^ADim",
                r"^JDim",
                r"^DateTableTemplate",
                r"^CalendarTable",
                r"^R-r0-Column",
                r"^A-r0",
                r"^A-r2",
                r"^J-r0",
                r"^J-r1",
                r"^M-t1",
                r"^R-r0",
                r"^R-r1",
                r"^R-t0",
                r"^J-r2",
                r"^J-r3",
                r"^M-r0",
            ],
        )
        logger.info(f"Number of tables to process: {len(table_names)}")

        # Process each table
        table_data_list_long = []
        table_data_list_short = []
        for table_name in table_names:
            query = f"EVALUATE '{table_name}'"
            table_data = self.client.execute_dax_query(self.group_id, self.dataset_id, query)
            filtered_data_short = self.filter_recent_weeks(table_data, table_name, current_week, 1)
            filtered_data_long = self.filter_recent_weeks(table_data, table_name, current_week, 4)
            table_data_list_short.append({table_name: filtered_data_short})
            table_data_list_long.append({table_name: filtered_data_long})
            logger.info(f"Processed table: {table_name}")
            logger.info(f"{str(table_data)[:100]}...")

        # Save results to JSON
        os.makedirs(output_path, exist_ok=True)
        report_collection_status = all(
            table_data.get("status_code") == 200
            for table_data in [self.client.execute_dax_query(self.group_id, self.dataset_id, f"EVALUATE '{name}'") for name in table_names]
        )
        log_file = os.path.join(output_path, "ltp_dashboard_data_model")
        with open(log_file, "w") as log:
            log.write(f"Report collection status: {'Success' if report_collection_status else 'Failure'}\n")
            log.write(f"Collected at {datetime.now().isoformat()}\n")
            log.write(f"Processed tables: {', '.join(table_names)}\n")
            log.write(f"Current week number: {current_week}\n")
            log.write(f"Table data count: {len(table_data_list_short)}\n")

        if report_collection_status:
            output_file_short = os.path.join(output_path, "ltp_dashboard_data_model_short.json")
            with open(output_file_short, "w") as res:
                json.dump(table_data_list_short, res, indent=2)
            logger.info(f"Processed data saved to: {output_file_short}")

        if report_collection_status:
            output_file_long = os.path.join(output_path, "ltp_dashboard_data_model_long.json")
            with open(output_file_long, "w") as res:
                json.dump(table_data_list_long, res, indent=2)
            logger.info(f"Processed data saved to: {output_file_long}")

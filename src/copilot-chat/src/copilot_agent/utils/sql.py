# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""SQL DB backend for the Copilot Agent."""

import csv
import os
import re
import sqlite3

from ..utils.logger import logger

from ..config import DATA_DIR
SQLDB_DIR = os.path.join(DATA_DIR, 'sql')

class SQLManager:
    """SQL DB backend."""

    def __init__(self, database_name):
        """Init function, input is the database name."""
        self.database_name = database_name
        self.database_dir = os.path.join(SQLDB_DIR, database_name)
        self.csv_file_path = os.path.join(self.database_dir, 'data.csv')
        self.database_path = os.path.join(self.database_dir, 'data.db')
        self.schema_file = os.path.join(self.database_dir, 'schema.txt')

        # Remove the 'data.db' if it exists
        if os.path.exists(self.database_path):
            os.remove(self.database_path)
            logger.info(f'{self.database_path} has been removed')

        # Set check_same_thread to False
        self.conn = sqlite3.connect(self.database_path, check_same_thread=False)
        self.cur = self.conn.cursor()

        # Read the schema from the schema.txt file
        with open(self.schema_file) as file:
            self.schema = file.read()

        # Check if the table exists
        self.cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (database_name,))
        if not database_name.isalnum():
            raise ValueError('Invalid database name')
        if self.cur.fetchone() is None:
            # Create the table with the appropriate schema
            self.cur.execute(self.schema)

            # Check if the CSV file exists
            if os.path.exists(self.csv_file_path):
                # Open the CSV file and read the data
                with open(self.csv_file_path) as csv_file:
                    # Create a DictReader to read the CSV file
                    dr = csv.DictReader(csv_file)

                    # Convert the CSV data to a list of tuples
                    to_db = [tuple(row[field] for field in dr.fieldnames) for row in dr]

                    # Bulk insert the data into the table
                    self.cur.executemany(
                        f"""
                    INSERT INTO {database_name} VALUES ({', '.join(['?']*len(dr.fieldnames))})
                    """,
                        to_db,
                    )

            # Commit changes
            self.conn.commit()

    def query(self, query):
        """Execute a query and return the results."""
        try:
            self.cur.execute(query)
            return 'OK', self.cur.fetchall()
        except sqlite3.Error as e:
            logger.info(f'An error occurred: {e}')
            return 'Error', []

    def extract_column_names(self):
        """Get matching column names."""
        if os.path.exists(self.schema_file):
            with open(self.schema_file) as f:
                schema = f.read()
                # Regular expression to match column names with TEXT type
                # \b is a word boundary to ensure we match whole words.
                # (?!Cluster\b|MachinePool\b) is a negative lookahead that ensures the column name does not contain these.
                # (\w+) captures the column name.
                # \s+TEXT ensures that the column is of type TEXT.
                pattern = r'\b(?!Cluster\b|MachinePool\b)(\w+)\s+TEXT'
                # Find all matches in the schema
                matches = re.findall(pattern, schema)
                return matches
        else:
            return None

    def get_unique_values(self):
        """Get unique values for a given db.table."""
        template = """
        SELECT DISTINCT <column_name>
        FROM <table_name>;
        """
        unique_values_list = []
        column_extracted = self.extract_column_names()
        if isinstance(column_extracted, list):
            for column in column_extracted:
                query = template
                status, values = self.query(
                    query.replace('<column_name>', column).replace('<table_name>', self.database_name)
                )
                unique_value_dict = {'column name': column, 'accepted values': values}
                unique_values_list.append(unique_value_dict)
        return str(unique_values_list)


def save_to_csv(input_data, db_name):
    """Save the input data to a CSV file."""
    # Check if input is a list of dicts
    if not isinstance(input_data, list) or not all(isinstance(i, dict) for i in input_data):
        logger.info('Input data is not a list of dicts')
        return False

    # Check if 'data.csv' exists in the dir
    file_path = os.path.join(SQLDB_DIR, db_name, 'data.csv')
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f'existing csv removed: {file_path}')

    # Save the list of dicts into the 'data.csv'
    total_rows = len(input_data)
    saved_rows = 0
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=input_data[0].keys())
        writer.writeheader()
        for data in input_data:
            # Check if any value in the dictionary is empty or None
            if any(value == '' or value is None for value in data.values()):
                continue
            writer.writerow(data)
            saved_rows += 1
        logger.info(f'latest csv saved: {file_path}')
        logger.info(f'Total rows: {total_rows}, Rows saved: {saved_rows}')

    return True

"""Dashboard Data Backup Service - Automated backup of PowerBI dashboard data to Kusto tables via cron."""

import os
import json

from util import KustoTable, extract_kusto_query_from_pbi

def backup_append_table(config):
    """
    Backup PowerBI dashboard data to Kusto table.
    Extracts query from .tmdl file, executes it, and appends results with timestamp.
    Creates destination table if it doesn't exist.
    """
    
    name = config.get('name', 'unsupported')
    print(f'Backup and append table: {name}')
    
    # Initialize Kusto table connections for source and destination
    src_table = KustoTable(**config['src_table'])
    dst_table = KustoTable(**config['dst_table'])

    # Build path to PowerBI .tmdl file containing the query
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    src_query_path = os.path.join(curr_dir, 'tables', name)
    print(f'src_query_path: {src_query_path}')

    # Extract and enhance the Kusto query with backup timestamp
    src_query = extract_kusto_query_from_pbi(src_query_path)
    src_query_extended = src_query + f'\n| extend BackupTimeStamp = now()'
    print(f'src_query_extended: {src_query_extended}')

    # Check if destination backup table exists, create if needed
    cache_exists = dst_table.check_table_existence()
    print(f"STEP 1: cache table exists: {cache_exists}")
    if not cache_exists:
        # Create table with schema inferred from first query execution
        dst_table.create_and_set_table(src_query_extended)
        print(f"STEP 2: dst table does not exist, creating it.")

    # Execute query and append results to backup table
    print(f"STEP 3: ingesting data into cache table.")
    dst_table.update_table_append(src_query_extended)


def main():
    """
    Main entry point for dashboard data backup service.
    Reads configurations from env or tables/table_name.json based on DEBUG_MODE.
    """
    debug_mode = os.environ.get("DEBUG_MODE", "no")
    configs = []
    if debug_mode != "no":
        # Debug mode: read from JSON file
        with open('tables/table_name.json') as f:
            configs = json.load(f)
    else:
        # Online mode: read from envs, support multiple tables separated by "'"
        table_names = os.environ.get("TABLE_NAMES", "")
        src_clusters = os.environ.get("SRC_TABLE_CLUSTERS", "")
        src_dbs = os.environ.get("SRC_TABLE_DBS", "")
        src_tables = os.environ.get("SRC_TABLE_TABLES", "")
        dst_clusters = os.environ.get("DST_TABLE_CLUSTERS", "")
        dst_dbs = os.environ.get("DST_TABLE_DBS", "")
        dst_tables = os.environ.get("DST_TABLE_TABLES", "")

        # Split by "'" to support multiple tables
        names = table_names.split("'")
        src_clusters = src_clusters.split("'")
        src_dbs = src_dbs.split("'")
        src_tables = src_tables.split("'")
        dst_clusters = dst_clusters.split("'")
        dst_dbs = dst_dbs.split("'")
        dst_tables = dst_tables.split("'")

        if not (len(names) == len(src_clusters) == len(src_dbs) == len(src_tables) == len(dst_clusters) == len(dst_dbs) == len(dst_tables)):
            raise ValueError("Mismatch in number of elements for table configuration environment variables.")
        for i in range(len(names)):
            config = {
                "name": names[i],
                "src_table": {
                    "cluster": src_clusters[i],
                    "db": src_dbs[i],
                    "table": src_tables[i]
                },
                "dst_table": {
                    "cluster": dst_clusters[i],
                    "db": dst_dbs[i],
                    "table": dst_tables[i]
                }
            }
            configs.append(config)

    for config in configs:
        backup_append_table(config)

if __name__ == "__main__":
    main()
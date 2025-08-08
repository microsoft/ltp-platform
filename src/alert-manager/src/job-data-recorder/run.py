#!/usr/bin/env python3
"""
Job Data Recorder - This script processes finished job metrics and react times, then ingests them into Kusto.
"""

import logging
import os
import sys

from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
import pandas as pd

# Add current directory to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from record_job import generate_metrics, generate_job_react_time, update_react_time, update_failure_reason_category
from kusto_util import KustoUtil
from data_sources import parse_interval

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def process_job_data(time_offset=None):
    """
    Collects job metrics and react times, then ingests them into Kusto.

    Args:
        time_offset (str, optional): Data window length (e.g. '24h', '3600s').
            If None, will use last timeGenerated from Kusto to fill missing data.
    """
    current_time = datetime.now().timestamp()

    metrics_table = os.getenv('KUSTO_METRICS_TABLE', 'JobSummary')
    react_table = os.getenv('KUSTO_REACT_TABLE', 'JobReactTime')
    retain_time = os.getenv('RECORD_RETAIN_TIME', '30d')

    logger.info(f"--- Processing job data at {datetime.now()} ---")

    # In case data missing during the service downtime, we will use the last timeGenerated as the start time for the first run
    # After that, we will use the time_offset to determine the time window
    if time_offset is None:
        last_time = KustoUtil().query_last_time_generated()
        if last_time:
            time_offset = current_time - int(
                pd.to_datetime(last_time).timestamp())
            time_offset = f'{int(time_offset)}s'
        else:
            time_offset = os.getenv('RUN_INTERVAL', '24h')

    logger.info(f"Time window: {time_offset}")

    try:
        # Generate job metrics in the specified time window
        logger.info("Generating job metrics...")
        metrics_df = generate_metrics(current_time, time_offset)
        if metrics_df.empty:
            logger.warning("No job metrics generated for this time window")
            return
        logger.info(f"Generated {len(metrics_df)} job metric records")
        react_df = generate_job_react_time(metrics_df)

        # Update the previous incomplete records
        # update the previous unknown category records within retain_time
        unknown_category_records = KustoUtil().query_unknown_category_records(
            retain_time)
        unknown_category_records = update_failure_reason_category(
            unknown_category_records)
        # update the previous empty react records within retain_time
        unknown_react_records = KustoUtil().query_unknown_react_records(
            retain_time)

        unknown_react_records = update_react_time(unknown_react_records,
                                                  metrics_df)
        # filterout records still in unknown category
        unknown_category_records = unknown_category_records[
            unknown_category_records['category'] !=
            'Unknown'] if not unknown_category_records.empty else pd.DataFrame(
            )
        # filterout records whose reactTime is still empty
        unknown_react_records = unknown_react_records[
            unknown_react_records['reactTime'].notna(
            )] if not unknown_react_records.empty else pd.DataFrame()

        # merge updated incomplete records with new records
        if not unknown_category_records.empty:
            metrics_df = pd.concat([metrics_df, unknown_category_records],
                                   ignore_index=True)
        if not unknown_react_records.empty:
            react_df = pd.concat([react_df, unknown_react_records],
                                 ignore_index=True)

        # Ingest records to Kusto
        try:
            logger.info(f"Ingesting metrics to Kusto table: {metrics_table}")
            KustoUtil().ingest_job_metrics_to_kusto(metrics_df, metrics_table)
            logger.info("Successfully ingested metrics to Kusto")
            logger.info(f"Ingesting react times to Kusto table: {react_table}")
            KustoUtil().ingest_job_metrics_to_kusto(react_df, react_table)
            logger.info("Successfully ingested react times to Kusto")
        except Exception as kusto_error:
            logger.error(f"Failed to ingest metrics to Kusto: {kusto_error}")

    except Exception as e:
        logger.error(f"Job data processing failed: {e}")


def main():
    """
    Main entry point: initializes scheduler and starts periodic job-data processing.
    """
    # Get configuration from environment
    interval_minutes = os.getenv('RUN_INTERVAL', '180m')

    logger.info("Job Data Recorder starting...")
    logger.info(
        f"Scheduled to run every {interval_minutes} minutes (fixed interval)")

    # Create scheduler with fixed interval (won't drift due to processing time)
    scheduler = BlockingScheduler()

    # Add job with fixed interval - this ensures runs happen at exact intervals
    # regardless of how long each job takes to complete
    scheduler.add_job(
        process_job_data,
        args=[None],
        trigger=IntervalTrigger(
            minutes=parse_interval(interval_minutes)// 60),
        id='job_data_processor',
        max_instances=1,  # Prevent overlapping runs
        coalesce=True,  # If a run is missed, don't queue multiple runs
        name='Job Data Processor')

    # Run immediately on startup
    logger.info("Running initial data processing...")
    process_job_data()

    # Start the scheduler
    logger.info("Starting fixed-interval scheduler...")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        scheduler.shutdown()


if __name__ == "__main__":
    main()

#! /usr/bin/env python3
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os
import sys
import time
import click
from secops.exceptions import APIError
from parser_manager import ParserManager
from models import ParserError, Operation
from utils import generate_pr_comment_output
from compare import ParserComparator
from dotenv import load_dotenv

LOGGER = logging.getLogger("pac")


@click.group()
@click.pass_context
def cli(ctx):
    """Manages Chronicle SecOps Parsers via the command line."""
    try:
        # Store the manager instance in the Click context object
        ctx.obj = ParserManager()
    except ParserError as e:
        LOGGER.critical(f"Fatal Initialization Error: {e}", exc_info=True)
        sys.exit(1)


@cli.command(name="verify-deploy-parsers")
@click.pass_obj
def verify_and_deploy(manager: ParserManager):
    """Plans, validates, and deploys parser changes to Chronicle."""
    plan = {}
    submitted = []
    has_errors = False
    try:
        LOGGER.info("--- Phase 1: Planning and Local Validation ---")
        plan = manager.plan_deployment()

        ops_to_run = any(d.parser_operation != Operation.NONE
                         or d.parser_ext_operation != Operation.NONE
                         for d in plan.values())
        if not ops_to_run:
            LOGGER.info(
                "No parsers or extensions need to be created or updated.")
            generate_pr_comment_output(plan, [], False)
            return

        LOGGER.info("\n--- Phase 2: Submitting to Chronicle API ---")
        submitted = manager.execute_deployment(plan)
        if submitted:
            LOGGER.info(
                f"\n--- Pausing 60s for Chronicle validation to begin ---")
            time.sleep(60)
        else:
            LOGGER.info("No valid changes to submit.")

        LOGGER.info("\n--- Phase 3: Verifying Submission Status ---")
        plan = manager.verify_submissions(submitted, plan)

    except ParserError as e:
        LOGGER.error(f"A pipeline error occurred: {e}", exc_info=True)
        has_errors = True
    finally:
        generate_pr_comment_output(plan, submitted, has_errors)
        if has_errors:
            sys.exit(1)


@cli.command()
@click.pass_obj
def activate_parsers(manager: ParserManager):
    """Finds and activates parsers that have passed validation."""
    try:
        LOGGER.info(
            "Checking for parsers and extensions ready for activation...")
        count = manager.activate_all_passed()
        if count > 0:
            LOGGER.info(f"Successfully activated {count} item(s).")
        else:
            LOGGER.info("No new items were ready for activation.")
    except ParserError as e:
        LOGGER.error(f"An error occurred during activation: {e}",
                     exc_info=True)
        sys.exit(1)


@cli.command()
@click.option('--log-type',
              '-t',
              type=str,
              help="Generate for a specific parser (log type).")
@click.pass_obj
def generate_events(manager: ParserManager, log_type: str):
    """Generates UDM event YAML files from raw log files."""
    try:
        LOGGER.info("Starting event generation...")
        manager.generate_events(log_type)
        LOGGER.info("Event generation completed successfully.")
    except ParserError as e:
        LOGGER.error(f"Failed to generate events: {e}", exc_info=True)
        sys.exit(1)


@cli.command()
@click.option(
    '--log-type',
    '-t',
    help=
    'Specific log type to ingest (e.g., "OKTA"). Ingests all types if omitted.'
)
@click.pass_obj
def pull_parser(manager: ParserManager, log_type: str):
    """Pulls an active parser from Chronicle and updates or creates it locally."""
    try:
        LOGGER.info(f"Attempting to pull parser for log type: {log_type}...")
        is_update = manager.pull_parser(log_type)

        if is_update is None:
            LOGGER.info(
                f"[{log_type}] No active custom parser found in Chronicle. No action taken."
            )
            return

        if is_update:
            LOGGER.info(
                f"[{log_type}] Parser was updated. Regenerating events...")
            # To regenerate events, we need some sample logs.
            # The user must add them manually if this is a new parser.
            # We can check if there are any logs before attempting to generate events.
            logs_dir = os.path.join("parsers", log_type, "logs")
            if os.path.isdir(logs_dir) and os.listdir(logs_dir):
                manager.generate_events(target_log_type=log_type)
            else:
                LOGGER.warning(
                    f"[{log_type}] No sample logs found in '{logs_dir}'. Skipping event generation."
                )
                LOGGER.warning(
                    f"[{log_type}] Please add sample log files to generate events."
                )

        LOGGER.info(f"Successfully pulled parser for log type: {log_type}.")

    except APIError as e:
        if "NOT_FOUND" in str(e):
            LOGGER.info(
                f"[{log_type}] No active custom parser found in Chronicle. No action taken."
            )
        else:
            LOGGER.error(f"Failed to pull parser: {e}", exc_info=True)
            sys.exit(1)
    except ParserError as e:
        LOGGER.error(f"Failed to pull parser: {e}", exc_info=True)
        sys.exit(1)


@cli.command()
@click.pass_obj
def pull_parsers(manager: ParserManager):
    """Pulls ALL active parsers from Chronicle and updates local files."""
    try:
        LOGGER.info("Starting bulk pull of all parsers...")
        manager.pull_all_parsers()
        LOGGER.info("Bulk pull completed.")
    except ParserError as e:
        LOGGER.error(f"Failed to pull parsers: {e}", exc_info=True)
        sys.exit(1)


@cli.command(name="compare-parsers")
@click.option('--log-type', required=True, help="The log type to compare.")
@click.option(
    '--branch',
    default=None,
    help=
    "The git branch to use as fallback if no active parser found (optional).")
@click.pass_obj
def compare_parsers(manager: ParserManager, log_type: str, branch: str):
    """Compares the current local parser against the active parser in SecOps (or git branch as fallback)."""
    try:
        comparator = ParserComparator(log_type, client=manager.client)
        report = comparator.run(branch=branch)
        # valid report printed by run()
    except Exception as e:
        LOGGER.error(f"Failed to compare parsers: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.
        stdout,  # Explicitly print to stdout for GitHub Actions visibility
        force=True)

    # Ensure our specific logger is also set to INFO
    LOGGER.setLevel(logging.INFO)
    cli()

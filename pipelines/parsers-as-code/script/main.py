#! /usr/bin/env python3
# Copyright 2025 Google LLC
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

import json
import logging
import sys
import time
import click
from parser_manager import ParserManager
from models import ParserError, Operation, ParserValidationStatus, ParserExtensionState
from config import GITHUB_OUTPUT_FILE, PARSER_TYPE_CUSTOM, PARSER_TYPE_PREBUILT
from dotenv import load_dotenv

load_dotenv()

# --- Logger Configuration ---
logging.basicConfig(
    level="INFO",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
LOGGER = logging.getLogger(__name__)


def generate_pr_comment_output(plan: dict, submitted_info: list,
                               has_errors: bool):
    """Generates a structured JSON output for a GitHub PR comment."""
    LOGGER.info("\n--- Generating output for PR comment ---")
    submitted_map = {info['log_type']: info for info in submitted_info}
    report_lines = []

    for log_type, details in sorted(plan.items()):
        if (details['parser_operation'] == Operation.NONE
                and details['parser_ext_operation'] == Operation.NONE
                and not details.get("validation_failed")):
            continue

        parser_type = details['config'].parser_type
        line_parts = [
            f"- **Log Type**: `{log_type}`",
            f"  - **Parser Type**: `{parser_type}`"
        ]

        # --- Parser Details ---
        if details['config'].parser:
            action = details['parser_operation']

            # For PREBUILT parsers, skip parser action reporting (no operations allowed)
            if parser_type == PARSER_TYPE_PREBUILT:
                line_parts.append(
                    f"  - **Parser**: Using PREBUILT parser from SecOps (read-only)"
                )
            else:
                # For CUSTOM parsers, show action
                line_parts.append(f"  - **Parser Action**: `{action.value}`")

                if details.get("validation_failed"):
                    status_text, icon = "EVENT_VALIDATION_FAILED", "❌"
                    details_text = "Not submitted due to local event validation failure."
                elif action in [Operation.CREATE, Operation.UPDATE]:
                    status = details.get("parser_validation_status", "PENDING")
                    icon = "✅" if status == ParserValidationStatus.PASSED.value else "❌" if status == ParserValidationStatus.FAILED.value else "⏳"
                    status_text = f"{status} {icon}"
                    parser_id = submitted_map.get(log_type,
                                                  {}).get('parser_id', 'N/A')
                    action_verb = "Created" if action == Operation.CREATE else "Updated"
                    details_text = f"{action_verb} CUSTOM parser. Parser ID: `{parser_id}`"
                else:  # Operation is NONE, but we're here because something else happened (e.g., ext change)
                    status_text = "NO_CHANGE"
                    details_text = "No changes detected for the CUSTOM parser."

                line_parts.append(f"  - **Validation Status**: {status_text}")
                line_parts.append(f"  - **Details**: {details_text}")

        # --- Parser Extension Details ---
        if details['config'].parser_ext:
            action = details['parser_ext_operation']
            line_parts.append(
                f"  - **Parser Extension Action**: `{action.value}`")

            if details.get("validation_failed"):
                status_text, icon = "EVENT_VALIDATION_FAILED", "❌"
                details_text = "Not submitted due to local event validation failure."
            elif action in [Operation.CREATE, Operation.UPDATE]:
                status = details.get("parser_ext_validation_status", "PENDING")
                icon = "✅" if status == ParserExtensionState.VALIDATED.value else "❌" if status == ParserExtensionState.REJECTED.value else "⏳"
                status_text = f"{status} {icon}"
                ext_id = submitted_map.get(log_type,
                                           {}).get('parser_ext_id', 'N/A')
                action_verb = "Attached" if action == Operation.CREATE else "Updated"
                parser_context = "PREBUILT parser" if parser_type == PARSER_TYPE_PREBUILT else "CUSTOM parser"
                details_text = f"{action_verb} extension to {parser_context}. Extension ID: `{ext_id}`"
            else:  # Operation is NONE
                status_text = "NO_CHANGE"
                details_text = "No changes detected for the parser extension."

            line_parts.append(f"  - **Validation Status**: {status_text}")
            line_parts.append(f"  - **Details**: {details_text}")

        report_lines.append("\n".join(line_parts))

    body = "\n\n".join(report_lines)

    if has_errors:
        title = "❌ Parser Deployment Failed"
        summary = "Errors were encountered during the process. See action logs for details."
    elif not submitted_info and not report_lines:
        title = "✅ All Parsers Up-to-Date"
        summary = "No changes were needed for any parsers or extensions."
        body = "All configurations in the repository are in sync with the active versions in Chronicle."
    else:
        title = "✅ Parser Deployment Plan"
        summary = f"{len(submitted_info)} log type(s) had changes submitted. Review validation status below."

    comment_data = {"title": title, "summary": summary, "details": body}

    if GITHUB_OUTPUT_FILE:
        LOGGER.info("Writing PR comment data to GITHUB_OUTPUT.")
        json_output = json.dumps(comment_data)
        try:
            with open(GITHUB_OUTPUT_FILE, "a") as f:
                f.write(f"pr_comment_data<<EOF\n{json_output}\nEOF\n")
        except IOError as e:
            LOGGER.error(f"Failed to write to GITHUB_OUTPUT file: {e}")
            LOGGER.info(
                f"PR Comment Data (fallback):\n{json.dumps(comment_data, indent=2)}"
            )
    else:
        LOGGER.info(
            f"PR Comment Data (simulation - GITHUB_OUTPUT not set):\n{json.dumps(comment_data, indent=2)}"
        )


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

        ops_to_run = any(d["parser_operation"] != Operation.NONE
                         or d["parser_ext_operation"] != Operation.NONE
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
@click.option('--parser',
              'target_parser_name',
              type=str,
              help="Generate for a specific parser (log type).")
@click.pass_obj
def generate_events(manager: ParserManager, target_parser_name: str):
    """Generates UDM event YAML files from raw log files."""
    try:
        LOGGER.info("Starting event generation...")
        manager.generate_events(target_parser_name)
        LOGGER.info("Event generation completed successfully.")
    except ParserError as e:
        LOGGER.error(f"Failed to generate events: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()

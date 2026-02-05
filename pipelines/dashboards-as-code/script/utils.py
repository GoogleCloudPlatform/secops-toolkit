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

import logging
import os
import sys
import json
from config import GITHUB_OUTPUT_FILE
from dotenv import load_dotenv

PIPELINE_ERRORS = []

load_dotenv()


def setup_logging():
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )


setup_logging()
LOGGER = logging.getLogger(__name__)


def generate_pr_comment_output(plan: dict, has_errors: bool):
    """Generates a structured JSON output for a GitHub PR comment."""
    LOGGER.info("\n--- Generating output for PR comment ---")
    report_lines = []

    for dashboard_name, operation_config in sorted(plan.items()):
        line_parts = [f"- **Dashboard**: `{dashboard_name}`"]

        op = operation_config['operation']
        line_parts.append(f"  - **Dashboard Operation**: `{op.value}`")

        report_lines.append("\n".join(line_parts))

    body = "\n\n".join(report_lines)

    if has_errors:
        title = "❌ Dashboard Plan Failed"
        summary = "Errors were encountered during the process. See action logs for details."
    elif not report_lines:
        title = "✅ All Dashboards Up-to-Date"
        summary = "No changes were needed for any dashboard."
        body = "All configurations in the repository are in sync with the active versions in SecOps."
    else:
        title = "✅ Dashboards Deployment"
        summary = f"{len(plan.keys())} dashboards had changes."

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


def report_pipeline_errors_and_exit():
    """
    If any critical errors were recorded, prints them and exits with status 1.
    Otherwise, exits with status 0.
    """
    if PIPELINE_ERRORS:
        LOGGER.error("--- Pipeline Finished with Errors ---")
        for error in PIPELINE_ERRORS:
            # GitHub Actions error format
            gha_error_message = error.replace('%', '%25').replace(
                '\r', '%0D').replace('\n', '%0A')
            print(f"::error::{gha_error_message}", file=sys.stderr)
        sys.exit(1)
    else:
        LOGGER.info("Operation completed successfully.")
        sys.exit(0)

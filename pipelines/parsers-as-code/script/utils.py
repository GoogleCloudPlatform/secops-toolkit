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

import difflib
import re
import yaml
import os
import logging
import json
from models import Operation, ParserValidationStatus, ParserExtensionState
from config import GITHUB_OUTPUT_FILE

LOGGER = logging.getLogger("pac")


def filter_lines(lines_list: list, ignore_patterns: list = None) -> list:
    """
    Filters lines from a list based on a list of regex patterns.

    Args:
        lines_list: A list of strings (lines).
        ignore_patterns: A list of regex patterns to ignore.

    Returns:
        A new list with the matching lines removed.
    """
    if not ignore_patterns:
        return lines_list
    return [
        line for line in lines_list
        if not any(re.search(pattern, line) for pattern in ignore_patterns)
    ]


def compare_yaml_files(file1_path: str,
                       file2_path: str,
                       ignore_patterns: list = None) -> list | None:
    """
    Compares two YAML files, ignoring specified patterns, and returns the differences.

    Args:
        file1_path: Path to the first YAML file.
        file2_path: Path to the second YAML file.
        ignore_patterns: A list of regex patterns to ignore in the comparison.

    Returns:
        A list of difference lines, or None if there are no differences.
    """
    with open(file1_path, 'r', encoding='utf-8') as f1:
        content1 = f1.read()
    with open(file2_path, 'r', encoding='utf-8') as f2:
        content2 = f2.read()

    try:
        data1 = yaml.safe_load(content1)
        data2 = yaml.safe_load(content2)
        processed_content1 = yaml.dump(data1,
                                       default_flow_style=False,
                                       sort_keys=True)
        processed_content2 = yaml.dump(data2,
                                       default_flow_style=False,
                                       sort_keys=True)
    except yaml.YAMLError:
        # Fallback to plain text if YAML is invalid
        processed_content1 = content1
        processed_content2 = content2

    lines1 = filter_lines(processed_content1.splitlines(), ignore_patterns)
    lines2 = filter_lines(processed_content2.splitlines(), ignore_patterns)

    diff_generator = difflib.Differ().compare(lines1, lines2)
    differences = [
        line for line in diff_generator if line.startswith(('+', '-'))
    ]
    return differences if differences else None


def process_data_for_dump(data):
    """
    Recursively processes data to be dumped to YAML.

    Currently, it sets the value of 'collectedTimestamp' to an empty string to
    ensure consistent comparisons for generated events.

    Args:
        data: The data structure (dict or list) to process.

    Returns:
        The processed data structure.
    """
    if isinstance(data, dict):
        return {
            k: '' if k == 'collectedTimestamp' else process_data_for_dump(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [process_data_for_dump(item) for item in data]
    return data


def count_total_events(events: list) -> int:
    """Counts total events in a list of parsed events (handling batches)."""
    count = 0
    for item in events:
        if isinstance(item, dict) and "events" in item and isinstance(
                item["events"], list):
            count += len(item["events"])
        elif isinstance(item, list):
            count += len(item)
        else:
            count += 1
    return count


def generate_event_files(client,
                         log_type: str,
                         parser_code: str,
                         parser_ext_code: str | None,
                         logs_dir: str,
                         events_dir: str,
                         file_suffix: str = "") -> dict:
    """
    Generates UDM event files from logs using the provided parser content.
    
    Args:
        client: SecOpsClient instance.
        log_type: The log type string.
        parser_code: The parser CBN content.
        parser_ext_code: The parser extension CBN content (optional).
        logs_dir: Directory containing input log files.
        events_dir: Directory to write output YAML files.
        file_suffix: Suffix to append to output filenames (before .yaml).

    Returns:
        dict: Mapping of log_filename -> (output_path, total_event_count, events_data)
    """
    results = {}
    if not os.path.exists(logs_dir):
        LOGGER.warning(f"[{log_type}] Logs directory not found: {logs_dir}")
        return results

    log_files = [
        f for f in sorted(os.listdir(logs_dir))
        if os.path.isfile(os.path.join(logs_dir, f))
    ]

    if not log_files:
        LOGGER.warning(f"[{log_type}] No log files found in {logs_dir}")
        return results

    os.makedirs(events_dir, exist_ok=True)

    for log_filename in log_files:
        log_filepath = os.path.join(logs_dir, log_filename)
        with open(log_filepath, "r", encoding="utf-8") as f:
            raw_logs = [line.strip() for line in f if line.strip()]

        if not raw_logs:
            continue

        LOGGER.info(f"[{log_type}] Generating events for {log_filename}...")
        try:
            response = client.run_parser(log_type=log_type,
                                         parser_code=parser_code,
                                         parser_extension_code=parser_ext_code,
                                         logs=raw_logs)
            events = [
                res.get("parsedEvents", [])
                for res in response.get("runParserResults", [])
            ]

            # Construct output filename
            base_name = os.path.splitext(log_filename)[0]
            output_filename = f"{base_name}{file_suffix}.yaml"
            output_path = os.path.join(events_dir, output_filename)

            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(process_data_for_dump(events), f, sort_keys=True)

            total_count = count_total_events(events)
            results[log_filename] = (output_path, total_count, events)
            LOGGER.info(
                f"[{log_type}] Saved {total_count} events to {output_filename}"
            )

        except Exception as e:
            LOGGER.error(
                f"[{log_type}] Failed to generate events for {log_filename}: {e}"
            )

    return results


def generate_pr_comment_output(plan: dict, submitted_info: list,
                               has_errors: bool):
    """Generates a structured JSON output for a GitHub PR comment."""
    LOGGER.info("\n--- Generating output for PR comment ---")
    submitted_map = {info['log_type']: info for info in submitted_info}
    report_lines = ["\n"]

    for log_type, details in sorted(plan.items()):
        if (details.parser_operation == Operation.NONE
                and details.parser_ext_operation == Operation.NONE
                and not details.validation_failed):
            continue

        line_parts = [f"- **Log Type**: `{log_type}`"]

        # --- Parser Details ---
        if details.config.parser:
            action = details.parser_operation
            line_parts.append(f"  - **Parser Action**: `{action.value}`")

            if details.validation_failed:
                status_text, icon = "EVENT_VALIDATION_FAILED", "❌"
                details_text = "Not submitted due to local event validation failure."
            elif action in [
                    Operation.CREATE, Operation.UPDATE, Operation.RELEASE
            ]:
                if action == Operation.RELEASE:
                    status_text = "READY_TO_RELEASE"
                    details_text = "Pending Release Candidate matched. Ready for activation key."
                    icon = "🚀"
                else:
                    status = details.parser_validation_status or "PENDING"
                    icon = "✅" if status == ParserValidationStatus.PASSED.value else "❌" if status == ParserValidationStatus.FAILED.value else "⏳"
                    status_text = f"{status} {icon}"
                    parser_id = submitted_map.get(log_type,
                                                  {}).get('parser_id', 'N/A')
                    details_text = f"Submitted for deployment. Parser ID: `{parser_id}`"
            else:  # Operation is NONE, but we're here because something else happened (e.g., ext change)
                status_text = "NO_CHANGE"
                details_text = "No changes detected for the parser."

            line_parts.append(f"  - **Validation Status**: {status_text}")
            line_parts.append(f"  - **Details**: {details_text}")

        # --- Parser Extension Details ---
        if details.config.parser_ext:
            action = details.parser_ext_operation
            line_parts.append(
                f"  - **Parser Extension Action**: `{action.value}`")

            if details.validation_failed:
                status_text, icon = "EVENT_VALIDATION_FAILED", "❌"
                details_text = "Not submitted due to local event validation failure."
            elif action in [Operation.CREATE, Operation.UPDATE]:
                status = details.parser_ext_validation_status or "PENDING"
                icon = "✅" if status == ParserExtensionState.VALIDATED.value else "❌" if status == ParserExtensionState.REJECTED.value else "⏳"
                status_text = f"{status} {icon}"
                ext_id = submitted_map.get(log_type,
                                           {}).get('parser_ext_id', 'N/A')
                details_text = f"Submitted for deployment. Extension ID: `{ext_id}`"
            else:  # Operation is NONE
                status_text = "NO_CHANGE"
                details_text = "No changes detected for the parser extension."

            line_parts.append(f"  - **Validation Status**: {status_text}")
            line_parts.append(f"  - **Details**: {details_text}")

        # --- Comparison Report ---
        if details.comparison_report:
            report = details.comparison_report
            line_parts.append(
                f"\n<details><summary><b>📉 UDM Comparison Report</b></summary>\n\n```text\n{report}\n```\n</details>"
            )

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

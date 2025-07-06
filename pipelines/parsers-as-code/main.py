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

import base64
import difflib
import os
import re
import sys
import tempfile
import json
import time
import yaml
import click
import logging
from enum import Enum
from secops import SecOpsClient

# --- Logger Configuration ---
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
LOGGER = logging.getLogger(__name__)


class ParserState(Enum):
    """Represents the state of a parser in SecOps."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ParserValidationStatus(Enum):
    """Represents the validation outcome of a parser submission."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    INCOMPLETE = "INCOMPLETE"


class Operation(Enum):
    """Represents the planned action for a parser."""
    NONE = "NONE"
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    ACTIVATE = "ACTIVATE"


# --- Configuration & Constants ---
SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

# Environment Variables
SECOPS_CUSTOMER_ID = os.environ.get("SECOPS_CUSTOMER_ID")
SECOPS_PROJECT_ID = os.environ.get("SECOPS_PROJECT_ID")
SECOPS_REGION = os.environ.get("SECOPS_REGION")

PARSERS_ROOT_DIR = "./parsers"
PARSER_CONFIG_FILENAME = "parser.conf"
LOGS_FOLDER_NAME = "logs"
EVENTS_FOLDER_NAME = "events"
PARSER_TYPE_CUSTOM = "CUSTOM"  # API constant, kept as is.

# Global list to track critical errors for final reporting.
PIPELINE_ERRORS = []


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


def initialize_chronicle_client():
    """Initializes and returns a Chronicle SecOps client."""
    if not all([SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION]):
        err_msg = "Missing required SecOps environment variables: SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION."
        LOGGER.error(err_msg)
        PIPELINE_ERRORS.append(err_msg)
        return None
    try:
        client = SecOpsClient()
        chronicle = client.chronicle(customer_id=SECOPS_CUSTOMER_ID,
                                     project_id=SECOPS_PROJECT_ID,
                                     region=SECOPS_REGION)
        LOGGER.info("Chronicle client initialized successfully.")
        return chronicle
    except Exception as e:
        err_msg = f"Failed to initialize Chronicle client: {e}"
        LOGGER.error(err_msg)
        PIPELINE_ERRORS.append(err_msg)
        return None


def filter_lines(lines_list: list, ignore_patterns: list = None):
    """Filters lines based on a list of regex patterns."""
    if not ignore_patterns:
        return lines_list
    return [
        line for line in lines_list
        if not any(re.search(pattern, line) for pattern in ignore_patterns)
    ]


def compare_yaml_files(file1_path: str,
                       file2_path: str,
                       ignore_patterns: list = None):
    """
    Compares two YAML files, ignoring specified patterns. Returns diffs or None.
    """
    try:
        with open(file1_path, 'r', encoding='utf-8') as f1:
            content1 = f1.read()
        with open(file2_path, 'r', encoding='utf-8') as f2:
            content2 = f2.read()
    except Exception as e:
        err_msg = f"Error reading files for comparison: {e}"
        LOGGER.error(err_msg)
        PIPELINE_ERRORS.append(err_msg)
        return None

    try:
        data1 = yaml.safe_load(content1)
        data2 = yaml.safe_load(content2)
        processed_content1 = yaml.dump(data1,
                                       default_flow_style=False,
                                       sort_keys=True)
        processed_content2 = yaml.dump(data2,
                                       default_flow_style=False,
                                       sort_keys=True)
    except yaml.YAMLError as e:
        LOGGER.warning(
            f"YAML parsing error when comparing, falling back to plain text comparison: {e}"
        )
        processed_content1 = content1
        processed_content2 = content2

    lines1 = filter_lines(processed_content1.splitlines(), ignore_patterns)
    lines2 = filter_lines(processed_content2.splitlines(), ignore_patterns)

    diff_generator = difflib.Differ().compare(lines1, lines2)
    differences = [
        line for line in diff_generator if line.startswith(('+', '-'))
    ]
    return differences if differences else None


def _get_active_parser_from_chronicle(chronicle_client, log_type: str):
    """Fetches the metadata of the active custom parser from Chronicle."""
    try:
        parsers = chronicle_client.list_parsers(log_type=log_type)
        for parser_meta in parsers:
            if parser_meta.get(
                    "type") == PARSER_TYPE_CUSTOM and parser_meta.get(
                        "state") == ParserState.ACTIVE.value:
                if "cbn" not in parser_meta:
                    LOGGER.warning(
                        f"Active parser for '{log_type}' is missing 'cbn' content: {parser_meta.get('name')}"
                    )
                    return None
                return parser_meta
        return None
    except Exception as e:
        LOGGER.warning(f"Error fetching active parser for '{log_type}': {e}")
        return None


def _get_release_parser_from_chronicle(chronicle_client, log_type: str):
    """Fetches a non-active parser that has completed validation."""
    try:
        parsers = chronicle_client.list_parsers(log_type=log_type)
        valid_statuses = [
            ParserValidationStatus.PASSED.value,
            ParserValidationStatus.FAILED.value
        ]
        for parser_meta in parsers:
            if (parser_meta.get("type") == PARSER_TYPE_CUSTOM
                    and parser_meta.get("state") != ParserState.ACTIVE.value
                    and parser_meta.get("validationStage") in valid_statuses):
                if "cbn" not in parser_meta:
                    LOGGER.warning(
                        f"Release candidate parser for '{log_type}' is missing 'cbn' content: {parser_meta.get('name')}"
                    )
                    return None
                return parser_meta
        return None
    except Exception as e:
        LOGGER.warning(
            f"Error fetching release candidate parser for '{log_type}': {e}")
        return None


def _discover_parser_configs(root_dir: str):
    """
    A generator that finds and yields parser configurations from a root directory.
    """
    if not os.path.isdir(root_dir):
        err_msg = f"Root parsers folder '{root_dir}' does not exist."
        LOGGER.error(err_msg)
        PIPELINE_ERRORS.append(err_msg)
        return

    found_parsers = False
    for item in sorted(os.listdir(root_dir)):
        parser_dir_path = os.path.join(root_dir, item)
        if not os.path.isdir(parser_dir_path):
            continue

        log_type = item
        parser_conf_path = os.path.join(parser_dir_path,
                                        PARSER_CONFIG_FILENAME)
        if os.path.isfile(parser_conf_path):
            found_parsers = True
            try:
                with open(parser_conf_path, 'r', encoding='utf-8') as f:
                    repo_parser_content = f.read()
                LOGGER.info(
                    f"Discovered parser config for log type '{log_type}'.")
                yield log_type, repo_parser_content, parser_dir_path
            except Exception as e:
                err_msg = f"Error reading parser config in '{parser_dir_path}': {e}"
                LOGGER.error(err_msg)
                PIPELINE_ERRORS.append(err_msg)
        else:
            LOGGER.info(
                f"No '{PARSER_CONFIG_FILENAME}' in '{parser_dir_path}', skipping."
            )

    if not found_parsers and not PIPELINE_ERRORS:
        LOGGER.info(
            f"No parsers with '{PARSER_CONFIG_FILENAME}' found in '{root_dir}'."
        )


def _validate_parser_events(chronicle_client, log_type, repo_parser_content,
                            parser_dir_path):
    """
    Validates that the local parser generates the expected events.
    Returns True if valid, False otherwise.
    """
    logs_subfolder = os.path.join(parser_dir_path, LOGS_FOLDER_NAME)
    events_subfolder = os.path.join(parser_dir_path, EVENTS_FOLDER_NAME)

    if not os.path.isdir(logs_subfolder):
        err_msg = f"[{log_type}] Missing '{LOGS_FOLDER_NAME}/' folder. Cannot validate."
        LOGGER.error(err_msg)
        PIPELINE_ERRORS.append(err_msg)
        return False

    if not os.path.isdir(events_subfolder):
        err_msg = f"[{log_type}] Missing '{EVENTS_FOLDER_NAME}/' folder. Cannot compare events."
        LOGGER.error(err_msg)
        PIPELINE_ERRORS.append(err_msg)
        return False

    all_raw_logs, all_expected_events = [], []
    try:
        # Aggregate all logs
        for log_filename in sorted(os.listdir(logs_subfolder)):
            log_filepath = os.path.join(logs_subfolder, log_filename)
            if os.path.isfile(log_filepath):
                with open(log_filepath, "r", encoding='utf-8') as lf:
                    all_raw_logs.extend(
                        [line.strip() for line in lf if line.strip()])
        # Aggregate all expected events
        for event_filename in sorted(os.listdir(events_subfolder)):
            if event_filename.endswith(".yaml"):
                event_filepath = os.path.join(events_subfolder, event_filename)
                with open(event_filepath, "r", encoding='utf-8') as ef:
                    loaded_events = yaml.safe_load(ef)
                    if isinstance(loaded_events, list):
                        all_expected_events.extend(loaded_events)
    except Exception as e:
        err_msg = f"[{log_type}] Error reading log or event files for validation: {e}"
        LOGGER.error(err_msg)
        PIPELINE_ERRORS.append(err_msg)
        return False

    if not all_raw_logs:
        LOGGER.info(
            f"[{log_type}] No log entries found. Skipping event generation diff."
        )
        return True

    temp_new_events_filepath, temp_expected_events_filepath = "", ""
    try:
        response = chronicle_client.run_parser(log_type=log_type,
                                               parser_code=repo_parser_content,
                                               parser_extension_code=None,
                                               logs=all_raw_logs)
        if not response or "runParserResults" not in response:
            err_msg = f"[{log_type}] Invalid response from run_parser API: {response}"
            LOGGER.error(err_msg)
            PIPELINE_ERRORS.append(err_msg)
            return False

        generated_events = []
        for res in response.get("runParserResults", []):
            generated_events.append(res.get("parsedEvents", []))

        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".yaml") as f_new, \
                tempfile.NamedTemporaryFile("w+", delete=False, suffix=".yaml") as f_exp:
            temp_new_events_filepath = f_new.name
            temp_expected_events_filepath = f_exp.name
            yaml.dump(process_data_for_dump(generated_events),
                      f_new,
                      sort_keys=True)
            yaml.dump(process_data_for_dump(all_expected_events),
                      f_exp,
                      sort_keys=True)

        diffs = compare_yaml_files(temp_expected_events_filepath,
                                   temp_new_events_filepath,
                                   ["timestamp", "Timestamp", "etag"])
        if diffs:
            err_msg_header = f"[{log_type}] Differences found between generated and expected events:"
            LOGGER.error(err_msg_header)
            PIPELINE_ERRORS.append(err_msg_header)
            for line in diffs:
                LOGGER.error(f"    {line}")
            return False

        LOGGER.info(f"[{log_type}] Event validation passed.")
        return True
    except Exception as e:
        err_msg = f"[{log_type}] Critical error during event generation/comparison: {e}"
        LOGGER.error(err_msg)
        PIPELINE_ERRORS.append(err_msg)
        return False
    finally:
        if os.path.exists(temp_new_events_filepath):
            os.remove(temp_new_events_filepath)
        if os.path.exists(temp_expected_events_filepath):
            os.remove(temp_expected_events_filepath)


def process_data_for_dump(data):
    """
    Recursively sets the value of 'collectedTimestamp' to an empty string.
    """
    if isinstance(data, dict):
        return {
            k: '' if k == 'collectedTimestamp' else process_data_for_dump(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [process_data_for_dump(item) for item in data]
    return data


# --- CLI Commands ---
@click.group()
def cli():
    """Manages Chronicle SecOps Parsers."""
    pass


@cli.command(name="verify-deploy-parsers")
def verify_deploy_parsers():
    """
    Plans parser changes, validates them, and submits them to Chronicle.
    """
    LOGGER.info("Starting verify-deploy-parsers operation...")
    chronicle = initialize_chronicle_client()
    if not chronicle:
        report_pipeline_errors_and_exit()

    parser_operations = {}

    # --- Phase 1: Plan Operations & Validate Events ---
    LOGGER.info(
        "\n--- Phase 1: Planning Parser Operations and Validating Events ---")
    for log_type, repo_parser_content, parser_dir_path in _discover_parser_configs(
            PARSERS_ROOT_DIR):
        active_parser = _get_active_parser_from_chronicle(chronicle, log_type)
        operation = Operation.NONE

        if active_parser:
            try:
                active_content = base64.b64decode(
                    active_parser["cbn"]).decode('utf-8')
                if active_content.strip() != repo_parser_content.strip():
                    LOGGER.info(
                        f"[{log_type}] Differences detected. UPDATE required.")
                    operation = Operation.UPDATE
                else:
                    LOGGER.info(f"[{log_type}] No changes detected.")
            except Exception as e:
                err_msg = f"[{log_type}] Error comparing with active parser: {e}. Assuming UPDATE."
                LOGGER.error(err_msg)
                PIPELINE_ERRORS.append(err_msg)
                operation = Operation.UPDATE
        else:
            LOGGER.info(
                f"[{log_type}] No active parser found. CREATE required.")
            operation = Operation.CREATE

        # If a change is planned, validate events before confirming the operation
        is_valid = True
        if operation != Operation.NONE:
            is_valid = _validate_parser_events(chronicle, log_type,
                                               repo_parser_content,
                                               parser_dir_path)

        parser_operations[log_type] = {
            "operation": operation if is_valid else Operation.NONE,
            "content": repo_parser_content,
            "validation_failed": not is_valid
        }

    # Abort if any critical errors occurred during planning (e.g., file read errors)
    if any(
            op_details.get("validation_failed")
            for op_details in parser_operations.values()) or PIPELINE_ERRORS:
        LOGGER.error(
            "Aborting before submission due to planning or validation errors.")
        generate_pr_comment_output(parser_operations, [], True)
        report_pipeline_errors_and_exit()

    parsers_to_submit = {
        lt: op
        for lt, op in parser_operations.items()
        if op["operation"] in [Operation.CREATE, Operation.UPDATE]
    }
    if not parsers_to_submit:
        LOGGER.info("No parsers need to be created or updated.")
        generate_pr_comment_output({}, [], False)
        report_pipeline_errors_and_exit()

    # --- Phase 2: Submit Parsers to Chronicle ---
    LOGGER.info("\n--- Phase 2: Submitting Parsers to Chronicle ---")
    submitted_info = []
    for log_type, op_details in parsers_to_submit.items():
        try:
            LOGGER.info(
                f"[{log_type}] Submitting parser for {op_details['operation'].value}..."
            )
            created_meta = chronicle.create_parser(
                log_type=log_type,
                parser_code=op_details['content'],
                validated_on_empty_logs=False)
            parser_name = created_meta.get("name")
            if not parser_name:
                raise ValueError(
                    "create_parser API call did not return a parser name.")
            parser_id = parser_name.split("/")[-1]
            LOGGER.info(
                f"[{log_type}] Submitted successfully. ID: {parser_id}.")
            submitted_info.append({
                "log_type": log_type,
                "id": parser_id,
                "name": parser_name
            })
        except Exception as e:
            err_msg = f"[{log_type}] Error submitting parser: {e}"
            LOGGER.error(err_msg)
            PIPELINE_ERRORS.append(err_msg)

    LOGGER.info("\n--- Pause for SecOps Parser Validation ---")
    if submitted_info: time.sleep(60)

    # --- Phase 3: Verify Submission and Generate Output ---
    LOGGER.info("\n--- Verifying Submission Status ---")
    for info in submitted_info:
        try:
            parser = chronicle.get_parser(log_type=info['log_type'],
                                          id=info['id'])
            parser_operations[info["log_type"]]["validation_status"] = parser[
                "validationStage"]
            LOGGER.info(
                f"[{info['log_type']}] Validation status: {parser['validationStage']}"
            )
        except Exception as e:
            err_msg = f"[{info['log_type']}] Could not verify validation status for parser {info['id']}: {e}"
            LOGGER.error(err_msg)
            PIPELINE_ERRORS.append(err_msg)

    generate_pr_comment_output(parser_operations, submitted_info,
                               bool(PIPELINE_ERRORS))
    report_pipeline_errors_and_exit()


def generate_pr_comment_output(parser_operations: dict, submitted_info: list,
                               has_errors: bool):
    """
    Generates a structured JSON output for a GitHub PR comment.
    """
    LOGGER.info("\n--- Generating output for PR comment ---")
    submitted_map = {info['log_type']: info for info in submitted_info}
    report_lines = []

    for log_type, details in sorted(parser_operations.items()):
        if details.get('operation') == Operation.NONE and not details.get(
                "validation_failed"):
            continue

        validation_status = details.get("validation_status", "PENDING")
        if details.get("validation_failed"):
            validation_status = "EVENT_VALIDATION_FAILED"

        icon = "⏳"
        if validation_status == ParserValidationStatus.PASSED.value: icon = "✅"
        elif validation_status in [
                ParserValidationStatus.FAILED.value, "EVENT_VALIDATION_FAILED"
        ]:
            icon = "❌"

        line = f"- **Log Type**: `{log_type}`\n"
        line += f"  - **SecOps Validation**: {validation_status} {icon}\n"

        if submitted_map.get(log_type):
            line += f"  - **Action**: Submitted for deployment\n"
            line += f"  - **Parser ID**: `{submitted_map.get(log_type, {}).get('id', 'N/A')}`"
        elif details.get("validation_failed"):
            line += f"  - **Action**: Not submitted due to event validation failure"
        else:
            line += f"  - **Action**: Not submitted due to other errors"

        report_lines.append(line)

    body = "\n".join(report_lines)
    if has_errors:
        title = "❌ Parser Deployment Failed"
        summary = "Errors were encountered. See action logs for details."
    elif not submitted_info and not report_lines:
        title = "✅ All Parsers Up-to-Date"
        summary = "No changes were needed."
        body = ""
    else:
        title = "✅ Parser Deployment Plan"
        summary = f"{len(submitted_info)} parser(s) submitted. Check validation status above."

    comment_data = {"title": title, "summary": summary, "details": body}
    github_output_file = os.getenv('GITHUB_OUTPUT')
    if github_output_file:
        LOGGER.info("Writing PR comment data to GITHUB_OUTPUT.")
        json_output = json.dumps(comment_data)
        with open(github_output_file, "a") as f:
            f.write(f"pr_comment_data<<EOF\n{json_output}\nEOF\n")
    else:
        LOGGER.info(f"PR Comment Data:\n{json.dumps(comment_data, indent=2)}")


@cli.command(name="activate-parsers")
def activate_parsers():
    """
    Checks validation status of submitted parsers and activates them if passed.
    """
    LOGGER.info("Starting activate-parsers operation...")
    chronicle = initialize_chronicle_client()
    if not chronicle: report_pipeline_errors_and_exit()

    activated_log_types = []
    LOGGER.info("\n--- Checking and Activating Parsers ---")
    for log_type, repo_parser_content, _ in _discover_parser_configs(
            PARSERS_ROOT_DIR):
        release_parser = _get_release_parser_from_chronicle(
            chronicle, log_type)
        if not release_parser:
            LOGGER.info(
                f"[{log_type}] No release candidate parser found. Skipping.")
            continue

        try:
            release_content = base64.b64decode(
                release_parser["cbn"]).decode('utf-8')
            if release_content.strip() != repo_parser_content.strip():
                err_msg = f"[{log_type}] Mismatch! Repo content differs from release candidate '{release_parser.get('name')}'. Activation aborted for safety."
                LOGGER.error(err_msg)
                PIPELINE_ERRORS.append(err_msg)
                continue

            parser_id = release_parser["name"].split("/")[-1]
            validation_stage = release_parser.get("validationStage")
            LOGGER.info(
                f"[{log_type}] Release candidate {parser_id} status: {validation_stage}"
            )

            if validation_stage == ParserValidationStatus.PASSED.value:
                LOGGER.info(
                    f"[{log_type}] Activating parser ID: {parser_id}...")
                chronicle.activate_parser(log_type=log_type, id=parser_id)
                LOGGER.info(f"[{log_type}] Parser activated successfully.")
                activated_log_types.append(log_type)
            elif validation_stage == ParserValidationStatus.FAILED.value:
                errors = release_parser.get("validationErrors", "N/A")
                err_msg = f"[{log_type}] Cannot activate parser {parser_id}. Validation FAILED. Errors: {errors}"
                LOGGER.error(err_msg)
                PIPELINE_ERRORS.append(err_msg)
            else:
                err_msg = f"[{log_type}] Cannot activate parser {parser_id}. Status is '{validation_stage}'."
                LOGGER.error(err_msg)
                PIPELINE_ERRORS.append(err_msg)
        except Exception as e:
            err_msg = f"[{log_type}] Error during activation for parser '{release_parser.get('name')}': {e}"
            LOGGER.error(err_msg)
            PIPELINE_ERRORS.append(err_msg)

    if activated_log_types:
        LOGGER.info(
            f"\nSuccessfully activated parsers for: {', '.join(activated_log_types)}"
        )
    elif not PIPELINE_ERRORS:
        LOGGER.info("No parsers were activated.")

    report_pipeline_errors_and_exit()


@cli.command(name="generate-events")
@click.option('--parser',
              'target_parser_name',
              type=str,
              default=None,
              help="Generate events for a specific parser (log type).")
def generate_events_cmd(target_parser_name: str = None):
    """
    Generates UDM event YAML files from raw log files for each parser.
    """
    LOGGER.info("Starting generate-events operation...")
    chronicle = initialize_chronicle_client()
    if not chronicle: report_pipeline_errors_and_exit()

    generated_files_count = 0
    parser_iterator = _discover_parser_configs(PARSERS_ROOT_DIR)
    if target_parser_name:
        parser_iterator = (p for p in parser_iterator
                           if p[0] == target_parser_name)

    for log_type, repo_parser_content, parser_dir_path in parser_iterator:
        logs_path = os.path.join(parser_dir_path, LOGS_FOLDER_NAME)
        events_path = os.path.join(parser_dir_path, EVENTS_FOLDER_NAME)
        if not os.path.isdir(logs_path):
            LOGGER.info(
                f"[{log_type}] No '{LOGS_FOLDER_NAME}' folder, skipping.")
            continue

        os.makedirs(events_path, exist_ok=True)
        for log_filename in sorted(os.listdir(logs_path)):
            log_filepath = os.path.join(logs_path, log_filename)
            if not os.path.isfile(log_filepath): continue

            event_filename = os.path.splitext(log_filename)[0] + ".yaml"
            event_filepath = os.path.join(events_path, event_filename)
            try:
                with open(log_filepath, "r", encoding='utf-8') as lf:
                    raw_logs = [line.strip() for line in lf if line.strip()]

                if not raw_logs:
                    LOGGER.info(
                        f"[{log_type}] Log file '{log_filename}' is empty, writing empty event file."
                    )
                    with open(event_filepath, "w", encoding='utf-8') as ef:
                        yaml.dump([], ef)
                    generated_files_count += 1
                    continue

                response = chronicle.run_parser(
                    log_type=log_type,
                    parser_code=repo_parser_content,
                    parser_extension_code=None,
                    logs=raw_logs)
                if not response or "runParserResults" not in response:
                    raise ValueError(
                        f"Invalid API response for '{log_filename}': {response}"
                    )

                events = []
                for res in response.get("runParserResults", []):
                    events.append(res.get("parsedEvents", []))

                with open(event_filepath, "w", encoding='utf-8') as ef:
                    yaml.dump(process_data_for_dump(events),
                              ef,
                              sort_keys=True)

                LOGGER.info(
                    f"[{log_type}] Successfully generated events for '{log_filename}'."
                )
                generated_files_count += 1
            except Exception as e:
                err_msg = f"[{log_type}] Failed to generate events for '{log_filename}': {e}"
                LOGGER.error(err_msg)
                PIPELINE_ERRORS.append(err_msg)

    if generated_files_count > 0 and not PIPELINE_ERRORS:
        LOGGER.info(
            f"\nSuccessfully generated/updated {generated_files_count} event file(s)."
        )
    elif not PIPELINE_ERRORS:
        LOGGER.info("No event files were generated.")

    report_pipeline_errors_and_exit()


if __name__ == "__main__":
    cli()

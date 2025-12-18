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
import logging
import os
import tempfile
import yaml
from typing import List
from secops import SecOpsClient
from config import SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION
from models import (LogTypeConfig, Operation, ParserState,
                    ParserExtensionState, ParserValidationStatus,
                    ValidationError, ParserError, APIError)
from config import (PARSERS_ROOT_DIR, PARSER_CONFIG_FILENAME,
                    PARSER_EXT_CONFIG_FILENAME, LOGS_FOLDER_NAME,
                    EVENTS_FOLDER_NAME, PARSER_TYPE_CUSTOM, PARSER_TYPE_PREBUILT)
from utils import compare_yaml_files, process_data_for_dump

LOGGER = logging.getLogger(__name__)


class ParserManager:
    """Manages the lifecycle of SecOps parsers and extensions."""

    def __init__(self):
        if not all([SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION]):
            raise APIError(
                "Missing SecOps env vars: SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION."
            )
        try:
            self.client = SecOpsClient().chronicle(
                customer_id=SECOPS_CUSTOMER_ID,
                project_id=SECOPS_PROJECT_ID,
                region=SECOPS_REGION)
            LOGGER.info("SecOps client initialized successfully.")
        except Exception as e:
            raise APIError(f"Failed to initialize SecOps client: {e}") from e

    def discover_local_configs(self) -> List[LogTypeConfig]:
        """Scans the local filesystem for parser configurations."""
        log_type_configs = []
        if not os.path.isdir(PARSERS_ROOT_DIR):
            raise ParserError(
                f"Root parsers folder '{PARSERS_ROOT_DIR}' does not exist.")

        for item in sorted(os.listdir(PARSERS_ROOT_DIR)):
            parser_dir_path = os.path.join(PARSERS_ROOT_DIR, item)
            if not os.path.isdir(parser_dir_path):
                continue

            config = LogTypeConfig(log_type=item, dir_path=parser_dir_path)

            parser_conf_path = os.path.join(parser_dir_path,
                                            PARSER_CONFIG_FILENAME)
            parser_ext_conf_path = os.path.join(parser_dir_path,
                                                PARSER_EXT_CONFIG_FILENAME)

            # Check if parser.conf exists
            has_parser_conf = os.path.isfile(parser_conf_path)
            has_parser_ext_conf = os.path.isfile(parser_ext_conf_path)

            if has_parser_conf:
                with open(parser_conf_path, 'r', encoding='utf-8') as f:
                    config.parser = f.read()
                config.parser_type = PARSER_TYPE_CUSTOM

            if has_parser_ext_conf:
                with open(parser_ext_conf_path, 'r', encoding='utf-8') as f:
                    config.parser_ext = f.read()

            # If only parser_extension.conf exists, it's a PREBUILT parser
            if not has_parser_conf and has_parser_ext_conf:
                config.parser_type = PARSER_TYPE_PREBUILT
                # Fetch the active prebuilt parser content from SecOps
                try:
                    prebuilt_content = self._get_active_prebuilt_parser(config.log_type)
                    if prebuilt_content:
                        config.parser = prebuilt_content
                        LOGGER.info(f"[{config.log_type}] Using PREBUILT parser from SecOps.")
                    else:
                        LOGGER.warning(
                            f"[{config.log_type}] No active PREBUILT parser found in SecOps. "
                            "Parser extension will be managed, but parser content unavailable for validation."
                        )
                except Exception as e:
                    LOGGER.warning(
                        f"[{config.log_type}] Could not fetch PREBUILT parser: {e}. "
                        "Parser extension will be managed, but validation may be limited."
                    )

            if config.parser or config.parser_ext:
                log_type_configs.append(config)

        return log_type_configs

    def _get_active_prebuilt_parser(self, log_type: str) -> str | None:
        """Fetches the content of an active PREBUILT parser."""
        try:
            parsers = self.client.list_parsers(log_type)
            for parser in parsers:
                if (parser.get("type") == PARSER_TYPE_PREBUILT
                        and parser.get("state") == ParserState.ACTIVE.value
                        and "cbn" in parser):
                    return base64.b64decode(parser["cbn"]).decode('utf-8')
        except Exception as e:
            LOGGER.debug(f"Error fetching PREBUILT parser for {log_type}: {e}")
        return None

    def _get_any_prebuilt_parser(self, log_type: str) -> str | None:
        """Fetches any PREBUILT parser (active or inactive) for the log type.

        This is used for event generation where we need the parser content
        regardless of its activation status.
        """
        try:
            parsers = self.client.list_parsers(log_type)
            for parser in parsers:
                if parser.get("type") == PARSER_TYPE_PREBUILT and "cbn" in parser:
                    return base64.b64decode(parser["cbn"]).decode('utf-8')
        except Exception as e:
            LOGGER.debug(f"Error fetching any PREBUILT parser for {log_type}: {e}")
        return None

    def _get_active_content(self, log_type: str,
                            is_extension: bool) -> str | None:
        """Fetches the content of an active parser or extension."""
        if is_extension:
            extensions = self.client.list_parser_extensions(log_type)
            if not "parserExtensions" in extensions:
                return None
            for ext in extensions["parserExtensions"]:
                if ext.get(
                        "state"
                ) == ParserExtensionState.LIVE.value and "cbnSnippet" in ext:
                    return base64.b64decode(ext["cbnSnippet"]).decode('utf-8')
        else:
            parsers = self.client.list_parsers(log_type)
            for parser in parsers:
                if (parser.get("type") == PARSER_TYPE_CUSTOM
                        and parser.get("state") == ParserState.ACTIVE.value
                        and "cbn" in parser):
                    return base64.b64decode(parser["cbn"]).decode('utf-8')
        return None

    def plan_deployment(self) -> dict:
        """Compares local files to Chronicle and plans operations."""
        all_configs = self.discover_local_configs()
        plan = {}

        for config in all_configs:
            op_details = {
                "config": config,
                "parser_operation": Operation.NONE,
                "parser_ext_operation": Operation.NONE,
                "validation_failed": False
            }

            # Plan parser operation (skip for PREBUILT parsers)
            if config.parser and config.parser_type == PARSER_TYPE_CUSTOM:
                active_parser = self._get_active_content(config.log_type,
                                                         is_extension=False)
                if not active_parser:
                    op_details["parser_operation"] = Operation.CREATE
                elif active_parser.strip() != config.parser.strip():
                    op_details["parser_operation"] = Operation.UPDATE

            # Plan parser extension operation
            if config.parser_ext:
                active_ext = self._get_active_content(config.log_type,
                                                      is_extension=True)
                if not active_ext:
                    op_details["parser_ext_operation"] = Operation.CREATE
                elif active_ext.strip() != config.parser_ext.strip():
                    op_details["parser_ext_operation"] = Operation.UPDATE

            # Log the planned operations
            if op_details["parser_operation"] != Operation.NONE or op_details["parser_ext_operation"] != Operation.NONE:
                LOGGER.info(f"[{config.log_type}] Planned operations:")
                if config.parser_type == PARSER_TYPE_PREBUILT:
                    LOGGER.info(f"  - Parser: PREBUILT (read-only, no operations)")
                elif op_details["parser_operation"] != Operation.NONE:
                    LOGGER.info(f"  - Parser: {op_details['parser_operation'].value} CUSTOM parser")
                if op_details["parser_ext_operation"] != Operation.NONE:
                    parser_context = "PREBUILT parser" if config.parser_type == PARSER_TYPE_PREBUILT else "CUSTOM parser"
                    LOGGER.info(f"  - Extension: {op_details['parser_ext_operation'].value} extension to {parser_context}")

            # Validate if any change is planned
            if (op_details["parser_operation"] != Operation.NONE
                    or op_details["parser_ext_operation"] != Operation.NONE):
                try:
                    self._validate_parser_events(config)
                    LOGGER.info(
                        f"[{config.log_type}] Event validation passed.")
                except ValidationError as e:
                    LOGGER.error(f"[{config.log_type}] {e}")
                    op_details["validation_failed"] = True
                    # Reset operations to NONE if validation fails
                    op_details["parser_operation"] = Operation.NONE
                    op_details["parser_ext_operation"] = Operation.NONE

            plan[config.log_type] = op_details
        return plan

    def execute_deployment(self, plan: dict) -> list:
        """Submits parsers and extensions to Chronicle based on the plan."""
        submitted_info = []
        for log_type, details in plan.items():
            if details["validation_failed"]:
                continue

            info = {"log_type": log_type}
            parser_type = details["config"].parser_type

            # Submit parser (only for CUSTOM parsers)
            if details["parser_operation"] in [
                    Operation.CREATE, Operation.UPDATE
            ]:
                action_verb = "Creating" if details["parser_operation"] == Operation.CREATE else "Updating"
                LOGGER.info(f"[{log_type}] {action_verb} CUSTOM parser...")
                meta = self.client.create_parser(log_type,
                                                 details["config"].parser,
                                                 validated_on_empty_logs=True)
                name = meta.get("name")
                if not name:
                    raise ParserError(
                        f"[{log_type}] create_parser API did not return a name."
                    )
                info["parser_id"] = name.split("/")[-1]
                info["parser_name"] = name

            # Submit parser extension
            if details["parser_ext_operation"] in [
                    Operation.CREATE, Operation.UPDATE
            ]:
                action_verb = "Attaching" if details["parser_ext_operation"] == Operation.CREATE else "Updating"
                parser_context = "PREBUILT parser" if parser_type == PARSER_TYPE_PREBUILT else "CUSTOM parser"
                LOGGER.info(f"[{log_type}] {action_verb} extension to {parser_context}...")
                meta = self.client.create_parser_extension(
                    log_type, parser_config=details["config"].parser_ext)
                name = meta.get("name")
                if not name:
                    raise ParserError(
                        f"[{log_type}] create_parser_extension API did not return a name."
                    )
                info["parser_ext_id"] = name.split("/")[-1]
                info["parser_ext_name"] = name

            if "parser_id" in info or "parser_ext_id" in info:
                submitted_info.append(info)
        return submitted_info

    def verify_submissions(self, submitted_info: list, plan: dict):
        """Checks the validation status of submitted artifacts."""
        for info in submitted_info:
            log_type = info["log_type"]
            if "parser_id" in info:
                parser = self.client.get_parser(log_type, info["parser_id"])
                status = parser.get("validationStage", "UNKNOWN")
                plan[log_type]["parser_validation_status"] = status
                LOGGER.info(f"[{log_type}] Parser validation status: {status}")

            if "parser_ext_id" in info:
                ext = self.client.get_parser_extension(log_type,
                                                       info["parser_ext_id"])
                status = ext.get("state", "UNKNOWN")
                plan[log_type]["parser_ext_validation_status"] = status
                LOGGER.info(
                    f"[{log_type}] Parser Extension validation status: {status}"
                )
        return plan

    def activate_all_passed(self):
        """Finds and activates all parsers/extensions that are ready for release."""
        configs = self.discover_local_configs()
        activated_count = 0
        for config in configs:
            # Activate Parser (only for CUSTOM parsers, not PREBUILT)
            if config.parser_type == PARSER_TYPE_CUSTOM and config.parser:
                parsers = self.client.list_parsers(config.log_type)
                for p in parsers:
                    if (p.get("type") == PARSER_TYPE_CUSTOM
                            and p.get("state") != ParserState.ACTIVE.value
                            and p.get("validationStage")
                            == ParserValidationStatus.PASSED.value):

                        p_content = base64.b64decode(p["cbn"]).decode('utf-8')
                        if p_content.strip() == config.parser.strip():
                            parser_id = p["name"].split("/")[-1]
                            self.client.activate_parser(config.log_type, parser_id)
                            activated_count += 1
                            LOGGER.info(f"[{config.log_type}] Activated CUSTOM parser.")
                        else:
                            LOGGER.warning(
                                f"[{config.log_type}] Passed parser content mismatch. Skipping activation."
                            )
                        break  # Assume only one valid release candidate

            # Activate Parser Extension
            if config.parser_ext:
                exts_response = self.client.list_parser_extensions(config.log_type)
                if "parserExtensions" in exts_response:
                    for ext in exts_response["parserExtensions"]:
                        if (ext.get("state") ==
                                ParserExtensionState.VALIDATED.value):
                            ext_content = base64.b64decode(
                                ext["cbnSnippet"]).decode('utf-8')
                            if ext_content.strip() == config.parser_ext.strip():
                                ext_id = ext["name"].split("/")[-1]
                                self.client.activate_parser_extension(
                                    config.log_type, ext_id)
                                activated_count += 1
                                parser_type_info = f"({config.parser_type} parser)"
                                LOGGER.info(f"[{config.log_type}] Activated parser extension {parser_type_info}.")
                            else:
                                LOGGER.warning(
                                    f"[{config.log_type}] Validated extension content mismatch. Skipping."
                                )
                            break  # Assume only one valid release candidate
        return activated_count

    def generate_events(self, target_log_type: str = None):
        """Generates UDM event YAML files from raw log files."""
        configs = self.discover_local_configs()
        if target_log_type:
            configs = [c for c in configs if c.log_type == target_log_type]
            if not configs:
                raise ParserError(
                    f"No parser found for log type '{target_log_type}'")

        for config in configs:
            logs_path = os.path.join(config.dir_path, LOGS_FOLDER_NAME)
            events_path = os.path.join(config.dir_path, EVENTS_FOLDER_NAME)
            if not os.path.isdir(logs_path):
                LOGGER.warning(
                    f"[{config.log_type}] No '{LOGS_FOLDER_NAME}' folder, skipping event generation."
                )
                continue

            # For PREBUILT parsers, ensure we have the parser content
            parser_code = config.parser
            if config.parser_type == PARSER_TYPE_PREBUILT and not parser_code:
                LOGGER.info(f"[{config.log_type}] Fetching PREBUILT parser for event generation...")
                parser_code = self._get_any_prebuilt_parser(config.log_type)
                if not parser_code:
                    LOGGER.error(
                        f"[{config.log_type}] Cannot generate events: No PREBUILT parser found in SecOps."
                    )
                    continue

            os.makedirs(events_path, exist_ok=True)
            for log_filename in sorted(os.listdir(logs_path)):
                log_filepath = os.path.join(logs_path, log_filename)
                if not os.path.isfile(log_filepath): continue

                with open(log_filepath, "r", encoding='utf-8') as lf:
                    raw_logs = [line.strip() for line in lf if line.strip()]

                response = self.client.run_parser(
                    log_type=config.log_type,
                    parser_code=parser_code,
                    parser_extension_code=config.parser_ext,
                    logs=raw_logs)
                events = [
                    res.get("parsedEvents", [])
                    for res in response.get("runParserResults", [])
                ]

                event_filename = os.path.splitext(log_filename)[0] + ".yaml"
                event_filepath = os.path.join(events_path, event_filename)
                with open(event_filepath, "w", encoding='utf-8') as ef:
                    yaml.dump(process_data_for_dump(events),
                              ef,
                              sort_keys=True)
                LOGGER.info(
                    f"[{config.log_type}] Generated event file: {event_filename}"
                )

    def _validate_parser_events(self, config: LogTypeConfig):
        """Validates that a local parser generates expected events."""
        logs_subfolder = os.path.join(config.dir_path, LOGS_FOLDER_NAME)
        events_subfolder = os.path.join(config.dir_path, EVENTS_FOLDER_NAME)

        if not os.path.isdir(logs_subfolder):
            raise ValidationError(
                f"Missing '{LOGS_FOLDER_NAME}/' folder. Cannot validate.")
        if not os.path.isdir(events_subfolder):
            raise ValidationError(
                f"Missing '{EVENTS_FOLDER_NAME}/' folder. Cannot compare events."
            )

        # Aggregate logs and expected events
        all_raw_logs, all_expected_events = [], []
        for log_filename in sorted(os.listdir(logs_subfolder)):
            with open(os.path.join(logs_subfolder, log_filename),
                      "r",
                      encoding='utf-8') as lf:
                all_raw_logs.extend(
                    [line.strip() for line in lf if line.strip()])

        for event_filename in sorted(os.listdir(events_subfolder)):
            if event_filename.endswith(".yaml"):
                with open(os.path.join(events_subfolder, event_filename),
                          "r",
                          encoding='utf-8') as ef:
                    loaded = yaml.safe_load(ef)
                    if isinstance(loaded, list):
                        all_expected_events.extend(loaded)

        if not all_raw_logs:
            return  # Nothing to validate

        # For PREBUILT parsers, ensure we have the parser content
        parser_code = config.parser
        if config.parser_type == PARSER_TYPE_PREBUILT and not parser_code:
            parser_code = self._get_any_prebuilt_parser(config.log_type)
            if not parser_code:
                raise ValidationError(
                    f"Cannot validate: No PREBUILT parser found in SecOps for '{config.log_type}'."
                )

        # Run parser and get generated events
        response = self.client.run_parser(
            config.log_type,
            logs=all_raw_logs,
            parser_code=parser_code,
            parser_extension_code=config.parser_ext)
        generated_events = [
            res.get("parsedEvents", [])
            for res in response.get("runParserResults", [])
        ]

        # Compare events in temporary files
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".yaml") as f_new, \
                tempfile.NamedTemporaryFile("w+", delete=False, suffix=".yaml") as f_exp:
            temp_new_path = f_new.name
            temp_exp_path = f_exp.name
            yaml.dump(process_data_for_dump(generated_events),
                      f_new,
                      sort_keys=True)
            yaml.dump(process_data_for_dump(all_expected_events),
                      f_exp,
                      sort_keys=True)

        try:
            diffs = compare_yaml_files(temp_exp_path, temp_new_path,
                                       ["timestamp", "Timestamp", "etag"])
            if diffs:
                diff_str = "\n".join(diffs)
                raise ValidationError(
                    f"Differences found between generated and expected events:\n{diff_str}"
                )
        finally:
            os.remove(temp_new_path)
            os.remove(temp_exp_path)

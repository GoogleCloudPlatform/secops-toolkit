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

import base64
import logging
import os
import tempfile
import yaml
from typing import List
from secops import SecOpsClient
from secops.auth import RetryConfig
from config import SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION
from models import (LogTypeConfig, Operation, ParserState,
                    ParserExtensionState, ParserValidationStatus,
                    ValidationError, ParserError, APIError, ParserType,
                    ParserDeploymentPlan)
from config import (PARSERS_ROOT_DIR, PARSER_CONFIG_FILENAME,
                    PARSER_EXT_CONFIG_FILENAME, LOGS_FOLDER_NAME,
                    EVENTS_FOLDER_NAME, PARSER_YAML_FILENAME)
from utils import compare_yaml_files, process_data_for_dump, generate_event_files

LOGGER = logging.getLogger(__name__)


class ParserManager:
    """Manages the lifecycle of SecOps parsers and extensions."""

    def __init__(self):
        if not all([SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION]):
            raise APIError(
                "Missing SecOps env vars: SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION."
            )
        try:
            retry_config = RetryConfig(
                total=10,
                retry_status_codes=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "POST", "PATCH", "DELETE"],
                backoff_factor=0.5,
            )
            self.client = SecOpsClient(retry_config=retry_config).chronicle(
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

            parser_yaml_path = os.path.join(parser_dir_path,
                                            PARSER_YAML_FILENAME)
            parser_conf_filename = PARSER_CONFIG_FILENAME
            parser_ext_conf_filename = PARSER_EXT_CONFIG_FILENAME

            if os.path.isfile(parser_yaml_path):
                try:
                    with open(parser_yaml_path, 'r', encoding='utf-8') as f:
                        yaml_content = yaml.safe_load(f)
                        config.parser_config_dict = yaml_content

                        if yaml_content.get(
                                "parser",
                            {}).get("type") == ParserType.PREBUILT.value:
                            config.parser_type = ParserType.PREBUILT
                        else:
                            config.parser_type = ParserType.CUSTOM

                        # Override filenames if specified in YAML
                        if "parser" in yaml_content and "cbn" in yaml_content[
                                "parser"]:
                            parser_conf_filename = yaml_content["parser"][
                                "cbn"]

                        if "parser_extension" in yaml_content and "cbn_snippet" in yaml_content[
                                "parser_extension"]:
                            parser_ext_conf_filename = yaml_content[
                                "parser_extension"]["cbn_snippet"]

                except yaml.YAMLError as e:
                    LOGGER.warning(
                        f"[{item}] Failed to parse {PARSER_YAML_FILENAME}: {e}. Falling back to defaults."
                    )

            parser_conf_path = os.path.join(parser_dir_path,
                                            parser_conf_filename)
            if os.path.isfile(parser_conf_path):
                with open(parser_conf_path, 'r', encoding='utf-8') as f:
                    config.parser = f.read()

            parser_ext_conf_path = os.path.join(parser_dir_path,
                                                parser_ext_conf_filename)
            if os.path.isfile(parser_ext_conf_path):
                with open(parser_ext_conf_path, 'r', encoding='utf-8') as f:
                    config.parser_ext = f.read()

            if config.parser or config.parser_ext:
                log_type_configs.append(config)

        return log_type_configs

    def _get_active_content(
            self,
            log_type: str,
            is_extension: bool,
            parser_type: ParserType = ParserType.CUSTOM) -> str | None:
        """Fetches the content of an active parser or extension."""
        try:
            if is_extension:
                extensions = self.client.list_parser_extensions(log_type)
                if not "parserExtensions" in extensions:
                    return None
                for ext in extensions["parserExtensions"]:
                    if ext.get(
                            "state"
                    ) == ParserExtensionState.LIVE.value and "cbnSnippet" in ext:
                        return base64.b64decode(
                            ext["cbnSnippet"]).decode('utf-8')
            else:
                parsers = self.client.list_parsers(log_type)
                for parser in parsers:
                    if parser.get(
                            "state"
                    ) == ParserState.ACTIVE.value and "cbn" in parser:
                        if parser_type == ParserType.CUSTOM and parser.get(
                                "type") == ParserType.CUSTOM.value:
                            return base64.b64decode(
                                parser["cbn"]).decode('utf-8')
                        elif parser_type == ParserType.PREBUILT and parser.get(
                                "type") != ParserType.CUSTOM.value:
                            return base64.b64decode(
                                parser["cbn"]).decode('utf-8')

        except APIError as e:
            if e.response and e.response.status_code == 404:
                return None
            raise
        return None

    def plan_deployment(self) -> dict[str, ParserDeploymentPlan]:
        """Compares local files to SecOps and plans operations."""
        all_configs = self.discover_local_configs()
        plan = {}

        for config in all_configs:
            plan_op = ParserDeploymentPlan(config=config)

            # Initialize comparison variables
            active_parser = None
            active_ext = None

            # Plan parser operation
            if config.parser:
                active_parser = self._get_active_content(
                    config.log_type,
                    is_extension=False,
                    parser_type=config.parser_type)

                if config.parser_type == ParserType.PREBUILT:
                    if not active_parser or active_parser.strip(
                    ) != config.parser.strip():
                        try:
                            parsers = self.client.list_parsers(config.log_type)
                            found_rc = False
                            for p in parsers:
                                if (p.get("type") == ParserType.PREBUILT.value
                                        and p.get("state")
                                        != ParserState.ACTIVE.value
                                        and p.get("releaseStage") ==
                                        ParserState.RELEASE_CANDIDATE.value):

                                    rc_content = base64.b64decode(
                                        p.get("cbn", "")).decode('utf-8')
                                    if rc_content.strip(
                                    ) == config.parser.strip():
                                        LOGGER.info(
                                            f"[{config.log_type}] Local code matches pending Release Candidate {p.get('name')}. Operation: RELEASE."
                                        )
                                        plan_op.parser_operation = Operation.RELEASE
                                        found_rc = True
                                        break

                            if not found_rc:
                                LOGGER.warning(
                                    f"[{config.log_type}] Local code differs from active parser and no matching Release Candidate found. Validation only (UPDATE)."
                                )
                                plan_op.parser_operation = Operation.UPDATE
                        except Exception as e:
                            LOGGER.warning(
                                f"[{config.log_type}] Failed to check release candidates: {e}. Defaulting to UPDATE."
                            )
                            plan_op.parser_operation = Operation.UPDATE
                    else:
                        plan_op.parser_operation = Operation.NONE

                else:
                    if not active_parser:
                        plan_op.parser_operation = Operation.CREATE
                    elif active_parser.strip() != config.parser.strip():
                        plan_op.parser_operation = Operation.UPDATE

            # Plan parser extension operation
            if config.parser_ext:
                active_ext = self._get_active_content(config.log_type,
                                                      is_extension=True)
                if not active_ext:
                    plan_op.parser_ext_operation = Operation.CREATE
                elif active_ext.strip() != config.parser_ext.strip():
                    plan_op.parser_ext_operation = Operation.UPDATE

            if (plan_op.parser_operation != Operation.NONE
                    or plan_op.parser_ext_operation != Operation.NONE):
                try:
                    self._validate_parser_events(config)
                    LOGGER.info(
                        f"[{config.log_type}] Event validation passed.")
                except ValidationError as e:
                    LOGGER.error(f"[{config.log_type}] {e}")
                    plan_op.validation_failed = True
                    plan_op.parser_operation = Operation.NONE
                    plan_op.parser_ext_operation = Operation.NONE

            needs_comparison = (plan_op.parser_operation
                                in [Operation.UPDATE, Operation.RELEASE]
                                or plan_op.parser_ext_operation
                                in [Operation.CREATE, Operation.UPDATE])

            if needs_comparison:
                try:
                    from compare import ParserComparator
                    comparator = ParserComparator(config.log_type,
                                                  client=self.client)

                    LOGGER.info(
                        f"[{config.log_type}] Generating UDM comparison report..."
                    )
                    report = comparator.compare_content(
                        old_parser=active_parser,
                        old_ext=active_ext,
                        new_parser=config.parser,
                        new_ext=config.parser_ext)
                    plan_op.comparison_report = report
                except Exception as e:
                    LOGGER.error(
                        f"[{config.log_type}] Failed to generate comparison report: {e}"
                    )
                    plan_op.comparison_report = f"Failed to generate comparison report: {e}"

            plan[config.log_type] = plan_op
        return plan

    def execute_deployment(self, plan: dict[str,
                                            ParserDeploymentPlan]) -> list:
        """Submits parsers and extensions to SecOps based on the plan."""
        submitted_info = []
        for log_type, details in plan.items():
            if details.validation_failed:
                continue

            info = {"log_type": log_type}
            # Submit parser
            if details.parser_operation in [
                    Operation.CREATE, Operation.UPDATE, Operation.RELEASE
            ]:
                if details.config.parser_type == ParserType.PREBUILT:
                    LOGGER.info(
                        f"[{log_type}] PREBUILT parser detected. Skipping submission."
                    )
                    if details.parser_operation == Operation.RELEASE:
                        LOGGER.info(
                            f"[{log_type}] Ready for release (activation).")
                    pass
                else:
                    LOGGER.info(f"[{log_type}] Submitting parser...")
                    meta = self.client.create_parser(
                        log_type,
                        details.config.parser,
                        validated_on_empty_logs=True)
                    name = meta.get("name")
                    if not name:
                        raise ParserError(
                            f"[{log_type}] create_parser API did not return a name."
                        )
                    info["parser_id"] = name.split("/")[-1]
                    info["parser_name"] = name

            # Submit parser extension
            if details.parser_ext_operation in [
                    Operation.CREATE, Operation.UPDATE
            ]:
                LOGGER.info(f"[{log_type}] Submitting parser extension...")
                meta = self.client.create_parser_extension(
                    log_type, parser_config=details.config.parser_ext)
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

    def verify_submissions(self, submitted_info: list,
                           plan: dict[str, ParserDeploymentPlan]):
        """Checks the validation status of submitted artifacts."""
        for info in submitted_info:
            log_type = info["log_type"]
            if "parser_id" in info:
                parser = self.client.get_parser(log_type, info["parser_id"])
                status = parser.get("validationStage", "UNKNOWN")
                plan[log_type].parser_validation_status = status
                LOGGER.info(f"[{log_type}] Parser validation status: {status}")

            if "parser_ext_id" in info:
                ext = self.client.get_parser_extension(log_type,
                                                       info["parser_ext_id"])
                status = ext.get("state", "UNKNOWN")
                plan[log_type].parser_ext_validation_status = status
                LOGGER.info(
                    f"[{log_type}] Parser Extension validation status: {status}"
                )
        return plan

    def activate_all_passed(self):
        """Finds and activates all parsers/extensions that are ready for release."""
        configs = self.discover_local_configs()
        activated_count = 0
        for config in configs:
            # Activate Parser
            if config.parser_type == ParserType.PREBUILT:
                try:
                    parsers = self.client.list_parsers(config.log_type)
                    for p in parsers:
                        if (p.get("type") == ParserType.PREBUILT.value
                                and p.get("state") != ParserState.ACTIVE.value
                                and p.get("releaseStage")
                                == ParserState.RELEASE_CANDIDATE.value):

                            rc_content = base64.b64decode(p.get(
                                "cbn", "")).decode('utf-8')
                            if rc_content.strip() == config.parser.strip():
                                rc_id = p.get("name").split("/")[-1]
                                LOGGER.info(
                                    f"[{config.log_type}] Found matching Release Candidate: {rc_id}. Activating..."
                                )
                                # Using activate_parser as it allows activating a specific parser ID (which this RC is)
                                self.client.activate_release_candidate_parser(
                                    config.log_type, rc_id)
                                activated_count += 1
                                break
                    else:
                        LOGGER.warning(
                            f"[{config.log_type}] No matching Release Candidate found for local content. Skipping activation."
                        )

                except Exception as e:
                    LOGGER.error(
                        f"[{config.log_type}] Failed to activate release candidate: {e}"
                    )

            else:
                # Handle CUSTOM parser activation
                parsers = self.client.list_parsers(config.log_type)
                for p in parsers:
                    if (p.get("type") == ParserType.CUSTOM.value
                            and p.get("state") != ParserState.ACTIVE.value
                            and p.get("validationStage")
                            == ParserValidationStatus.PASSED.value):

                        p_content = base64.b64decode(p["cbn"]).decode('utf-8')
                        if p_content.strip() == config.parser.strip():
                            parser_id = p["name"].split("/")[-1]
                            self.client.activate_parser(
                                config.log_type, parser_id)
                            activated_count += 1
                        else:
                            LOGGER.warning(
                                f"[{config.log_type}] Passed parser content mismatch. Skipping activation."
                            )
                        break  # Assume only one valid release candidate

            # Activate Parser Extension
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

            generate_event_files(client=self.client,
                                 log_type=config.log_type,
                                 parser_code=config.parser,
                                 parser_ext_code=config.parser_ext,
                                 logs_dir=logs_path,
                                 events_dir=events_path)

    def _validate_parser_events(self, config: LogTypeConfig):
        """
        Validates local parser events against generated events from the API.
        If differences are found, it updates the local event files with the
        results from the API.
        """
        logs_subfolder = os.path.join(config.dir_path, LOGS_FOLDER_NAME)
        events_subfolder = os.path.join(config.dir_path, EVENTS_FOLDER_NAME)

        if not os.path.isdir(logs_subfolder):
            LOGGER.warning(
                f"[{config.log_type}] Missing '{LOGS_FOLDER_NAME}/' folder. Skipping event validation."
            )
            return

        log_files = [
            f for f in sorted(os.listdir(logs_subfolder))
            if os.path.isfile(os.path.join(logs_subfolder, f))
        ]
        if not log_files:
            LOGGER.warning(
                f"[{config.log_type}] No log files found in '{LOGS_FOLDER_NAME}/'. Skipping event validation."
            )
            return

        if not os.path.isdir(events_subfolder):
            os.makedirs(events_subfolder, exist_ok=True)
            LOGGER.info(
                f"[{config.log_type}] Created missing '{EVENTS_FOLDER_NAME}/' folder."
            )

        for log_filename in log_files:
            log_filepath = os.path.join(logs_subfolder, log_filename)
            if not os.path.isfile(log_filepath):
                continue

            event_filename = os.path.splitext(log_filename)[0] + ".yaml"
            event_filepath = os.path.join(events_subfolder, event_filename)

            with open(log_filepath, "r", encoding='utf-8') as lf:
                raw_logs = [line.strip() for line in lf if line.strip()]

            if not raw_logs:
                continue

            response = self.client.run_parser(
                log_type=config.log_type,
                parser_code=config.parser,
                parser_extension_code=config.parser_ext,
                logs=raw_logs)
            generated_events = [
                res.get("parsedEvents", [])
                for res in response.get("runParserResults", [])
            ]
            processed_generated_events = process_data_for_dump(
                generated_events)

            local_events = []
            if os.path.exists(event_filepath):
                with open(event_filepath, "r", encoding='utf-8') as ef:
                    try:
                        loaded = yaml.safe_load(ef)
                        if isinstance(loaded, list):
                            local_events = loaded
                    except yaml.YAMLError:
                        LOGGER.warning(
                            f"Could not parse YAML from {event_filepath}. It will be overwritten."
                        )

            # Using temporary files for comparison to handle complex objects and ordering
            with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".yaml") as f_new, \
                    tempfile.NamedTemporaryFile("w+", delete=False, suffix=".yaml") as f_exp:
                temp_new_path = f_new.name
                temp_exp_path = f_exp.name
                yaml.dump(processed_generated_events, f_new, sort_keys=True)
                yaml.dump(process_data_for_dump(local_events),
                          f_exp,
                          sort_keys=True)

            try:
                diffs = compare_yaml_files(temp_exp_path, temp_new_path,
                                           ["timestamp", "Timestamp", "etag"])
                if diffs:
                    LOGGER.warning(
                        f"[{config.log_type}] Differences found for {log_filename}. Updating local events file: {event_filepath}"
                    )
                    with open(event_filepath, "w", encoding='utf-8') as ef:
                        yaml.dump(processed_generated_events,
                                  ef,
                                  sort_keys=True)
            finally:
                os.remove(temp_new_path)
                os.remove(temp_exp_path)

    def pull_all_parsers(self):
        """Discovers all log types with active parsers and pulls them."""
        LOGGER.info("Discovering all parsers in the tenant...")
        try:
            # List all parsers with pagination
            all_parsers = []
            response = self.client.list_parsers(log_type='-',
                                                page_size=1000,
                                                page_token=None)
            all_parsers.extend(response["parsers"])

            log_types = set()
            for p in all_parsers:
                parts = p.get("name", "").split("/")
                if "logTypes" in parts:
                    idx = parts.index("logTypes")
                    if idx + 1 < len(parts):
                        log_types.add(parts[idx + 1])

            LOGGER.info(
                f"Found {len(log_types)} log types with parsers. Starting pull..."
            )

            for lt in sorted(log_types):
                try:
                    self.pull_parser(lt)
                except Exception as e:
                    LOGGER.error(f"[{lt}] Failed to pull parser: {e}")

        except Exception as e:
            raise ParserError(f"Failed to list all parsers: {e}")

    def pull_parser(self, log_type: str):
        """Pulls the active parser and extension from SecOps and updates local files."""
        LOGGER.info(
            f"[{log_type}] Pulling active parser configuration from SecOps...")

        try:
            # We don't know the type yet, so we try to get whatever is active.
            # _get_active_content default is CUSTOM.
            # Let's try CUSTOM first.
            active_parser = self._get_active_content(
                log_type, is_extension=False, parser_type=ParserType.CUSTOM)
            parser_type = ParserType.CUSTOM

            if not active_parser:
                # Try PREBUILT
                active_parser = self._get_active_content(
                    log_type,
                    is_extension=False,
                    parser_type=ParserType.PREBUILT)
                if active_parser:
                    parser_type = ParserType.PREBUILT

            active_ext = self._get_active_content(log_type, is_extension=True)
        except APIError as e:
            if "NOT_FOUND" in str(e):
                # If log type not found, we still might want to create the folder if asking explicitly?
                # But here we return None.
                return None
            raise  # Re-raise other API errors

        if not active_parser and not active_ext:
            LOGGER.info(f"[{log_type}] No active parser or extension found.")
            return None

        parser_dir_path = os.path.join(PARSERS_ROOT_DIR, log_type)
        is_update = os.path.isdir(parser_dir_path)

        os.makedirs(parser_dir_path, exist_ok=True)

        # Write parser.yaml
        parser_yaml_path = os.path.join(parser_dir_path, PARSER_YAML_FILENAME)

        # Default content
        yaml_content = {
            "log_type": log_type,
            "parser": {
                "type": parser_type.value,
                "cbn": PARSER_CONFIG_FILENAME
            },
            "parser_extension": {}
        }

        if active_ext:
            yaml_content["parser_extension"][
                "cbn_snippet"] = PARSER_EXT_CONFIG_FILENAME

        # Preserve existing YAML filenames if possible
        if os.path.isfile(parser_yaml_path):
            try:
                with open(parser_yaml_path, 'r', encoding='utf-8') as f:
                    existing_yaml = yaml.safe_load(f)
                    if existing_yaml:
                        # Update type but keep filenames if present
                        if "parser" not in existing_yaml:
                            existing_yaml["parser"] = {}
                        existing_yaml["parser"]["type"] = parser_type.value

                        # Preserve filenames if they exist in valid yaml
                        if "cbn" in existing_yaml.get("parser", {}):
                            yaml_content["parser"]["cbn"] = existing_yaml[
                                "parser"]["cbn"]

                        # Only preserve extension filename if we have an active extension
                        if active_ext and "cbn_snippet" in existing_yaml.get(
                                "parser_extension", {}):
                            existing_name = existing_yaml["parser_extension"][
                                "cbn_snippet"]
                            if existing_name == "parser_ext.conf":
                                yaml_content["parser_extension"][
                                    "cbn_snippet"] = PARSER_EXT_CONFIG_FILENAME
                            else:
                                yaml_content["parser_extension"][
                                    "cbn_snippet"] = existing_name
            except Exception as e:
                LOGGER.warning(
                    f"[{log_type}] Failed to read existing {PARSER_YAML_FILENAME}, overwriting: {e}"
                )

        with open(parser_yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(yaml_content, f, sort_keys=False)
        LOGGER.info(f"[{log_type}] Updated '{PARSER_YAML_FILENAME}'.")

        parser_conf_filename = yaml_content.get("parser", {}).get(
            "cbn", PARSER_CONFIG_FILENAME)
        parser_conf_path = os.path.join(parser_dir_path, parser_conf_filename)

        if active_parser:
            with open(parser_conf_path, 'w', encoding='utf-8') as f:
                f.write(active_parser)
            LOGGER.info(
                f"[{log_type}] Wrote active parser to '{parser_conf_path}'.")
        elif parser_type == ParserType.PREBUILT:
            # If prebuilt but no active content returned (maybe system default?), we might not have CBN.
            # But _get_active_content only returns if it finds CBN.
            pass

        parser_ext_conf_filename = yaml_content.get(
            "parser_extension", {}).get("cbn_snippet",
                                        PARSER_EXT_CONFIG_FILENAME)
        parser_ext_conf_path = os.path.join(parser_dir_path,
                                            parser_ext_conf_filename)

        if active_ext:
            with open(parser_ext_conf_path, 'w', encoding='utf-8') as f:
                f.write(active_ext)
            LOGGER.info(
                f"[{log_type}] Wrote active parser extension to '{parser_ext_conf_path}'."
            )
        elif os.path.exists(parser_ext_conf_path):
            # If no active extension, remove the local file if it exists
            os.remove(parser_ext_conf_path)
            LOGGER.info(
                f"[{log_type}] Removed local parser extension as none is active in SecOps."
            )

        # Create logs and events folders if they don't exist
        os.makedirs(os.path.join(parser_dir_path, LOGS_FOLDER_NAME),
                    exist_ok=True)
        os.makedirs(os.path.join(parser_dir_path, EVENTS_FOLDER_NAME),
                    exist_ok=True)

        return is_update

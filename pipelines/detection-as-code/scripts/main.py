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
import sys
import click
import re
import ruamel.yaml
from secops import SecOpsClient
from config import (
    CUSTOMER_ID,
    REGION,
    PROJECT_ID,
    BASE_RULES_DIR,
    SECOPS_REFERENCE_LISTS_CONFIG_PATH,
)
from data_tables import DataTables

# --- Global Logger Setup ---
_LOGGER = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
_LOGGER.addHandler(handler)
_LOGGER.setLevel(logging.INFO)

ruamel_yaml = ruamel.yaml.YAML(typ="safe")


class AppContext:
    """Application context for the CLI."""

    def __init__(self):
        self.chronicle_client = None


pass_context = click.make_pass_decorator(AppContext, ensure=True)


@click.group()
@pass_context
def cli(ctx: AppContext):
    """A CLI tool for managing SecOps rules and data tables."""
    try:
        client = SecOpsClient()
        ctx.chronicle_client = client.chronicle(customer_id=CUSTOMER_ID,
                                                project_id=PROJECT_ID,
                                                region=REGION)
        _LOGGER.info("SecOpsClient for Chronicle initialized successfully.")
    except Exception as e:
        _LOGGER.error("Failed to initialize SecOpsClient for Chronicle: %s",
                      e,
                      exc_info=True)
        sys.exit(1)


@cli.command()
def init():
    """Check for required environment variables."""
    _LOGGER.info("Checking for required environment variables...")
    required_vars = [
        "SECOPS_CUSTOMER_ID", "SECOPS_PROJECT_ID", "SECOPS_REGION"
    ]
    missing_vars = [
        v for v in required_vars if not globals().get(v.split("_")[1]) in v
    ]
    if missing_vars:
        _LOGGER.error("Missing required environment variables: %s",
                      ", ".join(missing_vars))
        sys.exit(1)
    _LOGGER.info("All required environment variables are set.")


@cli.command()
@pass_context
def update_data_tables(ctx: AppContext):
    """Update SecOps Data Tables based on local Data Tables."""
    data_table_updates = DataTables.update_remote_data_tables(
        chronicle_client=ctx.chronicle_client)
    if not data_table_updates:
        _LOGGER.info("No data table updates to apply.")
        return

    _LOGGER.info("Summary of data table changes:")
    for update_type, names in data_table_updates.items():
        if names:
            _LOGGER.info("  %s: %s", update_type.capitalize(),
                         ", ".join(names))


@cli.command()
@pass_context
def verify_rules(ctx: AppContext):
    """Verify SecOps rules."""
    if not BASE_RULES_DIR.is_dir():
        _LOGGER.warning("Base rules directory '%s' not found.", BASE_RULES_DIR)
        return

    local_rules = {p.stem: p for p in BASE_RULES_DIR.rglob("*.yaral")}
    _LOGGER.info("Found %d local YARA-L rules to check.", len(local_rules))

    errors = []
    for name, path in local_rules.items():
        _LOGGER.info("Verifying rule: %s", name)
        try:
            rule_text = path.read_text()
            _validate_rule_file(name, rule_text)
            _validate_rule_with_chronicle(ctx.chronicle_client, name,
                                          rule_text)
        except (ValueError, IOError) as e:
            _LOGGER.error("Error processing rule %s: %s", name, e)
            errors.append(name)

    if errors:
        _LOGGER.error("Verification failed for rules: %s", ", ".join(errors))
        sys.exit(1)

    _LOGGER.info("All rules verified successfully.")


def _validate_rule_file(file_rule_name: str, rule_text: str):
    """Validate that the rule name in the file matches the file name."""
    match = re.search(r"rule\s+([a-zA-Z0_9_]+)\s+{", rule_text)
    if not match or match.group(1).casefold() != file_rule_name.casefold():
        raise ValueError("Rule name in file does not match file name.")


def _validate_rule_with_chronicle(chronicle, rule_name: str, rule_text: str):
    """Validate the rule text using the Chronicle client."""
    result = chronicle.validate_rule(rule_text=rule_text)
    if result.success:
        _LOGGER.info("Rule %s successfully verified.", rule_name)
        return

    if "reference list" in result.message:
        _handle_reference_list_error(rule_name, result.message)
    elif "Could not find Data Table" in result.message:
        _handle_data_table_error(rule_name, result.message)
    else:
        raise ValueError(f"Rule verification failed: {result.message}")


def _handle_reference_list_error(rule_name: str, error_message: str):
    """Handle reference list errors during rule validation."""
    match = re.search(r"for reference list\s+'(\S+)'", error_message)
    if not match:
        raise ValueError("Could not extract reference list name.")

    ref_list_name = match.group(1)
    with open(SECOPS_REFERENCE_LISTS_CONFIG_PATH, "r", encoding="utf-8") as f:
        ref_lists = ruamel_yaml.load(f).keys()

    if ref_list_name in ref_lists:
        _LOGGER.info(
            "Rule %s verified (reference list '%s' is local).",
            rule_name,
            ref_list_name,
        )
    else:
        raise ValueError(f"Reference list '{ref_list_name}' not found.")


def _handle_data_table_error(rule_name: str, error_message: str):
    """Handle data table errors during rule validation."""
    match = re.search(r"Data Table Name: (.*?)\n", error_message)
    if not match:
        raise ValueError("Could not extract data table name.")

    table_name = match.group(1)
    local_tables = DataTables.load_data_table_config().keys()

    if table_name in local_tables:
        _LOGGER.info("Rule %s verified (data table '%s' is local).", rule_name,
                     table_name)
    else:
        raise ValueError(f"Data table '{table_name}' not found.")


if __name__ == "__main__":
    cli()

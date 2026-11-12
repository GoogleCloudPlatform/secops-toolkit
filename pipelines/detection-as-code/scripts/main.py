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
import re
import sys
from typing import Any

import click
import config
import ruamel.yaml
from data_tables import DataTables
from secops import SecOpsClient
from secops.chronicle.models import APIVersion
from secops.chronicle.utils.request_utils import chronicle_request

# --- Global Logger Setup ---
_LOGGER = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
_LOGGER.addHandler(handler)
_LOGGER.setLevel(getattr(logging, config.LOGGING_LEVEL, logging.INFO))

ruamel_yaml = ruamel.yaml.YAML(typ="safe")

LEGACY_RUN_FREQUENCIES = frozenset({"LIVE", "HOURLY", "DAILY"})
CUSTOMIZABLE_RUN_FREQUENCIES = frozenset({"LIVE_CUSTOMIZABLE", "HOURLY_CUSTOMIZABLE"})
VALID_RUN_FREQUENCIES = LEGACY_RUN_FREQUENCIES | CUSTOMIZABLE_RUN_FREQUENCIES
ALLOWED_SCHEDULE_CUSTOMIZATION_KEYS = frozenset(
    {"ensure_enrichment_completeness", "late_arriving_data_adjustment"}
)
DURATION_PATTERN = re.compile(r"^\d+(\.\d{1,9})?s$")


class AppContext:
    """Application context for the CLI."""

    def __init__(self):
        self.chronicle_client = None

    def get_chronicle_client(self):
        """Lazily initialize and return the ChronicleClient."""
        if self.chronicle_client is not None:
            return self.chronicle_client

        missing = _get_missing_env_vars()
        if missing:
            _LOGGER.error(
                "Missing required environment variables: %s", ", ".join(missing)
            )
            sys.exit(1)

        try:
            client = SecOpsClient()
            self.chronicle_client = client.chronicle(
                customer_id=os.getenv("SECOPS_CUSTOMER_ID") or config.CUSTOMER_ID,
                project_id=os.getenv("SECOPS_PROJECT_ID") or config.PROJECT_ID,
                region=os.getenv("SECOPS_REGION") or config.REGION,
            )
            _LOGGER.info("SecOpsClient for Chronicle initialized successfully.")
            return self.chronicle_client
        except Exception:
            _LOGGER.exception("Failed to initialize SecOpsClient for Chronicle")
            sys.exit(1)


pass_context = click.make_pass_decorator(AppContext, ensure=True)


def _get_missing_env_vars() -> list[str]:
    """Return list of required SecOps environment variables that are unset."""
    env_mapping = {
        "SECOPS_CUSTOMER_ID": os.getenv("SECOPS_CUSTOMER_ID") or config.CUSTOMER_ID,
        "SECOPS_PROJECT_ID": os.getenv("SECOPS_PROJECT_ID") or config.PROJECT_ID,
        "SECOPS_REGION": os.getenv("SECOPS_REGION") or config.REGION,
    }
    return [name for name, val in env_mapping.items() if not val]


def _extract_rule_id_from_resource_name(resource_name: str) -> str:
    """Extract the rule ID (ru_...) from a Rule or RuleDeployment resource name."""
    if not resource_name:
        return ""
    trimmed = resource_name.removesuffix("/deployment")
    return trimmed.split("/")[-1]


def _schedule_customizations_to_yaml(
    api_customizations: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Convert API camelCase scheduleCustomizations into YAML snake_case."""
    if not isinstance(api_customizations, dict) or not api_customizations:
        return None

    converted: dict[str, Any] = {}
    if api_customizations.get("ensureEnrichmentCompleteness") is not None:
        converted["ensure_enrichment_completeness"] = bool(
            api_customizations["ensureEnrichmentCompleteness"]
        )
    if api_customizations.get("lateArrivingDataAdjustment"):
        converted["late_arriving_data_adjustment"] = str(
            api_customizations["lateArrivingDataAdjustment"]
        )

    return converted or None


@click.group()
@pass_context
def cli(ctx: AppContext):
    """A CLI tool for managing SecOps rules and data tables."""


@cli.command()
def init():
    """Check for required environment variables."""
    _LOGGER.info("Checking for required environment variables...")
    missing_vars = _get_missing_env_vars()
    if missing_vars:
        _LOGGER.error(
            "Missing required environment variables: %s", ", ".join(missing_vars)
        )
        sys.exit(1)
    _LOGGER.info("All required environment variables are set.")


@cli.command()
@pass_context
def update_data_tables(ctx: AppContext):
    """Update SecOps Data Tables based on local Data Tables."""
    chronicle_client = ctx.get_chronicle_client()
    data_table_updates = DataTables.update_remote_data_tables(
        chronicle_client=chronicle_client
    )
    if not data_table_updates:
        _LOGGER.info("No data table updates to apply.")
        return

    _LOGGER.info("Summary of data table changes:")
    for update_type, names in data_table_updates.items():
        if names:
            _LOGGER.info("  %s: %s", update_type.capitalize(), ", ".join(names))


@cli.command()
@pass_context
def pull_rules(ctx: AppContext):
    """Pull all rules from SecOps and populate local files."""
    chronicle_client = ctx.get_chronicle_client()
    customer_id = os.getenv("SECOPS_CUSTOMER_ID") or config.CUSTOMER_ID
    project_id = os.getenv("SECOPS_PROJECT_ID") or config.PROJECT_ID
    region = os.getenv("SECOPS_REGION") or config.REGION

    _LOGGER.info("Fetching rules from SecOps...")
    try:
        rules_data = chronicle_client.list_rules().get("rules", [])
        _LOGGER.info("Retrieved %d rules.", len(rules_data))

        deployments_data = chronicle_client.list_rule_deployments().get(
            "ruleDeployments", []
        )
        _LOGGER.info("Retrieved %d rule deployments.", len(deployments_data))

        # Build a mapping of ruleId -> deployment details
        deployments_map = {
            _extract_rule_id_from_resource_name(d.get("name", "")): d
            for d in deployments_data
            if d.get("name")
        }

        yaml = ruamel.yaml.YAML()
        yaml.preserve_quotes = True

        rules_config: dict[str, Any] = {}
        if config.SECOPS_RULES_CONFIG_PATH.is_file():
            with open(config.SECOPS_RULES_CONFIG_PATH, "r", encoding="utf-8") as f:
                rules_config = yaml.load(f) or {}

        config.BASE_RULES_DIR.mkdir(parents=True, exist_ok=True)

        import_commands = []

        for rule in rules_data:
            rule_id = _extract_rule_id_from_resource_name(rule.get("name", ""))
            rule_text = rule.get("text", "")

            # Extract rule name from text
            match = re.search(r"rule\s+([a-zA-Z0-9_]+)\s*\{", rule_text)
            if not match:
                _LOGGER.warning(
                    "Could not extract rule name for rule ID %s. Skipping.", rule_id
                )
                continue

            rule_name = match.group(1)

            # Save rule to file
            rule_file_path = config.BASE_RULES_DIR / f"{rule_name}.yaral"
            rule_file_path.write_text(rule_text, encoding="utf-8")

            # Update secops_rules_config
            dep = deployments_map.get(rule_id, {})
            if rule_name not in rules_config or not isinstance(
                rules_config[rule_name], dict
            ):
                rules_config[rule_name] = {}

            entry = rules_config[rule_name]
            entry["enabled"] = dep.get("enabled", False)
            entry["alerting"] = dep.get("alerting", False)
            entry["archived"] = dep.get("archived", False)

            run_freq = dep.get("runFrequency")
            if run_freq:
                entry["run_frequency"] = run_freq
            else:
                entry.pop("run_frequency", None)

            yaml_customizations = _schedule_customizations_to_yaml(
                dep.get("scheduleCustomizations")
            )
            if yaml_customizations:
                entry["schedule_customizations"] = yaml_customizations
            else:
                entry.pop("schedule_customizations", None)

            scope_resource = rule.get("scope")
            if scope_resource:
                entry["scope"] = scope_resource.split("/")[-1]
            else:
                entry.pop("scope", None)

            exec_state = dep.get("executionState")
            if exec_state in {"LIMITED", "PAUSED"}:
                _LOGGER.warning(
                    "Rule '%s' (%s) is currently in executionState=%s.",
                    rule_name,
                    rule_id,
                    exec_state,
                )

            # Generate terraform import commands
            tf_parent = f"projects/{project_id}/locations/{region}/instances/{customer_id}/rules/{rule_id}"
            import_commands.append(
                f"terraform import 'google_chronicle_rule.rule[\"{rule_name}\"]' {tf_parent}"
            )
            import_commands.append(
                f"terraform import 'google_chronicle_rule_deployment.rule_deployment[\"{rule_name}\"]' {tf_parent}/deployment"
            )

        with open(config.SECOPS_RULES_CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(rules_config, f)

        _LOGGER.info(
            "Successfully pulled rules and updated %s.",
            config.SECOPS_RULES_CONFIG_PATH.name,
        )

        if import_commands:
            click.echo("\n--- Terraform Import Commands ---")
            for cmd in import_commands:
                click.echo(cmd)

    except Exception:
        _LOGGER.exception("Failed to pull rules")
        sys.exit(1)


@cli.command()
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Treat deprecated/coerced run_frequency warnings and unconfigured rules as errors.",
)
@click.option(
    "--offline",
    is_flag=True,
    default=False,
    help="Run local rule and YAML deployment validations without calling the SecOps API.",
)
@pass_context
def verify_rules(ctx: AppContext, strict: bool, offline: bool):
    """Verify SecOps rules and deployment configurations."""
    if not config.BASE_RULES_DIR.is_dir():
        _LOGGER.warning("Base rules directory '%s' not found.", config.BASE_RULES_DIR)
        return

    chronicle_client = None if offline else ctx.get_chronicle_client()

    local_rules = {p.stem: p for p in sorted(config.BASE_RULES_DIR.rglob("*.yaral"))}
    _LOGGER.info("Found %d local YARA-L rules to check.", len(local_rules))

    rules_config: dict[str, Any] = {}
    if config.SECOPS_RULES_CONFIG_PATH.is_file():
        with open(config.SECOPS_RULES_CONFIG_PATH, "r", encoding="utf-8") as f:
            rules_config = ruamel_yaml.load(f) or {}

    errors: list[str] = []

    # 1. Check rules defined in secops_rules.yaml that lack a .yaral file
    for cfg_rule_name, rule_cfg in rules_config.items():
        if cfg_rule_name not in local_rules:
            _LOGGER.error(
                "Rule '%s' is configured in %s, but '%s.yaral' was not found in %s.",
                cfg_rule_name,
                config.SECOPS_RULES_CONFIG_PATH.name,
                cfg_rule_name,
                config.BASE_RULES_DIR,
            )
            errors.append(cfg_rule_name)
            continue

        try:
            effective_cfg = {} if rule_cfg is None else rule_cfg
            _validate_rule_deployment_config(
                cfg_rule_name, effective_cfg, strict=strict
            )
        except (ValueError, TypeError) as e:
            _LOGGER.error("Invalid deployment config for rule %s: %s", cfg_rule_name, e)
            errors.append(cfg_rule_name)

    # 2. Validate each .yaral rule locally and (unless --offline) remotely
    for name, path in local_rules.items():
        _LOGGER.info("Verifying rule: %s", name)
        if rules_config and name not in rules_config:
            msg = (
                f"Rule '{name}.yaral' is not present in "
                f"{config.SECOPS_RULES_CONFIG_PATH.name} and will not be deployed by Terraform."
            )
            if strict:
                _LOGGER.error(msg)
                errors.append(name)
                continue
            _LOGGER.warning(msg)

        try:
            rule_text = path.read_text(encoding="utf-8")
            _validate_rule_file(name, rule_text)
            if not offline:
                raw_cfg = rules_config.get(name)
                rule_cfg = raw_cfg if isinstance(raw_cfg, dict) else {}
                _validate_rule_with_chronicle(
                    chronicle_client,
                    name,
                    rule_text,
                    rule_cfg=rule_cfg,
                    strict=strict,
                )
        except (OSError, ValueError, TypeError) as e:
            _LOGGER.error("Error processing rule %s: %s", name, e)
            if name not in errors:
                errors.append(name)

    if errors:
        _LOGGER.error("Verification failed for rules: %s", ", ".join(errors))
        sys.exit(1)

    _LOGGER.info("All rules verified successfully.")


def _validate_rule_deployment_config(
    rule_name: str, rule_cfg: dict[str, Any], *, strict: bool = False
):
    """Validate deployment and schedule customization settings from secops_rules.yaml."""
    if not isinstance(rule_cfg, dict):
        raise TypeError("Rule deployment configuration must be a YAML mapping.")

    enabled = rule_cfg.get("enabled", True)
    archived = rule_cfg.get("archived", False)
    if archived and enabled:
        raise ValueError(
            "Rules with 'archived: true' must explicitly set 'enabled: false'."
        )

    run_frequency = rule_cfg.get("run_frequency")
    if run_frequency is not None:
        if run_frequency not in VALID_RUN_FREQUENCIES:
            raise ValueError(
                f"Unsupported run_frequency '{run_frequency}'. Must be one of: "
                f"{', '.join(sorted(VALID_RUN_FREQUENCIES))}."
            )
        if run_frequency == "HOURLY":
            msg = (
                f"Rule '{rule_name}' uses deprecated run_frequency 'HOURLY'. "
                "Use 'HOURLY_CUSTOMIZABLE' (multi-event) or 'LIVE' (single-event)."
            )
            if strict:
                raise ValueError(msg)
            _LOGGER.warning(msg)

    schedule_customizations = rule_cfg.get("schedule_customizations")
    if schedule_customizations is not None:
        if not isinstance(schedule_customizations, dict):
            raise TypeError("'schedule_customizations' must be a YAML mapping.")
        if run_frequency not in CUSTOMIZABLE_RUN_FREQUENCIES:
            raise ValueError(
                f"'schedule_customizations' is only valid when 'run_frequency' is one of "
                f"{', '.join(sorted(CUSTOMIZABLE_RUN_FREQUENCIES))} "
                f"(got {run_frequency!r})."
            )
        unknown_keys = (
            set(schedule_customizations.keys()) - ALLOWED_SCHEDULE_CUSTOMIZATION_KEYS
        )
        if unknown_keys:
            raise ValueError(
                f"Unknown schedule_customizations keys: {', '.join(sorted(unknown_keys))}. "
                f"Allowed keys: {', '.join(sorted(ALLOWED_SCHEDULE_CUSTOMIZATION_KEYS))}."
            )

        enrichment = schedule_customizations.get("ensure_enrichment_completeness")
        if enrichment is not None and not isinstance(enrichment, bool):
            raise ValueError("'ensure_enrichment_completeness' must be a boolean.")

        late_adj = schedule_customizations.get("late_arriving_data_adjustment")
        if late_adj is not None and (
            not isinstance(late_adj, str) or not DURATION_PATTERN.match(late_adj)
        ):
            raise ValueError(
                "'late_arriving_data_adjustment' must be a duration string in seconds "
                f"ending with 's' (e.g., '300s'), got {late_adj!r}."
            )


def _validate_rule_file(file_rule_name: str, rule_text: str):
    """Validate that the rule name in the file matches the file name."""
    match = re.search(r"rule\s+([a-zA-Z0-9_]+)\s*\{", rule_text)
    if not match or match.group(1).casefold() != file_rule_name.casefold():
        raise ValueError("Rule name in file does not match file name.")


def _call_verify_rule_text(chronicle, rule_text: str) -> dict[str, Any]:
    """Invoke Chronicle v1alpha instances:verifyRuleText to obtain full validation & schedule metadata."""
    cleaned_rule = rule_text.strip("` \n\t\r")
    return chronicle_request(
        chronicle,
        method="POST",
        endpoint_path=":verifyRuleText",
        json={"ruleText": cleaned_rule},
        api_version=APIVersion.V1ALPHA,
        error_message="Failed to validate rule",
    )


def _validate_allowed_schedule(
    rule_name: str,
    configured_frequency: str | None,
    allowed_frequencies: list[str],
    *,
    strict: bool = False,
):
    """Validate configured run_frequency against allowedRunFrequencies from verifyRuleText."""
    if not configured_frequency or not allowed_frequencies:
        return

    if configured_frequency in allowed_frequencies:
        return

    if configured_frequency in LEGACY_RUN_FREQUENCIES:
        msg = (
            f"Rule '{rule_name}' has run_frequency='{configured_frequency}', which is not in "
            f"allowedRunFrequencies={allowed_frequencies} returned by verifyRuleText and will be "
            "coerced by Google SecOps. Update secops_rules.yaml to one of the allowed frequencies."
        )
        if strict:
            raise ValueError(msg)
        _LOGGER.warning(msg)
        return

    raise ValueError(
        f"Rule '{rule_name}' has run_frequency='{configured_frequency}', which is not permitted "
        f"for this rule. Allowed run frequencies: {allowed_frequencies}."
    )


def _validate_rule_with_chronicle(
    chronicle,
    rule_name: str,
    rule_text: str,
    *,
    rule_cfg: dict[str, Any] | None = None,
    strict: bool = False,
):
    """Validate the rule text and schedule eligibility using Chronicle v1alpha verifyRuleText."""
    response = _call_verify_rule_text(chronicle, rule_text)
    diagnostics = response.get("compilationDiagnostics", []) or []

    for diag in diagnostics:
        if diag.get("severity") == "WARNING" and diag.get("message"):
            _LOGGER.warning(
                "Compilation warning in rule '%s': %s", rule_name, diag["message"]
            )

    allowed_frequencies = response.get("allowedRunFrequencies") or []
    configured_frequency = (rule_cfg or {}).get("run_frequency")

    if response.get("success", False):
        _validate_allowed_schedule(
            rule_name,
            configured_frequency,
            allowed_frequencies,
            strict=strict,
        )
        _LOGGER.info(
            "Rule %s successfully verified (allowedRunFrequencies=%s, nearRealTimeLiveRuleEligible=%s).",
            rule_name,
            allowed_frequencies or "unspecified",
            response.get("nearRealTimeLiveRuleEligible"),
        )
        return

    error_messages = [
        d.get("message", "")
        for d in diagnostics
        if d.get("severity") in (None, "ERROR", "SEVERITY_UNSPECIFIED")
        and d.get("message")
    ]
    error_message = error_messages[0] if error_messages else "Unknown validation error"

    if "reference list" in error_message:
        _handle_reference_list_error(rule_name, error_message)
    elif "Could not find Data Table" in error_message:
        _handle_data_table_error(rule_name, error_message)
    else:
        raise ValueError(f"Rule verification failed: {error_message}")

    # Even when a local reference list / data table is not yet pushed, check allowed schedules if returned
    _validate_allowed_schedule(
        rule_name,
        configured_frequency,
        allowed_frequencies,
        strict=strict,
    )


def _handle_reference_list_error(rule_name: str, error_message: str):
    """Handle reference list errors during rule validation."""
    match = re.search(r"for reference list\s+'(\S+)'", error_message)
    if not match:
        raise ValueError("Could not extract reference list name.")

    ref_list_name = match.group(1)
    if not config.SECOPS_REFERENCE_LISTS_CONFIG_PATH.is_file():
        raise ValueError(f"Reference list '{ref_list_name}' not found.")

    with open(config.SECOPS_REFERENCE_LISTS_CONFIG_PATH, "r", encoding="utf-8") as f:
        ref_lists = (ruamel_yaml.load(f) or {}).keys()

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
    match = re.search(r"Data Table Name: (.*?)(?:\n|$)", error_message)
    if not match:
        raise ValueError("Could not extract data table name.")

    table_name = match.group(1).strip()
    local_tables = DataTables.load_data_table_config().keys()

    if table_name in local_tables:
        _LOGGER.info(
            "Rule %s verified (data table '%s' is local).", rule_name, table_name
        )
    else:
        raise ValueError(f"Data table '{table_name}' not found.")


if __name__ == "__main__":
    cli()

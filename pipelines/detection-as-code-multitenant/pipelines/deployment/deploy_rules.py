#!/usr/bin/env python3

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

# PYTHON_ARGCOMPLETE_OK
"""
YARA-L Rule & Deployment Configuration Pipeline for Google SecOps.

This script deploys local YARA-L rules (*.yaral) and optional companion YAML
deployment configurations (*.yaml) to Google SecOps (Chronicle) tenants:
- Compares local rules and YAML configs against remote SecOps state via `compare_rules`.
- Creates missing rules in SecOps and configures their deployment (`enabled`,
  `alerting`, `run_frequency`, `schedule_customizations`) from `<RuleName>.yaml`
  (falling back to enabling rules automatically in `--env=prod` when no YAML exists).
- Updates rule contents (`text`, `scope`) and/or `RuleDeployment` scheduler settings
  (`LIVE_CUSTOMIZABLE`, `HOURLY_CUSTOMIZABLE`, `scheduleCustomizations`, archiving)
  for rules that have drifted.
- Archives extra rules in SecOps (disabling alerts and execution), unless --skip-extras is set.
- Supports dry-run simulation (--dry-run) and delta export to JSON (--deltas-file).
"""

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import argcomplete
import deployment_common
from compare_rules import Deltas, Rule, compare_rules
from secops.chronicle.client import ChronicleClient
from secops.exceptions import APIError, SecOpsError

SKIP_EXTRAS = False


def get_repo_rule_text(rules_path: Path, tenant: str, rule_name: str) -> str:
    repo_rule_path = rules_path / "tenants" / tenant / f"{rule_name}.yaral"
    return repo_rule_path.read_text(encoding="utf-8")


def create_rule(
    chronicle_client: ChronicleClient,
    rule_text: str,
    scope_resource: str | None = None,
) -> str:
    new_rule = deployment_common.create_rule_v1(
        chronicle_client, rule_text, scope=scope_resource
    )
    return deployment_common.get_rule_id_from_location(new_rule["name"])


def enable_rule(chronicle_client: ChronicleClient, rule_id: str):
    chronicle_client.enable_rule(rule_id, True)


def apply_rule_deployment_config(
    chronicle_client: ChronicleClient,
    rule_id: str,
    repo_cfg: dict[str, Any],
    *,
    env: str,
    current_rule: Rule | None = None,
):
    """Apply `<RuleName>.yaml` deployment & schedule settings to a rule deployment."""
    if not repo_cfg:
        if current_rule is None and env == "prod":
            enable_rule(chronicle_client, rule_id)
        return

    # Handle archiving as a safe two-step operation per Chronicle v1 API requirements
    if repo_cfg.get("archived", False):
        if current_rule is None or current_rule.get("live", False):
            deployment_common.update_rule_deployment_v1(
                chronicle_client,
                rule_id,
                enabled=False,
                alerting=False,
            )
        deployment_common.update_rule_deployment_v1(
            chronicle_client,
            rule_id,
            archived=True,
        )
        return

    default_enabled = env == "prod" if current_rule is None else None
    enabled = repo_cfg.get("enabled", default_enabled)
    alerting = repo_cfg.get("alerting")
    run_frequency = repo_cfg.get("run_frequency")
    has_sc_Or_freq = (
        "schedule_customizations" in repo_cfg or "run_frequency" in repo_cfg
    )
    schedule_customizations = repo_cfg.get("schedule_customizations")

    if (
        enabled is None
        and alerting is None
        and run_frequency is None
        and not has_sc_Or_freq
    ):
        return

    # Ensure run_frequency is passed if updating schedule_customizations alone
    effective_freq = run_frequency
    if effective_freq is None and has_sc_Or_freq and current_rule is not None:
        effective_freq = current_rule.get("frequency")

    deployment_common.update_rule_deployment_v1(
        chronicle_client,
        rule_id,
        enabled=enabled,
        alerting=alerting,
        run_frequency=effective_freq,
        schedule_customizations=schedule_customizations,
        update_schedule_customizations=has_sc_Or_freq,
    )


def update_rule(
    chronicle_client: ChronicleClient,
    rule_details: Rule,
    new_rule_text: str,
    repo_cfg: dict[str, Any],
    tenant_details: dict[str, str],
    env: str,
):
    text_changed = rule_details.get("text_changed", True)
    deployment_changed = rule_details.get("deployment_changed", False)

    update_scope = False
    scope_resource: str | None = None
    if "scope" in repo_cfg:
        desired_scope_id = deployment_common.extract_scope_id(repo_cfg.get("scope"))
        if desired_scope_id != rule_details.get("scope"):
            update_scope = True
            region = tenant_details.get("region", deployment_common.REGION)
            scope_resource = deployment_common.format_scope_resource(
                tenant_details["gcpProject"],
                region,
                tenant_details["customerId"],
                repo_cfg.get("scope"),
            )

    if text_changed or update_scope:
        deployment_common.update_rule_v1(
            chronicle_client,
            rule_details["id"],
            rule_text=new_rule_text if text_changed else None,
            scope=scope_resource,
            update_scope=update_scope,
        )

    if deployment_changed:
        apply_rule_deployment_config(
            chronicle_client,
            rule_details["id"],
            repo_cfg,
            env=env,
            current_rule=rule_details,
        )


def delete_rule(chronicle_client: ChronicleClient, rule_details: Rule):
    if rule_details.get("live", False):
        chronicle_client.update_rule_deployment(
            rule_details["id"], enabled=False, alerting=False
        )

    chronicle_client.update_rule_deployment(rule_details["id"], archived=True)


def sync_tenant_rule_tags(
    chronicle_client: ChronicleClient,
    tenant_details: dict[str, str],
    tag_updates: Sequence[tuple[str, str, Sequence[str]]],
) -> list[str]:
    """Auto-create missing custom tags and batch-apply rule tags via Chronicle v1alpha."""
    if not tag_updates:
        return []

    all_desired_tags: set[str] = set()
    for _rule_name, _rule_id, desired_tags in tag_updates:
        all_desired_tags.update(desired_tags)

    if all_desired_tags:
        deployment_common.ensure_custom_tags_v1alpha(chronicle_client, all_desired_tags)

    region = tenant_details.get("region", deployment_common.REGION)
    return deployment_common.modify_rule_tags_v1alpha(
        chronicle_client,
        tenant_details["gcpProject"],
        region,
        tenant_details["customerId"],
        tag_updates,
    )


def deploy_tenant_rules(
    chronicle_client: ChronicleClient,
    rules_path: Path,
    tenant_name: str,
    tenant_details: dict[str, str],
    *,
    env: str = "prod",
    skip_extras: bool = False,
) -> tuple[Deltas, bool]:
    """Compare and deploy rules, schedules, and v1alpha rule tags for a single tenant."""
    region = tenant_details.get("region", deployment_common.REGION)
    tenant_errors = False

    if deployment_common.verbose:
        print(f"Processing {tenant_name}")

    tenant_deltas, repo_rules, _ = compare_rules(
        chronicle_client, rules_path, tenant_name
    )

    if (
        len(tenant_deltas["missing"])
        + len(tenant_deltas["changed"])
        + len(tenant_deltas["extra"])
        > deployment_common.THROTTLE_THRESHOLD
    ):
        deployment_common.throttle_calls = True

    pending_tag_updates: list[tuple[str, str, list[str]]] = []

    for rule_name in tenant_deltas["missing"]:
        if deployment_common.verbose:
            print(f"Creating missing rule {rule_name}")
        if not deployment_common.dry_run:
            deployment_common.start_iteration()
            repo_cfg = repo_rules[rule_name].get("config") or {}
            scope_resource = deployment_common.format_scope_resource(
                tenant_details["gcpProject"],
                region,
                tenant_details["customerId"],
                repo_cfg.get("scope"),
            )
            try:
                new_rule_id = create_rule(
                    chronicle_client,
                    repo_rules[rule_name]["text"],
                    scope_resource=scope_resource,
                )
                if repo_cfg.get("tags"):
                    pending_tag_updates.append(
                        (rule_name, new_rule_id, list(repo_cfg["tags"]))
                    )
                try:
                    apply_rule_deployment_config(
                        chronicle_client,
                        new_rule_id,
                        repo_cfg,
                        env=env,
                        current_rule=None,
                    )
                except APIError as e:
                    tenant_errors = True
                    print(
                        f"Error configuring deployment for rule {tenant_name}/{rule_name}: {e!r}"
                    )
            except APIError as e:
                tenant_errors = True
                print(f"Error creating rule {tenant_name}/{rule_name}: {e!r}")
            deployment_common.end_iteration()

    for rule_name, secops_rule_details in tenant_deltas["changed"].items():
        if deployment_common.verbose:
            print(f"Updating changed rule {rule_name}")
        if not deployment_common.dry_run:
            deployment_common.start_iteration()
            repo_cfg = repo_rules[rule_name].get("config") or {}
            try:
                update_rule(
                    chronicle_client,
                    secops_rule_details,
                    repo_rules[rule_name]["text"],
                    repo_cfg,
                    tenant_details,
                    env,
                )
                if secops_rule_details.get("tags_changed", False):
                    pending_tag_updates.append(
                        (
                            rule_name,
                            secops_rule_details["id"],
                            list(repo_cfg.get("tags") or []),
                        )
                    )
            except APIError as e:
                tenant_errors = True
                print(f"Error updating rule {tenant_name}/{rule_name}: {e!r}")
            deployment_common.end_iteration()

    if not deployment_common.dry_run and pending_tag_updates:
        deployment_common.start_iteration()
        try:
            sync_tenant_rule_tags(chronicle_client, tenant_details, pending_tag_updates)
        except (APIError, SecOpsError) as e:
            tenant_errors = True
            print(f"Error updating rule tags for tenant {tenant_name}: {e!r}")
        deployment_common.end_iteration()

    for rule_name, secops_rule_details in tenant_deltas["extra"].items():
        if deployment_common.verbose:
            print(f"Deleting extra rule {rule_name}")
        if not deployment_common.dry_run and not skip_extras:
            deployment_common.start_iteration()
            try:
                delete_rule(chronicle_client, secops_rule_details)
            except APIError as e:
                tenant_errors = True
                print(f"Error deleting rule {tenant_name}/{rule_name}: {e!r}")
            deployment_common.end_iteration()

    if not deployment_common.dry_run:
        print(
            f"{tenant_name}: ",
            f"{len(tenant_deltas['missing'])} created,",
            f"{len(tenant_deltas['changed'])} updated,",
            f"{len(tenant_deltas['extra'])}",
            "deleted" if not skip_extras else "to be deleted",
            flush=True,
        )
    else:
        print(
            f"{tenant_name}: ",
            f"{len(tenant_deltas['missing'])} to be created,",
            f"{len(tenant_deltas['changed'])} to be updated,",
            f"{len(tenant_deltas['extra'])} to be deleted",
            flush=True,
        )

    return tenant_deltas, tenant_errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Deploy local YARA-L rules and YAML deployment configs to SecOps"
    )
    deployment_common.add_standard_arguments(parser)
    parser.add_argument(
        "--deltas-file",
        default=os.getenv("DAC_RULES_DELTAS_FILE", ""),
        help="The path where to write a file with all the deltas found while comparing, defaults to $DAC_RULES_DELTAS_FILE",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Only simulate deployment"
    )
    parser.add_argument(
        "--skip-extras",
        action="store_true",
        help="Do not delete extra rules from SecOps",
    )
    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    env, rules_path, all_tenants, selected_tenants_names = (
        deployment_common.process_standard_arguments(args)
    )

    if args.skip_extras:
        SKIP_EXTRAS = True

    deltas: dict[str, Deltas] = {}
    errors = False
    for tenant_name in sorted(selected_tenants_names):
        if (
            not all_tenants
            or env not in all_tenants
            or tenant_name not in all_tenants[env]
        ):
            print(
                f"Error: Tenant info not found for tenant {tenant_name} in environment {env}"
            )
            sys.exit(1)

        tenant_details = all_tenants[env][tenant_name]
        chronicle_client = deployment_common.create_chronicle_client(
            tenant_details, args.impersonate_sa
        )

        tenant_deltas, tenant_errors = deploy_tenant_rules(
            chronicle_client,
            rules_path,
            tenant_name,
            tenant_details,
            env=env,
            skip_extras=SKIP_EXTRAS,
        )
        deltas[tenant_name] = tenant_deltas
        if tenant_errors:
            errors = True

    if args.deltas_file:
        with open(args.deltas_file, "w", encoding="utf-8") as deltas_file:
            json.dump(deltas, deltas_file, indent=4)

    if errors:
        sys.exit(2)

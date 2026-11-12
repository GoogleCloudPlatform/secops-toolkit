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
YARA-L Rules & Deployment Configuration Comparison for Google SecOps.

This script compares local YARA-L rule files (*.yaral) and optional companion
deployment configurations (*.yaml) in `rules/tenants/<tenant>/` (with inheritance
from `rules/shared/`) against active, non-archived rules in Google SecOps tenants.

Deltas identified:
- missing: Non-archived rules defined locally in the repository but absent from SecOps.
- changed: Rules present in both environments whose YARA-L text or configured YAML
  deployment settings (`enabled`, `alerting`, `archived`, `run_frequency`,
  `schedule_customizations`, `scope`) differ.
- extra: Active rules deployed in SecOps that do not exist in the local repository.

Output:
- Summarizes missing, changed, and extra rule counts per tenant to stdout.
- Optionally exports detailed delta metadata to a JSON file (--deltas-file).
"""

import argparse
import difflib
import json
import os
import sys
from pathlib import Path
from typing import Any, TypedDict

import argcomplete
import deployment_common
import yaml
from secops.chronicle.client import ChronicleClient
from secops.exceptions import APIError


class Rule(TypedDict, total=False):
    id: str
    version: str
    text: str
    live: bool
    alerting: bool
    archived: bool
    frequency: str | None
    schedule_customizations: dict[str, Any] | None
    scope: str | None
    tags: list[str]
    execution_state: str | None
    config: dict[str, Any]
    text_changed: bool
    deployment_changed: bool
    tags_changed: bool


class Deltas(TypedDict):
    missing: dict[str, Rule]
    changed: dict[str, Rule]
    extra: dict[str, Rule]


def build_remote_config_dict(secops_rule: Rule) -> dict[str, Any]:
    """Convert a fetched SecOps Rule dict into its canonical YAML config dict."""
    cfg: dict[str, Any] = {
        "enabled": secops_rule.get("live", False),
        "alerting": secops_rule.get("alerting", False),
        "archived": secops_rule.get("archived", False),
    }
    if secops_rule.get("frequency"):
        cfg["run_frequency"] = secops_rule["frequency"]
    if secops_rule.get("scope"):
        cfg["scope"] = secops_rule["scope"]
    if secops_rule.get("tags"):
        cfg["tags"] = secops_rule["tags"]
    if secops_rule.get("schedule_customizations"):
        cfg["schedule_customizations"] = secops_rule["schedule_customizations"]
    return cfg


def has_tags_drift(repo_cfg: dict[str, Any], secops_rule: Rule) -> bool:
    """Return True if `tags` is configured in repo_cfg and differs from SecOps API tags."""
    if not repo_cfg or "tags" not in repo_cfg or repo_cfg["tags"] is None:
        return False
    return not deployment_common.tags_equal(
        repo_cfg["tags"], secops_rule.get("tags") or []
    )


def has_deployment_drift(repo_cfg: dict[str, Any], secops_rule: Rule) -> bool:
    """Return True if any deployment field configured in repo_cfg differs from SecOps."""
    if not repo_cfg:
        return False

    if "enabled" in repo_cfg and repo_cfg["enabled"] != secops_rule.get("live", False):
        return True
    if "alerting" in repo_cfg and repo_cfg["alerting"] != secops_rule.get(
        "alerting", False
    ):
        return True
    if "archived" in repo_cfg and repo_cfg["archived"] != secops_rule.get(
        "archived", False
    ):
        return True
    if "scope" in repo_cfg:
        repo_scope = deployment_common.extract_scope_id(repo_cfg.get("scope"))
        if repo_scope != secops_rule.get("scope"):
            return True
    if "run_frequency" in repo_cfg and repo_cfg["run_frequency"] != secops_rule.get(
        "frequency"
    ):
        return True
    if "schedule_customizations" in repo_cfg or "run_frequency" in repo_cfg:
        repo_sc = deployment_common.normalize_schedule_customizations(
            repo_cfg.get("schedule_customizations")
        )
        remote_sc = deployment_common.normalize_schedule_customizations(
            secops_rule.get("schedule_customizations")
        )
        if repo_sc != remote_sc:
            return True

    return False


def fetch_rules_from_tenant(chronicle_client: ChronicleClient) -> dict[str, Rule]:
    try:
        secops_rules_list = deployment_common.list_customer_rules_with_tags_v1alpha(
            chronicle_client
        )
    except APIError as e:
        print(f"Error fetching rules: {e!r}")
        raise

    secops_rules = {
        deployment_common.get_rule_id_from_location(rule["name"]): rule
        for rule in secops_rules_list
        if rule.get("name")
    }

    try:
        secops_rules_deployments = chronicle_client.list_rule_deployments(
            filter_query="archived=false",
            as_list=True,
        )
    except APIError as e:
        print(f"Error fetching rule deployments: {e!r}")
        raise

    secops_active_rules: dict[str, Rule] = {}
    for deployment in secops_rules_deployments:
        rule_id = deployment_common.get_rule_id_from_location(
            deployment.get("name", "")
        )
        rule = secops_rules.get(rule_id)
        if not rule:
            continue
        secops_active_rules[rule["displayName"]] = {
            "id": rule_id,
            "version": rule.get("revisionId", ""),
            "text": rule.get("text", ""),
            "live": deployment.get("enabled", False),
            "alerting": deployment.get("alerting", False),
            "archived": deployment.get("archived", False),
            "frequency": deployment.get("runFrequency"),
            "schedule_customizations": (
                deployment_common.schedule_customizations_api_to_yaml(
                    deployment.get("scheduleCustomizations")
                )
            ),
            "scope": deployment_common.extract_scope_id(rule.get("scope")),
            "tags": deployment_common.extract_api_rule_tags(rule),
            "execution_state": deployment.get("executionState"),
        }

    return secops_active_rules


def compare_rules(chronicle_client: ChronicleClient, rules_path: Path, tenant: str):
    deltas: Deltas = {
        "missing": {},
        "changed": {},
        "extra": {},
    }

    rules_dir_tenant = rules_path / "tenants" / tenant
    if not rules_dir_tenant.exists() or not rules_dir_tenant.is_dir():
        raise OSError(f"Directory not found for tenant '{tenant}': {rules_dir_tenant}")

    repo_rules: dict[str, Rule] = {}
    for p in sorted(rules_dir_tenant.glob("*.yaral")):
        rule_cfg = deployment_common.load_repo_rule_config(rules_path, tenant, p.stem)
        repo_rules[p.stem] = {
            "text": p.read_text(encoding="utf-8"),
            "config": rule_cfg,
        }

    secops_rules = fetch_rules_from_tenant(chronicle_client)

    all_repo_rule_names = set(repo_rules.keys())
    all_secops_rule_names = set(secops_rules.keys())

    # Rules in repo but not active in SecOps (skip rules marked archived: true locally)
    rules_missing_from_secops = all_repo_rule_names - all_secops_rule_names
    for rule_name in sorted(rules_missing_from_secops):
        repo_cfg = repo_rules[rule_name].get("config") or {}
        if repo_cfg.get("archived", False):
            continue
        deltas["missing"][rule_name] = {"config": repo_cfg} if repo_cfg else {}
        if deployment_common.verbose:
            print(f"Missing in SecOps, present in repo: {rule_name}")

    # Rules in both, check for text or YAML deployment differences
    rules_in_both = all_repo_rule_names.intersection(all_secops_rule_names)
    for rule_name in sorted(rules_in_both):
        secops_rule = secops_rules[rule_name]
        secops_text = secops_rule["text"]
        repo_text = repo_rules[rule_name]["text"]
        repo_cfg = repo_rules[rule_name].get("config") or {}

        # Approximate whitespace-insensitive diff by splitting lines by
        # whitespace and comparing tokens.
        repo_tokens = [line.split() for line in repo_text.splitlines()]
        secops_tokens = [line.split() for line in secops_text.splitlines()]

        text_changed = repo_tokens != secops_tokens
        deployment_changed = has_deployment_drift(repo_cfg, secops_rule)
        tags_changed = has_tags_drift(repo_cfg, secops_rule)

        if text_changed or deployment_changed or tags_changed:
            changed_entry: Rule = dict(secops_rule)
            changed_entry["text_changed"] = text_changed
            changed_entry["deployment_changed"] = deployment_changed
            changed_entry["tags_changed"] = tags_changed
            deltas["changed"][rule_name] = changed_entry

            if deployment_common.verbose:
                reasons = []
                if text_changed:
                    reasons.append("text")
                if deployment_changed:
                    reasons.append("deployment")
                if tags_changed:
                    reasons.append("tags")
                print(
                    f"Different between SecOps and repo ({', '.join(reasons)}): "
                    f"{rule_name} ({secops_rule['id']})"
                )
            if deployment_common.debug:
                if text_changed:
                    diff = difflib.unified_diff(
                        secops_text.splitlines(keepends=True),
                        repo_text.splitlines(keepends=True),
                        fromfile=f"{rule_name} (SecOps)",
                        tofile=f"{rule_name}.yaral (repository)",
                    )
                    sys.stdout.writelines(diff)
                if deployment_changed or tags_changed:
                    remote_yaml = yaml.safe_dump(
                        build_remote_config_dict(secops_rule), sort_keys=False
                    )
                    local_yaml = yaml.safe_dump(repo_cfg, sort_keys=False)
                    cfg_diff = difflib.unified_diff(
                        remote_yaml.splitlines(keepends=True),
                        local_yaml.splitlines(keepends=True),
                        fromfile=f"{rule_name} deployment (SecOps)",
                        tofile=f"{rule_name}.yaml (repository)",
                    )
                    sys.stdout.writelines(cfg_diff)

    # Rules in SecOps but not in repo
    rules_missing_from_repo = all_secops_rule_names - all_repo_rule_names
    for rule_name in sorted(rules_missing_from_repo):
        deltas["extra"][rule_name] = secops_rules[rule_name]
        if deployment_common.verbose:
            print(
                f"Extra in SecOps, not present in repo: {rule_name} ({secops_rules[rule_name]['id']})"
            )
        if deployment_common.debug:
            print(secops_rules[rule_name]["text"])

    return deltas, repo_rules, secops_rules


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare local YARA-L rules and YAML deployment configs with SecOps"
    )
    deployment_common.add_standard_arguments(parser)
    parser.add_argument(
        "--deltas-file",
        default=os.getenv("DAC_RULES_DELTAS_FILE", ""),
        help="The path where to write a file with all the deltas found while comparing, defaults to $DAC_RULES_DELTAS_FILE",
    )
    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    env, rules_path, all_tenants, selected_tenants_names = (
        deployment_common.process_standard_arguments(args)
    )

    deltas = {}
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

        if deployment_common.verbose:
            print(f"Processing {tenant_name}")

        tenant_deltas, _, _ = compare_rules(chronicle_client, rules_path, tenant_name)
        print(
            f"{tenant_name}: ",
            f"{len(tenant_deltas['missing'])} missing,",
            f"{len(tenant_deltas['changed'])} changed,",
            f"{len(tenant_deltas['extra'])} extra",
            flush=True,
        )
        deltas[tenant_name] = tenant_deltas

    if args.deltas_file:
        with open(args.deltas_file, "w", encoding="utf-8") as deltas_file:
            json.dump(deltas, deltas_file, indent=4)

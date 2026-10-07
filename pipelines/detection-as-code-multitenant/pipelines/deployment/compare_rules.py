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
YARA-L Rules Comparison and Drift Detection for Google SecOps.

This script compares local YARA-L rule files (*.yaral) in `rules/tenants/<tenant>/`
against active, non-archived rules deployed in Google SecOps (Chronicle) tenants.

Deltas identified:
- missing: Rules defined locally in the repository but absent from SecOps.
- changed: Rules present in both environments whose text differs (evaluated via
  whitespace-insensitive token comparison; diffs can be viewed using --debug).
- extra: Rules deployed in SecOps that do not exist in the local repository.

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
from typing import TypedDict

import argcomplete
import deployment_common
from secops.chronicle.client import ChronicleClient
from secops.exceptions import APIError


class Rule(TypedDict, total=False):
    id: str
    version: str
    text: str
    live: bool
    alerting: bool
    frequency: str


class Deltas(TypedDict):
    missing: dict[str, Rule]
    changed: dict[str, Rule]
    extra: dict[str, Rule]


def fetch_rules_from_tenant(chronicle_client: ChronicleClient) -> dict[str, Rule]:
    try:
        secops_rules_list = chronicle_client.list_rules(as_list=True)
    except APIError as e:
        print(f"Error fetching rules: {e!r}")
        raise

    secops_rules = {
        deployment_common.get_rule_id_from_location(rule["name"]): rule
        for rule in secops_rules_list
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
        rule_id = deployment["name"].split("/")[7]
        rule = secops_rules[rule_id]
        secops_active_rules[rule["displayName"]] = {
            "id": rule_id,
            "version": rule["revisionId"],
            "text": rule["text"],
            "live": deployment.get("enabled", False),
            "alerting": deployment.get("alerting", False),
            "frequency": deployment["runFrequency"],
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

    repo_rules: dict[str, Rule] = {
        p.stem: {"text": p.read_text()} for p in rules_dir_tenant.glob("*.yaral")
    }
    secops_rules = fetch_rules_from_tenant(chronicle_client)

    all_repo_rule_names = set(repo_rules.keys())
    all_secops_rule_names = set(secops_rules.keys())

    # Rules in repo but not in SecOps
    rules_missing_from_secops = all_repo_rule_names - all_secops_rule_names
    for rule_name in sorted(rules_missing_from_secops):
        deltas["missing"][rule_name] = {}
        if deployment_common.verbose:
            print(f"Missing in SecOps, present in repo: {rule_name}")

    # Rules in both, check for differences
    rules_in_both = all_repo_rule_names.intersection(all_secops_rule_names)
    for rule_name in sorted(rules_in_both):
        secops_text = secops_rules[rule_name]["text"]
        repo_text = repo_rules[rule_name]["text"]

        # Approximate whitespace-insensitive diff by splitting lines by
        # whitespace and comparing tokens.
        repo_tokens = [line.split() for line in repo_text.splitlines()]
        secops_tokens = [line.split() for line in secops_text.splitlines()]

        if repo_tokens != secops_tokens:
            deltas["changed"][rule_name] = secops_rules[rule_name]
            if deployment_common.verbose:
                print(
                    f"Different between SecOps and repo: {rule_name} ({secops_rules[rule_name]['id']})"
                )
            if deployment_common.debug:
                diff = difflib.unified_diff(
                    secops_text.splitlines(keepends=True),
                    repo_text.splitlines(keepends=True),
                    fromfile=f"{rule_name} (SecOps)",
                    tofile=f"{rule_name}.yaral (repository)",
                )
                sys.stdout.writelines(diff)

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
        description="Compare local YARA-L rules with SecOps"
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
            or not env in all_tenants
            or not tenant_name in all_tenants[env]
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
        with open(args.deltas_file, "w") as deltas_file:
            json.dump(deltas, deltas_file, indent=4)

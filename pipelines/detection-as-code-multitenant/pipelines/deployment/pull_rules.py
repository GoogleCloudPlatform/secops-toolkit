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
Pull YARA-L Rules and YAML Deployment Configurations from Google SecOps.

This script synchronizes rule and deployment state by fetching active YARA-L rules
and their `RuleDeployment` configurations (`enabled`, `alerting`, `run_frequency`,
`schedule_customizations`, `scope`) from Google SecOps (Chronicle) tenants and
updating local files in `rules/tenants/<tenant>/`:
- Uses `compare_rules` to determine missing, changed, and extra rules.
- Deletes local `.yaral` and `.yaml` files for rules no longer present in SecOps.
- Overwrites changed `.yaral` and/or `.yaml` files locally, breaking any existing
  symlinks into standalone tenant files when drifted.
- Creates new local `.yaral` and `.yaml` files for rules created directly in SecOps
  (or keeps existing rules synced when `--sync-all-configs` is passed).
"""

import argparse
import sys
from pathlib import Path

import argcomplete
import deployment_common
from compare_rules import Rule, build_remote_config_dict, compare_rules


def get_repo_rule_path(rules_path: Path, tenant: str, rule_name: str) -> Path:
    return rules_path / "tenants" / tenant / f"{rule_name}.yaral"


def get_repo_rule_config_path(rules_path: Path, tenant: str, rule_name: str) -> Path:
    return rules_path / "tenants" / tenant / f"{rule_name}.yaml"


def write_rule_config_file(
    rules_path: Path, tenant: str, rule_name: str, secops_rule: Rule
):
    cfg_file = get_repo_rule_config_path(rules_path, tenant, rule_name)
    if cfg_file.is_symlink():
        cfg_file.unlink()
    remote_cfg = build_remote_config_dict(secops_rule)
    cfg_file.write_text(
        deployment_common.format_rule_config_yaml(remote_cfg), encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pull YARA-L rules and YAML deployment configs from SecOps to the local repository"
    )
    deployment_common.add_standard_arguments(parser)
    parser.add_argument(
        "--no-configs",
        action="store_true",
        help="Only pull .yaral rule text files without creating/updating companion .yaml deployment configs",
    )
    parser.add_argument(
        "--sync-all-configs",
        action="store_true",
        help="Write companion .yaml deployment configs for all active remote rules (even unchanged rules lacking a .yaml file)",
    )
    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    env, rules_path, all_tenants, selected_tenants_names = (
        deployment_common.process_standard_arguments(args)
    )

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

        tenant_deltas, _, secops_rules = compare_rules(
            chronicle_client, rules_path, tenant_name
        )

        for rule_name in tenant_deltas["missing"]:
            if deployment_common.verbose:
                print(f"Deleting missing rule: {rule_name}")
            rule_file = get_repo_rule_path(rules_path, tenant_name, rule_name)
            rule_file.unlink(missing_ok=True)
            cfg_file = get_repo_rule_config_path(rules_path, tenant_name, rule_name)
            cfg_file.unlink(missing_ok=True)

        for rule_name, secops_rule_details in tenant_deltas["changed"].items():
            if deployment_common.verbose:
                print(f"Updating changed rule: {rule_name}")
            if secops_rule_details.get("text_changed", True):
                rule_file = get_repo_rule_path(rules_path, tenant_name, rule_name)
                if rule_file.is_symlink():
                    rule_file.unlink()
                rule_file.write_text(secops_rule_details["text"], encoding="utf-8")
            if not args.no_configs and (
                secops_rule_details.get("deployment_changed", False)
                or secops_rule_details.get("tags_changed", False)
            ):
                write_rule_config_file(
                    rules_path, tenant_name, rule_name, secops_rule_details
                )

        for rule_name, secops_rule_details in tenant_deltas["extra"].items():
            if deployment_common.verbose:
                print(f"Creating extra rule: {rule_name}")
            rule_file = get_repo_rule_path(rules_path, tenant_name, rule_name)
            rule_file.write_text(secops_rule_details["text"], encoding="utf-8")
            if not args.no_configs:
                write_rule_config_file(
                    rules_path, tenant_name, rule_name, secops_rule_details
                )

        if args.sync_all_configs and not args.no_configs:
            for rule_name, secops_rule_details in secops_rules.items():
                cfg_file = get_repo_rule_config_path(rules_path, tenant_name, rule_name)
                if not cfg_file.exists():
                    write_rule_config_file(
                        rules_path, tenant_name, rule_name, secops_rule_details
                    )

        print(
            f"{tenant_name}: ",
            f"{len(tenant_deltas['missing'])} removed,",
            f"{len(tenant_deltas['changed'])} updated,",
            f"{len(tenant_deltas['extra'])} created",
            flush=True,
        )

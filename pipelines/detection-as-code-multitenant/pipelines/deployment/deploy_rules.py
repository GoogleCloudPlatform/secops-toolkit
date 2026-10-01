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
YARA-L Rule Deployment Pipeline for Google SecOps.

This script deploys local YARA-L rules to Google SecOps (Chronicle) tenants:
- Compares local rules against remote SecOps rules using `compare_rules`.
- Creates missing rules in SecOps and automatically enables them in production (--env=prod).
- Updates rule contents for rules that have changed.
- Archives extra rules in SecOps (disabling alerts and execution), unless --skip-extras is set.
- Automatically enables API request rate throttling when delta volumes exceed thresholds.
- Supports dry-run simulation (--dry-run) and delta export to JSON (--deltas-file).
"""

import argparse
import json
import os
import sys
from pathlib import Path

import argcomplete
import deployment_common
from compare_rules import Deltas, Rule, compare_rules
from secops.chronicle.client import ChronicleClient
from secops.exceptions import APIError

SKIP_EXTRAS = False


def get_repo_rule_text(rules_path: Path, tenant: str, rule_name: str) -> str:
    repo_rule_path = rules_path / "tenants" / tenant / f"{rule_name}.yaral"
    return repo_rule_path.read_text()


def create_rule(chronicle_client: ChronicleClient, rule_text: str) -> str:
    new_rule = chronicle_client.create_rule(rule_text)
    return deployment_common.get_rule_id_from_location(new_rule["name"])


def enable_rule(chronicle_client: ChronicleClient, rule_id: str):
    chronicle_client.enable_rule(rule_id, True)


def update_rule(
    chronicle_client: ChronicleClient,
    rule_details: Rule,
    new_rule_text: str,
):
    chronicle_client.update_rule(rule_details["id"], new_rule_text)


def delete_rule(chronicle_client: ChronicleClient, rule_details: Rule):
    if rule_details.get("live", False):
        chronicle_client.update_rule_deployment(
            rule_details["id"], enabled=False, alerting=False
        )

    chronicle_client.update_rule_deployment(rule_details["id"], archived=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy local YARA-L rules to SecOps")
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

        tenant_deltas, repo_rules, _ = compare_rules(
            chronicle_client, rules_path, tenant_name
        )
        deltas[tenant_name] = tenant_deltas

        if (
            len(tenant_deltas["missing"])
            + len(tenant_deltas["changed"])
            + len(tenant_deltas["extra"])
            > deployment_common.THROTTLE_THRESHOLD
        ):
            deployment_common.throttle_calls = True

        for rule_name in tenant_deltas["missing"]:
            if deployment_common.verbose:
                print(f"Creating missing rule {rule_name}")
            if not deployment_common.dry_run:
                deployment_common.start_iteration()
                try:
                    new_rule_id = create_rule(
                        chronicle_client,
                        repo_rules[rule_name]["text"],
                    )
                    if env == "prod":
                        try:
                            enable_rule(chronicle_client, new_rule_id)
                        except APIError as e:
                            errors = True
                            print(
                                f"Error enabling rule {tenant_name}/{rule_name}: {e!r}"
                            )
                except APIError as e:
                    errors = True
                    print(f"Error creating rule {tenant_name}/{rule_name}: {e!r}")
                deployment_common.end_iteration()

        for rule_name, secops_rule_details in tenant_deltas["changed"].items():
            if deployment_common.verbose:
                print(f"Updating changed rule {rule_name}")
            if not deployment_common.dry_run:
                deployment_common.start_iteration()
                try:
                    update_rule(
                        chronicle_client,
                        secops_rule_details,
                        repo_rules[rule_name]["text"],
                    )
                except APIError as e:
                    errors = True
                    print(f"Error updating rule {tenant_name}/{rule_name}: {e!r}")
                deployment_common.end_iteration()

        for rule_name, secops_rule_details in tenant_deltas["extra"].items():
            if deployment_common.verbose:
                print(f"Deleting extra rule {rule_name}")
            if not deployment_common.dry_run and not SKIP_EXTRAS:
                deployment_common.start_iteration()
                try:
                    delete_rule(chronicle_client, secops_rule_details)
                except APIError as e:
                    errors = True
                    print(f"Error deleting rule {tenant_name}/{rule_name}: {e!r}")
                deployment_common.end_iteration()

        if not deployment_common.dry_run:
            print(
                f"{tenant_name}: ",
                f"{len(tenant_deltas['missing'])} created,",
                f"{len(tenant_deltas['changed'])} updated,",
                f"{len(tenant_deltas['extra'])}",
                "deleted" if not SKIP_EXTRAS else "to be deleted",
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

    if args.deltas_file:
        with open(args.deltas_file, "w") as deltas_file:
            json.dump(deltas, deltas_file, indent=4)

    if errors:
        sys.exit(2)

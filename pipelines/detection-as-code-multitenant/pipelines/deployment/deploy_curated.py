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
Google SecOps Curated Detection Rule Sets Deployment Pipeline.

This script manages the deployment and enablement state of Google SecOps Curated
Detection Rule Sets for multi-tenant environments:
- Uses `compare_curated` to detect discrepancies between repository YAML configs and SecOps.
- Enables missing curated rule sets in SecOps with the specified precision level (precise/broad).
- Disables extra curated rule sets in SecOps that are not tracked in the repository.
- Resolves category-to-ruleset mappings dynamically using Chronicle APIs.
- Supports dry-run simulation (--dry-run), rate-limiting throttling, and JSON delta logging (--deltas-file).
"""

import argparse
import json
import os
import sys
from pathlib import Path

import argcomplete
import deployment_common
from compare_curated import Deltas, PrecisionType, compare_curated
from secops.chronicle.client import ChronicleClient
from secops.exceptions import APIError


def enable_curated(
    chronicle_client: ChronicleClient,
    category_id: str,
    ruleset_id: str,
    precision: PrecisionType,
):
    chronicle_client.update_curated_rule_set_deployment(
        {
            "category_id": category_id,
            "rule_set_id": ruleset_id,
            "precision": precision.value,
            "enabled": True,
            "alerting": False,
        }
    )


def disable_curated(
    chronicle_client: ChronicleClient,
    category_id: str,
    ruleset_id: str,
    precision: PrecisionType,
):
    chronicle_client.update_curated_rule_set_deployment(
        {
            "category_id": category_id,
            "rule_set_id": ruleset_id,
            "precision": precision.value,
            "enabled": False,
            "alerting": False,
        }
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy local YARA-L rules to SecOps")
    deployment_common.add_standard_arguments(parser, include_rules_dir=False)
    parser.add_argument(
        "--curated-dir",
        default=os.getenv("DAC_CURATED_DIR", "curated"),
        help="The path to the local curated detection files, defaults to $DAC_CURATED_DIR or 'curated/' if missing",
    )
    parser.add_argument(
        "--deltas-file",
        default=os.getenv("DAC_CURATED_DELTAS_FILE", ""),
        help="The path where to write a file with all the deltas found while comparing, defaults to $DAC_CURATED_DELTAS_FILE",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Only simulate deployment"
    )
    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    env, _, all_tenants, selected_tenants_names = (
        deployment_common.process_standard_arguments(args, include_rules_dir=False)
    )

    curated_path = Path(args.curated_dir)
    if not curated_path.exists():
        print(
            f"Error: Local curated detection directory {args.curated_dir} does not exist,",
            "check the --curated-dir flag or the DAC_CURATED_DIR env variable",
        )
        sys.exit(1)

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

        tenant_deltas, _, _ = compare_curated(
            chronicle_client, curated_path, tenant_name
        )
        deltas[tenant_name] = tenant_deltas

        count_actions = len(tenant_deltas["missing"]) + len(tenant_deltas["extra"])

        categories_mapping = {}
        if count_actions:
            try:
                rulesets = chronicle_client.list_curated_rule_sets(as_list=True)
                for location in [r["name"] for r in rulesets]:
                    location_elements = location.split("/")
                    categories_mapping[location_elements[9]] = location_elements[7]
            except APIError as e:
                errors = True
                print(f"Error getting curated ruleSets for {tenant_name}: {e!r}")
                continue

        if count_actions > deployment_common.THROTTLE_THRESHOLD:
            deployment_common.throttle_calls = True

        for curated_name, curated_details in tenant_deltas["missing"].items():
            if deployment_common.verbose:
                print(f"Enabling curated detection {curated_name}")
            if not deployment_common.dry_run:
                deployment_common.start_iteration()
                try:
                    ruleset_id = curated_details["id"]
                    category_id = categories_mapping[ruleset_id]
                    enable_curated(
                        chronicle_client,
                        category_id,
                        ruleset_id,
                        curated_details["precision"],
                    )
                except APIError as e:
                    errors = True
                    print(
                        f"Error enabling curated detection {tenant_name}/{curated_name}: {e!r}"
                    )
                deployment_common.end_iteration()

        for curated_name, curated_details in tenant_deltas["extra"].items():
            if deployment_common.verbose:
                print(f"Disabling extra curated detection {curated_name}")
            if not deployment_common.dry_run:
                deployment_common.start_iteration()
                try:
                    ruleset_id = curated_details["id"]
                    category_id = categories_mapping[ruleset_id]
                    disable_curated(
                        chronicle_client,
                        category_id,
                        ruleset_id,
                        curated_details["precision"],
                    )
                except APIError as e:
                    errors = True
                    print(
                        f"Error disabling curated detection {tenant_name}/{curated_name}: {e!r}"
                    )
                deployment_common.end_iteration()

        if not deployment_common.dry_run:
            print(
                f"{tenant_name}: ",
                f"{len(tenant_deltas['missing'])} enabled,",
                f"{len(tenant_deltas['extra'])} disabled",
                flush=True,
            )
        else:
            print(
                f"{tenant_name}: ",
                f"{len(tenant_deltas['missing'])} to be enabled,",
                f"{len(tenant_deltas['extra'])} to be disabled",
                flush=True,
            )

    if args.deltas_file:
        with open(args.deltas_file, "w") as deltas_file:
            json.dump(deltas, deltas_file, indent=4)

    if errors:
        sys.exit(2)

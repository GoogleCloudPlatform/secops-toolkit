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
Create Missing Google SecOps Data Tables Referenced in YARA-L Rules.

This script parses local YARA-L rules for a tenant, identifies referenced
Data Tables (%table_name) that do not yet exist in the target Google SecOps tenant,
and creates them:
- Discovers required tables from rules in `rules/tenants/<tenant>/`.
- Lists existing remote Data Tables in Google SecOps.
- Identifies missing tables and resolves schemas/rows from shared or tenant definitions.
- Creates missing tables with proper column types (string, cidr, regex), keys, descriptions, and initial rows.
- Supports dry-run simulation (--dry-run) and automatic request throttling.
"""

import argparse
import os
import sys
from pathlib import Path

import argcomplete
import deployment_common
from compare_tables import get_required_tables
from deploy_tables import create_table
from secops.exceptions import APIError

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create missing Data Tables referenced in YARA-L rules"
    )
    deployment_common.add_standard_arguments(parser)
    parser.add_argument(
        "--tables-dir",
        default=os.getenv("DAC_TABLES_DIR", "tables"),
        help="The path to the local table definition YAML files, defaults to $DAC_TABLES_DIR or 'tables/'",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Only simulate deployment"
    )
    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    env, rules_path, all_tenants, selected_tenants_names = (
        deployment_common.process_standard_arguments(args)
    )

    tables_path = Path(args.tables_dir)
    if not tables_path.exists():
        print(
            f"Error: Local tables directory {args.tables_dir} does not exist,",
            "check the --tables-dir flag or the DAC_TABLES_DIR env variable",
        )
        sys.exit(1)

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

        required_tables = get_required_tables(rules_path, tables_path, tenant_name)
        required_table_names = {t for t in required_tables}
        if not required_tables:
            continue

        try:
            existing_table_names = {
                t["name"].split("/")[-1] for t in chronicle_client.list_data_tables()
            }
        except APIError as e:
            errors = True
            print(f"Error listing data tables for tenant {tenant_name}: {e!r}")
            continue

        missing_tables = required_table_names - existing_table_names

        if len(missing_tables) > deployment_common.THROTTLE_THRESHOLD:
            deployment_common.throttle_calls = True

        for table_name in sorted(missing_tables):
            if deployment_common.verbose:
                print(f"Creating missing table {table_name}")
            if not deployment_common.dry_run:
                deployment_common.start_iteration()
                try:
                    create_table(
                        chronicle_client,
                        table_name,
                        required_tables[table_name],
                    )
                except APIError as e:
                    errors = True
                    print(f"Error creating table {tenant_name}/{table_name}: {e!r}")
                deployment_common.end_iteration()

        print(
            f"{tenant_name}: ",
            f"{len(missing_tables)}",
            "created" if not deployment_common.dry_run else "to be created",
            flush=True,
        )

    if errors:
        sys.exit(2)

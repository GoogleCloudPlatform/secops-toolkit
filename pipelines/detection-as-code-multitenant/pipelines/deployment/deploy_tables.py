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
Data Tables Deployment and Synchronization Pipeline for Google SecOps.

This script deploys local Data Table schemas and row contents to Google SecOps (Chronicle)
for multi-tenant environments:
- Uses `compare_tables` to identify missing, changed, and extra tables.
- Creates missing Data Tables with structured column definitions (types, key columns, descriptions).
- Updates rows in existing Data Tables when differences are detected.
- Deletes extra tables from SecOps when explicitly requested (--delete-extras).
- Supports dry-run simulation (--dry-run), automatic request throttling, and JSON delta export (--deltas-file).
"""

import argparse
import contextlib
import json
import os
import sys
from collections import OrderedDict
from pathlib import Path

import argcomplete
import deployment_common
from compare_tables import (
    Deltas,
    Table,
    compare_tables,
)
from secops.chronicle.client import ChronicleClient
from secops.exceptions import APIError

SKIP_EXTRAS = True


def create_table(
    chronicle_client: ChronicleClient,
    table_name: str,
    table: Table,
):
    header = OrderedDict()
    column_options = {}
    for column in table["columns"]:
        header[column["name"]] = column["type"]
        if column["key"]:
            column_options[column["name"]] = {"keyColumn": True}

    chronicle_client.create_data_table(
        name=table_name,
        description=table["description"],
        header=header,
        column_options=column_options,
        rows=table["rows"],
    )


def update_table_rows(
    chronicle_client: ChronicleClient,
    table_name: str,
    table: Table,
):
    # suppress print() statements
    with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull):
        chronicle_client.replace_data_table_rows(
            name=table_name,
            rows=table["rows"],
        )


def delete_table(
    chronicle_client: ChronicleClient,
    table_name: str,
):
    chronicle_client.delete_data_table(name=table_name, force=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deploy local Data Tables to SecOps")
    deployment_common.add_standard_arguments(parser)
    parser.add_argument(
        "--tables-dir",
        default=os.getenv("DAC_TABLES_DIR", "tables"),
        help="The path to the local table definition YAML files, defaults to $DAC_TABLES_DIR or 'tables/'",
    )
    parser.add_argument(
        "--deltas-file",
        default=os.getenv("DAC_TABLES_DELTAS_FILE", ""),
        help="The path where to write a file with all the deltas found while comparing, defaults to $DAC_TABLES_DELTAS_FILE",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Only simulate deployment"
    )
    parser.add_argument(
        "--delete-extras",
        action="store_true",
        help="Delete extra tables from SecOps",
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

    if args.delete_extras:
        SKIP_EXTRAS = False

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

        tenant_deltas, repo_tables, _ = compare_tables(
            chronicle_client, rules_path, tables_path, tenant_name
        )
        deltas[tenant_name] = tenant_deltas

        if (
            len(tenant_deltas["missing"])
            + len(tenant_deltas["changed"])
            + len(tenant_deltas["extra"])
            > deployment_common.THROTTLE_THRESHOLD
        ):
            deployment_common.throttle_calls = True

        for table_name in tenant_deltas["missing"]:
            if deployment_common.verbose:
                print(f"Creating missing table {table_name}")
            if not deployment_common.dry_run:
                deployment_common.start_iteration()
                try:
                    create_table(
                        chronicle_client,
                        table_name,
                        repo_tables[table_name],
                    )
                except APIError as e:
                    errors = True
                    print(f"Error creating table {tenant_name}/{table_name}: {e!r}")
                deployment_common.end_iteration()

        for table_name in tenant_deltas["changed"]:
            if deployment_common.verbose:
                print(f"Updating changed table {table_name}")
            if not deployment_common.dry_run:
                deployment_common.start_iteration()
                try:
                    update_table_rows(
                        chronicle_client,
                        table_name,
                        repo_tables[table_name],
                    )
                except APIError as e:
                    errors = True
                    print(f"Error updating table {tenant_name}/{table_name}: {e!r}")
                deployment_common.end_iteration()

        for table_name in tenant_deltas["extra"]:
            if deployment_common.verbose:
                print(f"Deleting extra table {table_name}")
            if not deployment_common.dry_run and not SKIP_EXTRAS:
                deployment_common.start_iteration()
                try:
                    delete_table(chronicle_client, table_name)
                except APIError as e:
                    errors = True
                    print(f"Error deleting table {tenant_name}/{table_name}: {e!r}")
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

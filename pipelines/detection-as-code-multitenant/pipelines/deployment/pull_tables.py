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
Pull Google SecOps Data Tables to Local Git Repository.

This script synchronizes Data Tables from Google SecOps (Chronicle) tenants into
local configuration and data files in `tables/tenants/<tenant>/`:
- Uses `compare_tables` to identify discrepancies between local and remote table data.
- Removes local CSV and YAML files for tables that no longer exist in SecOps.
- Updates local tenant CSV files with current row data fetched from SecOps.
- Optionally exports extra tables and generated YAML schemas when --create-extras is enabled.
"""

import argparse
import csv
import os
import sys
from pathlib import Path

import argcomplete
import deployment_common
import yaml
from compare_tables import compare_tables
from secops.chronicle.data_table import DataTableColumnType

SKIP_EXTRAS = True


def get_repo_table_path(
    tables_path: Path, tenant: str, table_name: str, type="csv"
) -> Path:
    return tables_path / "tenants" / tenant / f"{table_name}.{type}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pull Data Tables from SecOps to the local repository"
    )
    deployment_common.add_standard_arguments(parser)
    parser.add_argument(
        "--tables-dir",
        default=os.getenv("DAC_TABLES_DIR", "tables"),
        help="The path to the local table definition YAML files, defaults to $DAC_TABLES_DIR or 'tables/'",
    )
    parser.add_argument(
        "--create-extras",
        action="store_true",
        help="Create extra tables from SecOps even if they are not used by any rule",
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

    if args.create_extras:
        SKIP_EXTRAS = False

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

        tenant_deltas, _, _ = compare_tables(
            chronicle_client, rules_path, tables_path, tenant_name
        )

        for table_name in tenant_deltas["missing"]:
            if deployment_common.verbose:
                print(f"Deleting missing table: {table_name}")
            table_file_csv = get_repo_table_path(
                tables_path, tenant_name, table_name, type="csv"
            )
            table_file_csv.unlink(missing_ok=True)
            table_file_yaml = get_repo_table_path(
                tables_path, tenant_name, table_name, type="yaml"
            )
            table_file_yaml.unlink(missing_ok=True)

        for table_name, secops_table_details in tenant_deltas["changed"].items():
            if deployment_common.verbose:
                print(f"Updating changed table: {table_name}")
            table_file = get_repo_table_path(tables_path, tenant_name, table_name)
            table_file.parent.mkdir(exist_ok=True)
            with open(table_file, "w") as f:
                csv.writer(f).writerows(secops_table_details["rows"])

        if not SKIP_EXTRAS:
            for table_name, secops_table_details in tenant_deltas["extra"].items():
                if deployment_common.verbose:
                    print(f"Creating extra table: {table_name}")

                if len(secops_table_details["columns"]) > 1:
                    columns = []
                    for column_definition in secops_table_details["columns"]:
                        column = column_definition["name"]
                        if column_definition["type"] != DataTableColumnType.STRING:
                            column += f"({column_definition['type'].value.lower()})"
                        if column_definition["key"]:
                            column += "*"
                        columns.append(column)
                    table_definition = {
                        "description": secops_table_details["description"],
                        "columns": columns,
                    }
                    table_definition_file = get_repo_table_path(
                        tables_path, tenant_name, table_name, type="yaml"
                    )
                    with open(table_definition_file, "w") as f:
                        yaml.safe_dump(table_definition, f)

                table_file = get_repo_table_path(tables_path, tenant_name, table_name)
                with open(table_file, "w") as f:
                    csv.writer(f).writerows(secops_table_details["rows"])

        print(
            f"{tenant_name}: ",
            f"{len(tenant_deltas['missing'])} removed,",
            f"{len(tenant_deltas['changed'])} updated,",
            f"{len(tenant_deltas['extra'])}",
            "created" if not SKIP_EXTRAS else "ignored",
            flush=True,
        )

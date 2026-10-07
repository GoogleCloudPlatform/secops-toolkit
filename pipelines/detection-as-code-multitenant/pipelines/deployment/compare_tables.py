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
Data Tables Comparison and Drift Detection for Google SecOps.

This script parses YARA-L rules to find referenced Data Tables (%table_name)
and compares local schema/row definitions against remote Data Tables in Google SecOps:
- Scans `rules/tenants/<tenant>/*.yaral` for `%table_name` references (including cidr/regex prefixes).
- Loads table schemas from `tables/tenants/<tenant>/<table_name>.yaml` or `tables/shared/<table_name>.yaml`.
- Loads row data from default schema values or tenant CSV overrides (`tables/tenants/<tenant>/<table_name>.csv`).
- Fetches remote Data Table schemas and rows from Google SecOps.
- Identifies missing, changed (row data differences), and extra tables.
- Displays unified CSV diffs when --debug is enabled.
- Outputs drift summary counts and optionally dumps deltas to JSON (--deltas-file).
"""

import argparse
import csv
import difflib
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import TypedDict

import argcomplete
import deployment_common
import yaml
from secops.chronicle.client import ChronicleClient
from secops.chronicle.data_table import DataTableColumnType
from secops.exceptions import APIError


class Column(TypedDict):
    name: str
    key: bool
    type: DataTableColumnType


class Table(TypedDict, total=False):
    description: str
    columns: list[Column]
    rows: list[list[str]]


class Deltas(TypedDict):
    missing: dict[str, Table]
    changed: dict[str, Table]
    extra: dict[str, Table]


# Regex to find data table usage in rules (%table_name)
DATATABLE_PATTERN = re.compile(r"(cidr|regex)?(?:^|\s)%([a-zA-Z]\w{0,254})")

definitions_cache: dict[str, Table] = {}


def get_required_tables(
    rules_path: Path, tables_path: Path, tenant: str
) -> dict[str, Table]:
    required_tables: dict[str, Table] = {}

    rules_dir_tenant = rules_path / "tenants" / tenant
    if not rules_dir_tenant.exists() or not rules_dir_tenant.is_dir():
        raise OSError(f"Directory not found for tenant '{tenant}': {rules_dir_tenant}")
    for rule_file in rules_dir_tenant.glob("*.yaral"):
        text = rule_file.read_text()
        matches = DATATABLE_PATTERN.findall(text)
        for m in matches:
            table_name = m[1]

            if table_name in required_tables:
                continue

            required_tables[table_name] = get_repo_table(
                tables_path,
                tenant,
                table_name,
                main_type=m[0] or "string",
            )

    return required_tables


def get_repo_table(
    tables_path: Path, tenant: str, table_name: str, main_type: str = "string"
) -> Table:
    table = load_table_definition(tables_path, tenant, table_name)

    if not table:
        if deployment_common.debug:
            print(
                f"Definition not found for table {table_name} in tenant {tenant}, using default"
            )
        table = {
            "description": "Ad-hoc table managed by the SOC",
            "columns": [
                {
                    "name": "main",
                    "key": True,
                    "type": DataTableColumnType(main_type.upper()),
                },
                {
                    "name": "comment",
                    "key": False,
                    "type": DataTableColumnType.STRING,
                },
            ],
            "rows": [],
        }

    rows_override = get_rows_override(tables_path, tenant, table_name)
    if rows_override is not None:
        table["rows"] = rows_override

    return table


def load_table_definition(
    tables_path: Path, tenant: str, table_name: str
) -> Table | None:
    if table_name in definitions_cache:
        return definitions_cache[table_name]

    tenant_path = tables_path / "tenants" / tenant / f"{table_name}.yaml"
    shared_path = tables_path / "shared" / f"{table_name}.yaml"
    if tenant_path.is_file():
        path = tenant_path
    elif shared_path.is_file():
        path = shared_path
    else:
        return None

    with open(path, "r") as f:
        definition = yaml.safe_load(f)

        columns: list[Column] = []
        for column in definition["columns"]:
            f = column.strip("*").split("(")
            column_name = f[0]
            column_type = f[1].strip(")") if len(f) > 1 else "string"
            columns.append(
                {
                    "name": column_name,
                    "key": column.endswith("*"),
                    "type": DataTableColumnType(column_type.upper()),
                }
            )
        num_columns = len(columns)

        raw_default_values = definition.get("default_values", [])
        default_values = []
        for row in raw_default_values:
            if isinstance(row, str):
                row_values = [row]
            elif isinstance(row, list):
                row_values = row
            else:
                row_values = []

            # Adjust row to match the number of columns
            if len(row_values) > num_columns:
                row_values = row_values[:num_columns]
            elif len(row_values) < num_columns:
                row_values.extend([""] * (num_columns - len(row_values)))

            default_values.append(row_values)

        table: Table = {
            "description": definition.get("description", ""),
            "columns": columns,
            # ordering is not guaranteed for data tables, sorting to allow comparison
            "rows": sorted(default_values),
        }

        definitions_cache[table_name] = table
        return table


def get_rows_override(
    tables_path: Path, tenant: str, table_name: str
) -> list[list[str]] | None:
    csv_path = tables_path / "tenants" / tenant / f"{table_name}.csv"
    if csv_path.is_file():
        if deployment_common.debug:
            print(f"Found override for table {table_name} in tenant {tenant}")
        with open(csv_path, "r") as f:
            return list(
                csv.reader(
                    # ordering is not guaranteed for data tables, sorting to allow comparison
                    sorted(
                        # skip empty rows
                        filter(None, f.readlines())
                    )
                )
            )
    return None


def fetch_tables_from_tenant(chronicle_client: ChronicleClient) -> dict[str, Table]:
    try:
        secops_tables_list = chronicle_client.list_data_tables()
    except APIError as e:
        print(f"Error listing data tables: {e!r}")
        raise

    secops_tables: dict[str, Table] = {}
    for table in secops_tables_list:
        table_name = table["name"].split("/")[-1]

        try:
            rows = [
                row["values"]
                for row in chronicle_client.list_data_table_rows(table_name)
                # skip empty rows
                if row["values"] and row["values"][0]
            ]
        except APIError as e:
            print(f"Error listing rows for table {table_name}: {e!r}")
            raise

        secops_tables[table_name] = {
            "description": table.get("description", ""),
            "columns": [
                {
                    "name": column["originalColumn"],
                    "key": column.get("keyColumn", False),
                    "type": DataTableColumnType(column["columnType"]),
                }
                for column in table["columnInfo"]
            ],
            # ordering is not guaranteed for data tables, sorting to allow comparison
            "rows": sorted(rows),
        }

    return secops_tables


def compare_tables(
    chronicle_client: ChronicleClient, rules_path: Path, tables_path: Path, tenant: str
):
    deltas: Deltas = {
        "missing": {},
        "changed": {},
        "extra": {},
    }

    repo_tables = get_required_tables(rules_path, tables_path, tenant)
    secops_tables = fetch_tables_from_tenant(chronicle_client)

    all_repo_table_names = set(repo_tables.keys())
    all_secops_table_names = set(secops_tables.keys())

    # Tables in repo but not in SecOps
    tables_missing_from_secops = all_repo_table_names - all_secops_table_names
    for table_name in sorted(tables_missing_from_secops):
        deltas["missing"][table_name] = {}
        if deployment_common.verbose:
            print(f"Missing in SecOps, present in repo: {table_name}")

    # Tables in both, check for differences
    tables_in_both = all_repo_table_names.intersection(all_secops_table_names)
    for table_name in sorted(tables_in_both):
        repo_table = repo_tables[table_name]
        secops_table = secops_tables[table_name]

        if repo_table["columns"] != secops_table["columns"]:
            print(f"Incompatible column definition for {table_name}, skipping")
            continue

        if repo_table["rows"] != secops_table["rows"]:
            deltas["changed"][table_name] = secops_table
            if deployment_common.verbose:
                print(f"Different between SecOps and repo: {table_name}")
            if deployment_common.debug:
                repo_rows = io.StringIO()
                secops_rows = io.StringIO()
                csv.writer(repo_rows).writerows(repo_table["rows"])
                csv.writer(secops_rows).writerows(secops_table["rows"])
                diff = difflib.unified_diff(
                    secops_rows.getvalue().splitlines(keepends=True),
                    repo_rows.getvalue().splitlines(keepends=True),
                    fromfile=f"{table_name} (SecOps)",
                    tofile=f"{table_name} (repository)",
                )
                sys.stdout.writelines(diff)

    # Tables in SecOps but not in repo
    tables_missing_from_repo = all_secops_table_names - all_repo_table_names
    for table_name in sorted(tables_missing_from_repo):
        secops_table = secops_tables[table_name]
        deltas["extra"][table_name] = secops_table
        if deployment_common.verbose:
            print(f"Extra in SecOps, not present in repo: {table_name}")
        if deployment_common.debug:
            csv.writer(sys.stdout).writerows(secops_table["rows"])

    return deltas, repo_tables, secops_tables


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare local Data Tables with SecOps"
    )
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

        tenant_deltas, _, _ = compare_tables(
            chronicle_client, rules_path, tables_path, tenant_name
        )
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

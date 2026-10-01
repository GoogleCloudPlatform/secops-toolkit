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
Convert Legacy Google SecOps Reference Lists to Modern Data Tables.

This migration utility facilitates the transition from legacy Chronicle Reference
Lists to structured Data Tables:
- Inspects YARA-L rules for required tables (%table_name) and discovers matching Reference Lists in SecOps.
- Maps Reference List syntax types (STRING, REGEX, CIDR) into DataTableColumnType definitions.
- Parses values and inline comments (e.g., `// comment`) into structured columns.
- Generates local CSV data files (`tables/tenants/<tenant>/<table_name>.csv`) populated with converted rows.
"""

import argparse
import csv
import difflib
import io
import os
import re
import sys
from pathlib import Path

import argcomplete
import deployment_common
from compare_tables import Table, get_required_tables
from pull_tables import get_repo_table_path
from secops.chronicle.client import ChronicleClient
from secops.chronicle.data_table import DataTableColumnType
from secops.chronicle.reference_list import ReferenceListView
from secops.exceptions import APIError

COMMENTS_PATTERN = re.compile(r"(.*\S)\s+//(.*)$")


def fetch_reflists_from_tenant(chronicle_client: ChronicleClient) -> dict[str, Table]:
    try:
        secops_reflists_list = chronicle_client.list_reference_lists(
            view=ReferenceListView.FULL
        )
    except APIError as e:
        print(f"Error listing reference lists: {e!r}")
        raise

    secops_reflists: dict[str, Table] = {}
    for reflist in secops_reflists_list:
        reflist_name = reflist["displayName"]

        match reflist["syntaxType"]:
            case "REFERENCE_LIST_SYNTAX_TYPE_REGEX":
                reflist_type = DataTableColumnType.REGEX
            case "REFERENCE_LIST_SYNTAX_TYPE_CIDR":
                reflist_type = DataTableColumnType.CIDR
            case _:
                reflist_type = DataTableColumnType.STRING

        rows = []
        for entry in reflist.get("entries", {}):
            row_main = entry.get("value", "").strip()
            if row_main and not row_main.startswith("//"):
                m = COMMENTS_PATTERN.search(row_main)
                if m:
                    row_main = rows.append([m.group(1), m.group(2)])
                else:
                    rows.append([row_main, ""])

        secops_reflists[reflist_name] = {
            "description": reflist.get(
                "description", "Ad-hoc table managed by the SOC"
            ),
            "columns": [
                {
                    "name": "main",
                    "key": True,
                    "type": reflist_type,
                },
                {
                    "name": "comment",
                    "key": False,
                    "type": DataTableColumnType.STRING,
                },
            ],
            "rows": sorted(rows),
        }

    return secops_reflists


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create Data Tables from existing Reference Lists referenced by YARA-L rules"
    )
    deployment_common.add_standard_arguments(parser)
    parser.add_argument(
        "--tables-dir",
        default=os.getenv("DAC_TABLES_DIR", "tables"),
        help="The path to the local table definition YAML files, defaults to $DAC_TABLES_DIR or 'tables/'",
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

        repo_tables = get_required_tables(rules_path, tables_path, tenant_name)
        secops_reflists = fetch_reflists_from_tenant(chronicle_client)

        pulled_count = 0
        for table_name, repo_table in sorted(repo_tables.items()):
            if table_name in secops_reflists:
                secops_reflist = secops_reflists[table_name]
                if repo_table["columns"] != secops_reflist["columns"]:
                    print(f"Incompatible column definition for {table_name}, skipping")
                    continue

                if repo_table["rows"] != secops_reflist["rows"]:
                    if deployment_common.verbose:
                        print(f"Different between SecOps and repo: {table_name}")
                    if deployment_common.debug:
                        repo_rows = io.StringIO()
                        secops_rows = io.StringIO()
                        csv.writer(repo_rows).writerows(repo_table["rows"])
                        csv.writer(secops_rows).writerows(secops_reflist["rows"])
                        diff = difflib.unified_diff(
                            secops_rows.getvalue().splitlines(keepends=True),
                            repo_rows.getvalue().splitlines(keepends=True),
                            fromfile=f"{table_name} (SecOps reference list)",
                            tofile=f"{table_name} (repository data table)",
                        )
                        sys.stdout.writelines(diff)

                    table_file = get_repo_table_path(
                        tables_path, tenant_name, table_name
                    )
                    table_file.parent.mkdir(exist_ok=True)
                    with open(table_file, "w") as f:
                        csv.writer(f).writerows(secops_reflist["rows"])
                    pulled_count += 1

        print(
            f"{tenant_name}: ",
            f"{pulled_count}",
            "converted",
            flush=True,
        )

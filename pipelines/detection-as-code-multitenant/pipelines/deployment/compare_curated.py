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
Google SecOps Curated Detection Rule Sets Comparison and Drift Detection.

This script compares local curated detection configurations (*.yaml) in `curated/tenants/<tenant>/`
against actively enabled Curated Rule Set deployments in Google SecOps (Chronicle) tenants.

Deltas identified:
- missing: Curated rule sets configured in the repository but disabled in SecOps.
- extra: Curated rule sets currently enabled in SecOps but not declared in the repository.

Features:
- Handles name normalization, category shortening, and precision level mapping
  (PRECISE vs BROAD).
- Compares enabled rule sets across specified tenants or lifecycle stages.
- Outputs human-readable delta counts and optionally exports full deltas to JSON (--deltas-file).
"""

import argparse
import json
import os
import string
import sys
from enum import StrEnum
from pathlib import Path
from typing import TypedDict

import argcomplete
import deployment_common
import yaml
from secops.chronicle.client import ChronicleClient
from secops.exceptions import APIError


class PrecisionType(StrEnum):
    """
    PrecisionType denotes the precision level of the RuleSet deployment
    """

    PRECISE = "precise"
    BROAD = "broad"


class RuleSet(TypedDict, total=False):
    id: str
    name: str
    precision: PrecisionType
    live: bool
    alerting: bool


class Deltas(TypedDict):
    missing: dict[str, RuleSet]
    extra: dict[str, RuleSet]


SANITIZE_CATEGORY_MAPPING = {
    ord(c): None
    for c in (string.punctuation + string.whitespace + string.ascii_lowercase)
}
SANITIZE_RULESET_MAPPING = {
    ord(c): None for c in (string.punctuation + string.whitespace)
}


def shorten_category(name: str) -> str:
    result = name.translate(SANITIZE_CATEGORY_MAPPING)
    if not result:
        raise ValueError(f"Error shortening category name <{name}>: no character left")
    return result


def sanitize_ruleset(name: str) -> str:
    return name.translate(SANITIZE_RULESET_MAPPING)


def fetch_curated_from_tenant(chronicle_client: ChronicleClient) -> dict[str, RuleSet]:
    try:
        secops_curated_categories = chronicle_client.list_curated_rule_set_categories(
            as_list=True,
        )
    except APIError as e:
        print(f"Error fetching curated detection categories: {e!r}")
        raise

    categories = {}
    for category in secops_curated_categories:
        categories[category["name"].split("/")[7]] = shorten_category(
            category["displayName"]
        )

    try:
        secops_curated_deployments = chronicle_client.list_curated_rule_set_deployments(
            only_enabled=True,
            as_list=True,
        )
    except APIError as e:
        print(f"Error fetching curated detection deployments: {e!r}")
        raise

    secops_active_curated: dict[str, RuleSet] = {}
    for curated in secops_curated_deployments:
        category_name = categories[curated["name"].split("/")[7]]
        ruleset_id = curated["name"].split("/")[9]
        name = curated["displayName"]
        precision = PrecisionType(curated["name"].split("/")[11])
        secops_active_curated[
            f"{shorten_category(category_name)}_{sanitize_ruleset(name)}_{precision.value}"
        ] = {
            "id": ruleset_id,
            "name": name,
            "precision": precision,
            "live": curated.get("enabled", False),
            "alerting": curated.get("alerting", False),
        }

    return secops_active_curated


def parse_curated_from_repo(curated_dir_tenant: Path) -> dict[str, RuleSet]:
    repo_curated: dict[str, RuleSet] = {}

    for p in curated_dir_tenant.glob("*.yaml"):
        precision = PrecisionType(p.stem.split("_")[2])
        with open(p, "r") as f:
            definition = yaml.safe_load(f)
            repo_curated[p.stem] = {
                "id": definition["id"],
                "name": definition["name"],
                "precision": precision,
                "live": True,
                "alerting": False,
            }

    return repo_curated


def compare_curated(chronicle_client: ChronicleClient, curated_path: Path, tenant: str):
    deltas: Deltas = {
        "missing": {},
        "extra": {},
    }

    curated_dir_tenant = curated_path / "tenants" / tenant
    if not curated_dir_tenant.exists() or not curated_dir_tenant.is_dir():
        raise OSError(
            f"Directory not found for tenant '{tenant}': {curated_dir_tenant}"
        )
    repo_curated = parse_curated_from_repo(curated_dir_tenant)
    secops_curated = fetch_curated_from_tenant(chronicle_client)

    all_repo_curated_names = set(repo_curated.keys())
    all_secops_curated_names = set(secops_curated.keys())

    # Curated in repo but not in SecOps
    curated_missing_from_secops = all_repo_curated_names - all_secops_curated_names
    for curated_name in sorted(curated_missing_from_secops):
        deltas["missing"][curated_name] = repo_curated[curated_name]
        if deployment_common.verbose:
            print(f"Missing in SecOps, present in repo: {curated_name}")

    # Curated in SecOps but not in repo
    curated_missing_from_repo = all_secops_curated_names - all_repo_curated_names
    for curated_name in sorted(curated_missing_from_repo):
        deltas["extra"][curated_name] = secops_curated[curated_name]
        if deployment_common.verbose:
            print(
                f"Extra in SecOps, not present in repo: {curated_name} ({secops_curated[curated_name]['id']})"
            )

    return deltas, repo_curated, secops_curated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare local curated detections with SecOps"
    )
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

        tenant_deltas, _, _ = compare_curated(
            chronicle_client, curated_path, tenant_name
        )
        print(
            f"{tenant_name}: ",
            f"{len(tenant_deltas['missing'])} missing,",
            f"{len(tenant_deltas['extra'])} extra",
            flush=True,
        )
        deltas[tenant_name] = tenant_deltas

    if args.deltas_file:
        with open(args.deltas_file, "w") as deltas_file:
            json.dump(deltas, deltas_file, indent=4)

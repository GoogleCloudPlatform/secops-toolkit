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
Pull Google SecOps Curated Detection Rule Sets to Local Git Repository.

This script synchronizes the active curated detection state from Google SecOps (Chronicle)
into local YAML definition files in `curated/tenants/<tenant>/`:
- Uses `compare_curated` to detect differences between local configs and remote SecOps deployments.
- Deletes local curated YAML files for rule sets that are disabled or removed in SecOps.
- Generates new YAML definition files (storing ruleset ID and display name) for curated rule sets
  enabled directly in SecOps.
- Supports reverse-syncing active curated detections when onboarding or auditing tenants.
"""

import argparse
import os
import sys
from pathlib import Path

import argcomplete
import deployment_common
import yaml
from compare_curated import compare_curated


def get_repo_curated_path(
    curated_path: Path, tenant: str, deployment_name: str
) -> Path:
    return curated_path / "tenants" / tenant / f"{deployment_name}.yaml"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pull curated detections from SecOps to the local repository"
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

        for deployment_name in tenant_deltas["missing"]:
            if deployment_common.verbose:
                print(f"Deleting missing curated detection: {deployment_name}")
            curated_file = get_repo_curated_path(
                curated_path, tenant_name, deployment_name
            )
            curated_file.unlink(missing_ok=True)

        for deployment_name, secops_curated_details in tenant_deltas["extra"].items():
            if deployment_common.verbose:
                print(f"Creating extra curated detection: {deployment_name}")
            curated_file = get_repo_curated_path(
                curated_path, tenant_name, deployment_name
            )
            with open(curated_file, "w") as f:
                definition = {
                    "id": secops_curated_details["id"],
                    "name": secops_curated_details["name"],
                }
                yaml.safe_dump(definition, f, sort_keys=False)

        print(
            f"{tenant_name}: ",
            f"{len(tenant_deltas['missing'])} removed,",
            f"{len(tenant_deltas['extra'])} created",
            flush=True,
        )

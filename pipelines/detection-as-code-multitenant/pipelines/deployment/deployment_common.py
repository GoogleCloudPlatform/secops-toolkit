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
"""
Common Utilities for Google SecOps Multi-Tenant CI/CD Deployment Pipelines.

This module provides foundational helpers used across comparison, synchronization,
and deployment scripts for detection-as-code management in Google SecOps (Chronicle):
- Google Cloud authentication and SecOps/Chronicle client session initialization,
  with support for service account impersonation.
- Standardized command-line argument parsing for target environments (--env),
  specific tenants (--tenant), tenant lifecycle stages (--stage: all, build, live),
  inventory file loading (--tenants-file), and rules directory resolution.
- Lifecycle stage filtering based on Git tags (-handover and -golive) to distinguish
  onboarding/build tenants from stabilized live tenants.
- Rate-limiting and request throttling mechanisms to ensure API call rates remain
  within Google SecOps API quota thresholds.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Iterable
from pathlib import Path

from secops import SecOpsClient
from secops.auth import RetryConfig
from secops.chronicle.client import ChronicleClient

REGION = "me-central1"
THROTTLE_ITERATION = 1.1
THROTTLE_THRESHOLD = 50
CHRONICLE_API_BASE = "https://chronicle.me-central1.rep.googleapis.com/v1beta/"
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/chronicle",
]


debug = False
dry_run = False
throttle_calls = False
verbose = False

_iteration_start: float = 0


def get_live_tenant_ids():
    """
    Runs 'git tag' to get all tags and filters for those ending in '-handover' or
    '-golive' (with a potential suffix).

    Returns:
        set: A set of unique tenant IDs extracted from the matching tags.
    """

    try:
        result = subprocess.run(
            ["git", "tag"], capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as e:
        print(e.returncode, e.stdout, e.stderr)
        raise

    all_tags = result.stdout.strip().split("\n")

    golive_pattern = re.compile(r"^(.+)-(handover|golive)")
    tenant_ids = set()

    for tag in all_tags:
        match = golive_pattern.match(tag)
        if match:
            tenant_ids.add(match.group(1))

    return tenant_ids


def get_build_tenant_ids(all_tenants: Iterable[str]):
    return all_tenants - get_live_tenant_ids()


def get_rule_id_from_location(location: str):
    return location.split("/")[-1]


def create_chronicle_client(
    tenant_details: dict[str, str], service_account=""
) -> ChronicleClient:
    secops_client = SecOpsClient(
        impersonate_service_account=service_account if service_account else None,
        retry_config=RetryConfig(backoff_factor=3, total=3),
    )
    chronicle_client = secops_client.chronicle(
        customer_id=tenant_details["customerId"],
        project_id=tenant_details["gcpProject"],
        region=REGION,
    )
    return chronicle_client


def add_standard_arguments(
    parser: argparse.ArgumentParser, affects_tenants=True, include_rules_dir=True
):
    parser.add_argument(
        "-e",
        "--env",
        default="prod",
        choices=["dev", "prod"],
        help="The target environment",
    )
    if affects_tenants:
        parser.add_argument(
            "-p",
            "--tenant",
            action="append",
            help="The code of the tenant to process, can be set multiple times (required unless you pass --stage)",
        )
        parser.add_argument(
            "-s",
            "--stage",
            choices=["all", "build", "live"],
            help="Only process tenants in a given stage",
        )
    parser.add_argument(
        "-t",
        "--tenants-file",
        default=os.getenv("DAC_TENANTS_FILE", "tenants.json"),
        help="The path to the JSON file with the tenants details, defaults to $DAC_TENANTS_FILE",
    )
    if include_rules_dir:
        parser.add_argument(
            "--rules-dir",
            default=os.getenv("DAC_RULES_DIR", "rules"),
            help="The path to the local rule files, defaults to $DAC_RULES_DIR or 'rules/' if missing",
        )
    parser.add_argument(
        "--impersonate-sa",
        default=os.getenv("DAC_IMPERSONATE_SA", ""),
        help="If present, impersonate this service account while calling Chronicle APIs, defaults to $DAC_IMPERSONATE_SA",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable very verbose output (list actions in detail and show content), implies -v",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output (list actions in detail)",
    )


def process_standard_arguments(
    args: argparse.Namespace, affects_tenants=True, include_rules_dir=True
) -> tuple[str, Path, dict[str, dict[str, dict[str, str]]], list[str]]:
    env = args.env

    if affects_tenants and not args.tenant and not args.stage:
        print("Error: No tenant specified")
        sys.exit(1)

    if not os.path.exists(args.tenants_file):
        print(
            f"Error: Tenants file {args.tenants_file} does not exist,",
            "check the --tenants-file flag",
        )
        sys.exit(1)

    if include_rules_dir:
        rules_path = Path(args.rules_dir)
        if not rules_path.exists():
            print(
                f"Error: Local rules directory {args.rules_dir} does not exist,",
                "check the --rules-dir flag or the DAC_RULES_DIR env variable",
            )
            sys.exit(1)
    else:
        rules_path = Path("rules")

    global debug
    global verbose
    if args.debug:
        debug = True
        verbose = True
    if args.verbose:
        verbose = True

    if "dry_run" in args and args.dry_run:
        global dry_run
        dry_run = True

    with open(args.tenants_file, "r") as tenants_file:
        all_tenants = json.load(tenants_file)

    if affects_tenants:
        if args.stage:
            all_tenants_names = all_tenants[env].keys()
            match args.stage:
                case "all":
                    selected_tenants_names = list(all_tenants_names)
                case "build":
                    selected_tenants_names = get_build_tenant_ids(all_tenants_names)
                case "live":
                    selected_tenants_names = get_live_tenant_ids()
            if "primary" in selected_tenants_names:
                selected_tenants_names.remove("primary")
        else:
            selected_tenants_names = args.tenant
        if len(selected_tenants_names) == 0:
            print("Error: No tenant found")
            sys.exit(1)
    else:
        selected_tenants_names = []

    return env, rules_path, all_tenants, selected_tenants_names


def start_iteration():
    global _iteration_start
    _iteration_start = time.monotonic()


def end_iteration():
    iteration_duration = time.monotonic() - _iteration_start
    if throttle_calls and iteration_duration < THROTTLE_ITERATION:
        time.sleep(THROTTLE_ITERATION - iteration_duration)

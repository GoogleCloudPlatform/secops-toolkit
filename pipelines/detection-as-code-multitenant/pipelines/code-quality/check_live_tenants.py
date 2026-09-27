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
"""
Code Quality Check: Live Tenant Rule Decoupling Validator.

This script checks rule isolation for production tenants in Google SecOps.
During the onboarding ('build') stage, tenants may symlink to shared YARA-L rules
in `rules/shared/`. Once a tenant transitions to 'live' status (indicated by a
Git tag ending in '-handover' or '-golive'), organizations may choose to decouple
rules into independent standalone files to prevent unintentional upstream changes
from affecting live environments.

This check is OPTIONAL and controlled via the `DAC_ENFORCE_LIVE_DECOUPLING` environment
variable or the `--enforce` CLI flag. When not enabled, the check is skipped.

Checks performed (when enabled):
- Identifies live tenants via Git tags ending in '-handover' or '-golive'.
- Scans `rules/tenants/<tenant_id>/` for any symbolic links (*.yaral).
- Exits with return code 3 if symbolic links are detected in live tenant configurations.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


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


def check_live(enforce: bool = False):
    if not enforce:
        print(
            "Live tenant rule decoupling check skipped "
            "(set DAC_ENFORCE_LIVE_DECOUPLING=true or pass --enforce to enable)."
        )
        return

    rules_path = Path("rules")

    issues_count = 0

    for tenant_id in sorted(get_live_tenant_ids()):
        tenant_dir = rules_path / "tenants" / tenant_id
        if tenant_dir.is_dir():
            for yaral_file in tenant_dir.glob("*.yaral"):
                if yaral_file.is_symlink():
                    print(
                        f"Symlink in tenant not in BUILD phase: {tenant_id}/{yaral_file.name}"
                    )
                    issues_count += 1

    if issues_count == 0:
        print("All live tenants have no symlink")
    else:
        print(f"Found {issues_count} issues")
        sys.exit(3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check that live tenants do not contain symlinked YARA-L rules"
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        default=os.getenv("DAC_ENFORCE_LIVE_DECOUPLING", "").strip().lower() == "true",
        help="Enforce rule decoupling for live tenants (defaults to $DAC_ENFORCE_LIVE_DECOUPLING)",
    )
    args = parser.parse_args()
    check_live(enforce=args.enforce)

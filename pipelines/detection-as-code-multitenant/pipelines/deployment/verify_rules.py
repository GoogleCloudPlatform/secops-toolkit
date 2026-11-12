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
Verify YARA-L Rules and Allowed Schedules via Google SecOps `verifyRuleText`.

This script validates each tenant's YARA-L rules (`*.yaral`) and companion YAML
deployment configurations (`*.yaml`) against Google SecOps `v1alpha`
`instances:verifyRuleText`:
- Validates YAML configuration schemas (`run_frequency`, `schedule_customizations`).
- Calls `verifyRuleText` to verify YARA-L syntax and compiler diagnostics.
- Checks local `tables/` definitions when a referenced Data Table has not yet been
  deployed remotely.
- Cross-checks configured `run_frequency` against `allowedRunFrequencies` returned
  by `verifyRuleText` (emitting warnings for legacy coerced frequencies by default,
  or failing with exit code 5 when `--strict` is passed).
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

import argcomplete
import deployment_common
from secops.chronicle.client import ChronicleClient
from secops.exceptions import APIError


def discover_local_tables(tables_path: Path, tenant: str) -> set[str]:
    """Return the set of Data Table names defined locally in shared/ or tenants/<tenant>/."""
    names: set[str] = set()
    shared_dir = tables_path / "shared"
    if shared_dir.is_dir():
        names.update(p.stem for p in shared_dir.glob("*.yaml"))
    tenant_dir = tables_path / "tenants" / tenant
    if tenant_dir.is_dir():
        names.update(p.stem for p in tenant_dir.glob("*.yaml"))
        names.update(p.stem for p in tenant_dir.glob("*.csv"))
    return names


def check_allowed_schedule(
    tenant: str,
    rule_name: str,
    configured_frequency: str | None,
    allowed_frequencies: list[str],
    *,
    strict: bool = False,
) -> None:
    """Validate configured run_frequency against verifyRuleText allowedRunFrequencies."""
    if not configured_frequency or not allowed_frequencies:
        return
    if configured_frequency in allowed_frequencies:
        return

    if configured_frequency in deployment_common.LEGACY_RUN_FREQUENCIES:
        msg = (
            f"Warning [{tenant}/{rule_name}]: run_frequency={configured_frequency!r} is not in "
            f"allowedRunFrequencies={allowed_frequencies} and will be coerced by Google SecOps."
        )
        if strict:
            raise ValueError(msg)
        print(msg)
        return

    raise ValueError(
        f"run_frequency={configured_frequency!r} is not allowed for rule '{rule_name}'. "
        f"Allowed frequencies: {allowed_frequencies}."
    )


def verify_tenant_rules(
    chronicle_client: ChronicleClient,
    rules_path: Path,
    tables_path: Path,
    tenant: str,
    *,
    strict: bool = False,
) -> tuple[int, int]:
    """Verify all rules for a tenant. Returns (verified_count, error_count)."""
    tenant_dir = rules_path / "tenants" / tenant
    if not tenant_dir.is_dir():
        raise OSError(f"Directory not found for tenant '{tenant}': {tenant_dir}")

    local_tables = discover_local_tables(tables_path, tenant)
    verified = 0
    errors = 0

    for yaral_file in sorted(tenant_dir.glob("*.yaral")):
        rule_name = yaral_file.stem
        try:
            rule_text = yaral_file.read_text(encoding="utf-8")
            repo_cfg: dict[str, Any] = deployment_common.load_repo_rule_config(
                rules_path, tenant, rule_name
            )
            warnings = deployment_common.validate_rule_config_dict(
                rule_name, repo_cfg, strict=strict
            )
            for w in warnings:
                print(f"Warning [{tenant}/{rule_name}]: {w}")

            response = deployment_common.verify_rule_text_v1alpha(
                chronicle_client, rule_text
            )
            diagnostics = response.get("compilationDiagnostics") or []
            for diag in diagnostics:
                if diag.get("severity") == "WARNING" and diag.get("message"):
                    print(f"Compiler warning [{tenant}/{rule_name}]: {diag['message']}")

            allowed_frequencies = response.get("allowedRunFrequencies") or []
            configured_frequency = repo_cfg.get("run_frequency")

            if not response.get("success", False):
                error_msgs = [
                    d.get("message", "")
                    for d in diagnostics
                    if d.get("severity") in (None, "ERROR", "SEVERITY_UNSPECIFIED")
                    and d.get("message")
                ]
                err_msg = error_msgs[0] if error_msgs else "Unknown compilation error"
                if "Could not find Data Table" in err_msg:
                    match = re.search(r"Data Table Name: (.*?)(?:\n|$)", err_msg)
                    table_name = match.group(1).strip() if match else ""
                    if table_name and table_name in local_tables:
                        if deployment_common.verbose:
                            print(
                                f"{tenant}/{rule_name}: verified (local Data Table '{table_name}')"
                            )
                    else:
                        raise ValueError(
                            f"Missing Data Table '{table_name or err_msg}'"
                        )
                else:
                    raise ValueError(err_msg)

            check_allowed_schedule(
                tenant,
                rule_name,
                configured_frequency,
                allowed_frequencies,
                strict=strict,
            )
            verified += 1
            if deployment_common.verbose:
                print(
                    f"{tenant}/{rule_name}: OK (allowedRunFrequencies={allowed_frequencies})"
                )
        except (OSError, ValueError, TypeError, APIError) as e:
            print(f"Error [{tenant}/{rule_name}]: {e}")
            errors += 1

    return verified, errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Verify tenant YARA-L rules and YAML schedules against Chronicle verifyRuleText"
    )
    deployment_common.add_standard_arguments(parser)
    parser.add_argument(
        "--tables-dir",
        default=os.getenv("DAC_TABLES_DIR", "tables"),
        help="Path to local Data Table definitions, defaults to $DAC_TABLES_DIR or 'tables/'",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail verification if legacy/deprecated run_frequency values are configured",
    )
    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    env, rules_path, all_tenants, selected_tenants_names = (
        deployment_common.process_standard_arguments(args)
    )
    tables_path = Path(args.tables_dir)

    total_errors = 0
    for tenant_name in sorted(selected_tenants_names):
        if (
            not all_tenants
            or env not in all_tenants
            or tenant_name not in all_tenants[env]
        ):
            print(
                f"Error: Tenant info not found for tenant {tenant_name} in environment {env}"
            )
            sys.exit(1)

        tenant_details = all_tenants[env][tenant_name]
        chronicle_client = deployment_common.create_chronicle_client(
            tenant_details, args.impersonate_sa
        )
        verified_count, error_count = verify_tenant_rules(
            chronicle_client,
            rules_path,
            tables_path,
            tenant_name,
            strict=args.strict,
        )
        print(
            f"{tenant_name}: {verified_count} verified, {error_count} failed",
            flush=True,
        )
        total_errors += error_count

    if total_errors > 0:
        sys.exit(5)

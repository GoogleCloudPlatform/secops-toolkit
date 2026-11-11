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
Code Quality Check: YARA-L Companion YAML Deployment Configuration Validator.

This script validates all per-rule YAML deployment configuration files (`*.yaml`)
under `rules/shared/` and `rules/tenants/` offline without requiring GCP credentials:
- Ensures every `<RuleName>.yaml` has a corresponding `<RuleName>.yaral` in the
  same directory.
- Validates `enabled`, `alerting`, `archived`, `run_frequency` (including
  `LIVE_CUSTOMIZABLE` and `HOURLY_CUSTOMIZABLE`), `scope`, and `schedule_customizations`
  (`ensure_enrichment_completeness`, `late_arriving_data_adjustment`).
- Emits warnings for deprecated legacy schedules (`HOURLY`), or exits with error
  code 5 when `--strict` (or `DAC_STRICT_RULE_CONFIGS=true`) is enabled.
"""

import argparse
import os
import sys
from pathlib import Path

import yaml

# Allow importing shared validation logic from pipelines/deployment
_DEPLOYMENT_DIR = Path(__file__).resolve().parent.parent / "deployment"
if str(_DEPLOYMENT_DIR) not in sys.path:
    sys.path.insert(0, str(_DEPLOYMENT_DIR))

import deployment_common


def check_rule_configs(rules_dir: Path = Path("rules"), *, strict: bool = False) -> int:
    """Validate all rule YAML sidecars in rules_dir. Returns number of errors."""
    if not rules_dir.is_dir():
        print(f"Rules directory '{rules_dir}' not found")
        return 1

    error_count = 0
    checked_count = 0

    for yaml_path in sorted(rules_dir.rglob("*.yaml")):
        # Skip symlinks whose targets will be validated at their canonical location,
        # except still verify a matching .yaral exists alongside the symlink.
        yaral_companion = yaml_path.with_suffix(".yaral")
        if not yaral_companion.exists():
            print(
                f"Orphan rule config {yaml_path}: matching '{yaral_companion.name}' not found"
            )
            error_count += 1
            continue

        if yaml_path.is_symlink():
            continue

        checked_count += 1
        rule_name = yaml_path.stem
        try:
            raw_text = yaml_path.read_text(encoding="utf-8")
            content = yaml.safe_load(raw_text)
            effective_cfg = {} if content is None else content
            warnings = deployment_common.validate_rule_config_dict(
                rule_name, effective_cfg, strict=strict
            )
            for w in warnings:
                print(f"Warning in {yaml_path}: {w}")
        except (OSError, yaml.YAMLError, ValueError, TypeError) as e:
            print(f"Invalid config in {yaml_path}: {e}")
            error_count += 1

    if error_count == 0:
        print(f"All {checked_count} rule configuration YAML files are valid")
    else:
        print(f"Found {error_count} rule configuration issues")
    return error_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate companion YAML rule deployment configuration files"
    )
    parser.add_argument(
        "--rules-dir",
        default=os.getenv("DAC_RULES_DIR", "rules"),
        help="Path to local rules directory (defaults to $DAC_RULES_DIR or 'rules')",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=os.getenv("DAC_STRICT_RULE_CONFIGS", "").strip().lower() == "true",
        help="Treat deprecated schedule warnings as errors (defaults to $DAC_STRICT_RULE_CONFIGS)",
    )
    args = parser.parse_args()
    issues = check_rule_configs(Path(args.rules_dir), strict=args.strict)
    if issues > 0:
        sys.exit(5)

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
verification, and deployment scripts for detection-as-code management in Google SecOps:
- Google Cloud authentication and SecOps/Chronicle client session initialization,
  with support for service account impersonation.
- Standardized command-line argument parsing for target environments (--env),
  specific tenants (--tenant), tenant lifecycle stages (--stage: all, build, live),
  inventory file loading (--tenants-file), and rules directory resolution.
- Per-rule YAML deployment configuration loading (`<RuleName>.yaml`), validation,
  and Chronicle v1 `RuleDeployment` / v1alpha `verifyRuleText` API helpers supporting
  `LIVE_CUSTOMIZABLE`, `HOURLY_CUSTOMIZABLE`, and `scheduleCustomizations`.
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
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml
from secops import SecOpsClient
from secops.auth import RetryConfig
from secops.chronicle.client import ChronicleClient
from secops.chronicle.models import APIVersion
from secops.chronicle.utils.request_utils import (
    chronicle_paginated_request,
    chronicle_request,
)
from secops.exceptions import APIError, SecOpsError

REGION = "me-central1"
THROTTLE_ITERATION = 1.1
THROTTLE_THRESHOLD = 50
CHRONICLE_API_BASE = "https://chronicle.me-central1.rep.googleapis.com/v1beta/"
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/chronicle",
]

LEGACY_RUN_FREQUENCIES = frozenset({"LIVE", "HOURLY", "DAILY"})
CUSTOMIZABLE_RUN_FREQUENCIES = frozenset({"LIVE_CUSTOMIZABLE", "HOURLY_CUSTOMIZABLE"})
VALID_RUN_FREQUENCIES = LEGACY_RUN_FREQUENCIES | CUSTOMIZABLE_RUN_FREQUENCIES
ALLOWED_RULE_CONFIG_KEYS = frozenset(
    {
        "enabled",
        "alerting",
        "archived",
        "run_frequency",
        "schedule_customizations",
        "scope",
        "tags",
    }
)
ALLOWED_SCHEDULE_CUSTOMIZATION_KEYS = frozenset(
    {"ensure_enrichment_completeness", "late_arriving_data_adjustment"}
)
DURATION_PATTERN = re.compile(r"^\d+(\.\d{1,9})?s$")
CUSTOM_TAG_ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,98}$")
GOOGLE_TAG_ID_PATTERN = re.compile(r"^google\.[a-zA-Z0-9][a-zA-Z0-9._-]*$")
FULL_TAG_RESOURCE_PATTERN = re.compile(
    r"^projects/[^/]+/locations/[^/]+/instances/[^/]+/tags/(.+)$"
)

YAML_BOILERPLATE_HEADER = """\
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
    return set(all_tenants) - get_live_tenant_ids()


def get_rule_id_from_location(location: str) -> str:
    """Extract rule ID (ru_...) from a Rule or RuleDeployment resource name."""
    if not location:
        return ""
    return location.removesuffix("/deployment").split("/")[-1]


def extract_scope_id(scope: str | None) -> str | None:
    """Normalize a DataAccessScope resource name or short ID into its short ID."""
    if not scope:
        return None
    return scope.split("/")[-1]


def format_scope_resource(
    project_id: str, region: str, customer_id: str, scope: str | None
) -> str | None:
    """Format a short scope ID or full scope path into a full Chronicle resource path."""
    if not scope:
        return None
    if scope.startswith("projects/"):
        return scope
    return (
        f"projects/{project_id}/locations/{region}/instances/{customer_id}"
        f"/dataAccessScopes/{scope}"
    )


def extract_tag_id(tag: str) -> str:
    """Extract short tag ID from a short tag ID or full Chronicle Tag resource name."""
    cleaned = tag.strip()
    match = FULL_TAG_RESOURCE_PATTERN.match(cleaned)
    if match:
        return match.group(1)
    return cleaned


def is_google_tag_id(tag_id: str) -> bool:
    """Return True if tag_id uses the Google-managed `google.*` namespace."""
    return bool(GOOGLE_TAG_ID_PATTERN.match(tag_id))


def is_valid_tag_identifier(tag: str) -> bool:
    """Return True if tag is a valid custom tag ID, `google.*` tag ID, or full resource path."""
    if not isinstance(tag, str) or not tag.strip() or tag != tag.strip():
        return False
    if "/" in tag:
        match = FULL_TAG_RESOURCE_PATTERN.match(tag)
        if not match:
            return False
        tag_id = match.group(1)
    else:
        tag_id = tag
    return bool(
        CUSTOM_TAG_ID_PATTERN.match(tag_id) or GOOGLE_TAG_ID_PATTERN.match(tag_id)
    )


def canonical_tag_key(tag: str) -> str:
    """Return canonical comparison key (case-insensitive for `google.*`, exact for custom)."""
    tag_id = extract_tag_id(tag)
    if tag_id.lower().startswith("google."):
        return tag_id.lower()
    return tag_id


def format_tag_resource(
    project_id: str, region: str, customer_id: str, tag: str
) -> str:
    """Format a short tag ID or full Tag path into a full Chronicle Tag resource name."""
    cleaned = tag.strip()
    if FULL_TAG_RESOURCE_PATTERN.match(cleaned):
        return cleaned
    return (
        f"projects/{project_id}/locations/{region}/instances/{customer_id}"
        f"/tags/{extract_tag_id(cleaned)}"
    )


def extract_rule_text_tags(rule_dict: Mapping[str, Any]) -> list[str]:
    """Return inline YARA-L `meta` tags (`ruleTextTags`) as normalized short tag IDs."""
    rule_text_tags = rule_dict.get("ruleTextTags") or []
    result: list[str] = []
    seen: set[str] = set()
    for raw_tag in rule_text_tags:
        if not isinstance(raw_tag, str) or not raw_tag.strip():
            continue
        key = canonical_tag_key(raw_tag)
        if key in seen:
            continue
        seen.add(key)
        result.append(extract_tag_id(raw_tag))
    return result


def filter_out_rule_text_tags(
    desired_tags: Sequence[str], rule_text_tags: Sequence[str]
) -> list[str]:
    """Exclude tags already present in `ruleTextTags` (YARA-L `meta`) from desired API tags."""
    if not rule_text_tags:
        return list(desired_tags)
    text_keys = {
        canonical_tag_key(t) for t in rule_text_tags if isinstance(t, str) and t.strip()
    }
    return [t for t in desired_tags if canonical_tag_key(t) not in text_keys]


def extract_api_rule_tags(rule_dict: Mapping[str, Any]) -> list[str]:
    """Return API-applied rule tags (`tags` minus `ruleTextTags`) as short tag IDs."""
    all_tags = rule_dict.get("tags") or []
    rule_text_tags = rule_dict.get("ruleTextTags") or []
    text_keys = {
        canonical_tag_key(t) for t in rule_text_tags if isinstance(t, str) and t.strip()
    }

    api_tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in all_tags:
        if not isinstance(raw_tag, str) or not raw_tag.strip():
            continue
        key = canonical_tag_key(raw_tag)
        if key in text_keys or key in seen:
            continue
        seen.add(key)
        api_tags.append(extract_tag_id(raw_tag))
    return api_tags


def tags_equal(desired_tags: Iterable[str], remote_api_tags: Iterable[str]) -> bool:
    """Return True if desired and remote API tag iterables represent the same tag set."""
    return {canonical_tag_key(t) for t in desired_tags} == {
        canonical_tag_key(t) for t in remote_api_tags
    }


def schedule_customizations_api_to_yaml(
    api_customizations: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Convert API camelCase scheduleCustomizations into YAML snake_case."""
    if not isinstance(api_customizations, dict) or not api_customizations:
        return None

    result: dict[str, Any] = {}
    if api_customizations.get("ensureEnrichmentCompleteness") is not None:
        result["ensure_enrichment_completeness"] = bool(
            api_customizations["ensureEnrichmentCompleteness"]
        )
    if api_customizations.get("lateArrivingDataAdjustment"):
        result["late_arriving_data_adjustment"] = str(
            api_customizations["lateArrivingDataAdjustment"]
        )
    return result or None


def _normalize_duration_seconds(value: str) -> str | None:
    """Normalize a duration string in seconds to canonical Protobuf JSON format, or None if 0s."""
    raw = value.strip()
    if not DURATION_PATTERN.match(raw):
        return raw
    num_str = raw[:-1]
    if "." in num_str:
        int_part, frac_part = num_str.split(".", 1)
        frac_part = frac_part.rstrip("0")
        int_val = int(int_part)
        if int_val == 0 and not frac_part:
            return None
        return f"{int_val}.{frac_part}s" if frac_part else f"{int_val}s"
    int_val = int(num_str)
    return None if int_val == 0 else f"{int_val}s"


def normalize_schedule_customizations(
    customizations: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    Canonicalize schedule_customizations for drift comparison against Chronicle v1.

    Chronicle v1 uses Protobuf3 JSON serialization, omitting default values such as
    `ensureEnrichmentCompleteness: false` and zero-duration adjustments (`0s`).
    """
    if not isinstance(customizations, dict) or not customizations:
        return None

    result: dict[str, Any] = {}
    if customizations.get("ensure_enrichment_completeness") is True:
        result["ensure_enrichment_completeness"] = True

    late_adj = customizations.get("late_arriving_data_adjustment")
    if isinstance(late_adj, str) and late_adj.strip():
        normalized_dur = _normalize_duration_seconds(late_adj)
        if normalized_dur is not None:
            result["late_arriving_data_adjustment"] = normalized_dur

    return result or None


def schedule_customizations_yaml_to_api(
    yaml_customizations: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Convert YAML snake_case schedule_customizations into API camelCase."""
    if not isinstance(yaml_customizations, dict) or not yaml_customizations:
        return None

    result: dict[str, Any] = {}
    if yaml_customizations.get("ensure_enrichment_completeness") is not None:
        result["ensureEnrichmentCompleteness"] = bool(
            yaml_customizations["ensure_enrichment_completeness"]
        )
    if yaml_customizations.get("late_arriving_data_adjustment"):
        result["lateArrivingDataAdjustment"] = str(
            yaml_customizations["late_arriving_data_adjustment"]
        )
    return result or None


def validate_rule_config_dict(
    rule_name: str, rule_cfg: Any, *, strict: bool = False
) -> list[str]:
    """
    Validate a rule's YAML deployment configuration dictionary.

    Returns:
        List of warning messages emitted during validation.

    Raises:
        TypeError: If rule_cfg is not a dict or None.
        ValueError: If configuration is invalid (or has warnings when strict=True).
    """
    if rule_cfg is None:
        return []
    if not isinstance(rule_cfg, dict):
        raise TypeError(
            f"Rule '{rule_name}': configuration must be a YAML mapping, got {type(rule_cfg).__name__}."
        )

    warnings: list[str] = []

    unknown_keys = set(rule_cfg.keys()) - ALLOWED_RULE_CONFIG_KEYS
    if unknown_keys:
        raise ValueError(
            f"Rule '{rule_name}': unknown configuration keys {sorted(unknown_keys)}. "
            f"Allowed keys: {sorted(ALLOWED_RULE_CONFIG_KEYS)}."
        )

    for bool_key in ("enabled", "alerting", "archived"):
        if bool_key in rule_cfg and not isinstance(rule_cfg[bool_key], bool):
            raise ValueError(f"Rule '{rule_name}': '{bool_key}' must be a boolean.")

    if rule_cfg.get("archived", False) and rule_cfg.get("enabled", False):
        raise ValueError(
            f"Rule '{rule_name}': 'archived: true' requires 'enabled: false'."
        )

    run_frequency = rule_cfg.get("run_frequency")
    if run_frequency is not None:
        if (
            not isinstance(run_frequency, str)
            or run_frequency not in VALID_RUN_FREQUENCIES
        ):
            raise ValueError(
                f"Rule '{rule_name}': unsupported run_frequency {run_frequency!r}. "
                f"Must be one of: {sorted(VALID_RUN_FREQUENCIES)}."
            )
        if run_frequency == "HOURLY":
            msg = (
                f"Rule '{rule_name}' uses deprecated run_frequency 'HOURLY'. "
                "Prefer 'HOURLY_CUSTOMIZABLE' (multi-event) or 'LIVE' (single-event)."
            )
            if strict:
                raise ValueError(msg)
            warnings.append(msg)

    if (
        "scope" in rule_cfg
        and rule_cfg["scope"] is not None
        and (not isinstance(rule_cfg["scope"], str) or not rule_cfg["scope"].strip())
    ):
        raise ValueError(
            f"Rule '{rule_name}': 'scope' must be a non-empty string when specified."
        )

    schedule_customizations = rule_cfg.get("schedule_customizations")
    if schedule_customizations is not None:
        if not isinstance(schedule_customizations, dict):
            raise TypeError(
                f"Rule '{rule_name}': 'schedule_customizations' must be a YAML mapping."
            )
        if run_frequency not in CUSTOMIZABLE_RUN_FREQUENCIES:
            raise ValueError(
                f"Rule '{rule_name}': 'schedule_customizations' is only valid when "
                f"'run_frequency' is in {sorted(CUSTOMIZABLE_RUN_FREQUENCIES)} "
                f"(got {run_frequency!r})."
            )
        unknown_sc_keys = (
            set(schedule_customizations.keys()) - ALLOWED_SCHEDULE_CUSTOMIZATION_KEYS
        )
        if unknown_sc_keys:
            raise ValueError(
                f"Rule '{rule_name}': unknown schedule_customizations keys "
                f"{sorted(unknown_sc_keys)}."
            )
        enrichment = schedule_customizations.get("ensure_enrichment_completeness")
        if enrichment is not None and not isinstance(enrichment, bool):
            raise ValueError(
                f"Rule '{rule_name}': 'ensure_enrichment_completeness' must be a boolean."
            )
        late_adj = schedule_customizations.get("late_arriving_data_adjustment")
        if late_adj is not None and (
            not isinstance(late_adj, str) or not DURATION_PATTERN.match(late_adj)
        ):
            raise ValueError(
                f"Rule '{rule_name}': 'late_arriving_data_adjustment' must be a duration "
                f"in seconds ending with 's' (e.g., '300s'), got {late_adj!r}."
            )

    tags = rule_cfg.get("tags")
    if tags is not None:
        if not isinstance(tags, list):
            raise TypeError(
                f"Rule '{rule_name}': 'tags' must be a YAML list of strings."
            )
        seen_tag_keys: set[str] = set()
        for raw_tag in tags:
            if not isinstance(raw_tag, str):
                raise TypeError(
                    f"Rule '{rule_name}': every entry in 'tags' must be a string, "
                    f"got {type(raw_tag).__name__}."
                )
            if not is_valid_tag_identifier(raw_tag):
                raise ValueError(
                    f"Rule '{rule_name}': invalid tag {raw_tag!r}. Custom tags must start "
                    "with a letter, contain only letters/numbers/underscores, and be < 100 "
                    "characters (or use a Google-managed 'google.*' tag or full "
                    "'projects/.../locations/.../instances/.../tags/...' resource name)."
                )
            key = canonical_tag_key(raw_tag)
            if key in seen_tag_keys:
                dup_msg = f"Rule '{rule_name}' contains duplicate tag {raw_tag!r}."
                if strict:
                    raise ValueError(dup_msg)
                warnings.append(dup_msg)
            seen_tag_keys.add(key)

    return warnings


def load_repo_rule_config(
    rules_path: Path, tenant: str, rule_name: str
) -> dict[str, Any]:
    """
    Load the per-rule YAML configuration for a tenant rule if available.

    Resolution precedence:
    1. `rules/tenants/<tenant>/<rule_name>.yaml` (standalone file or symlink)
    2. `rules/shared/<rule_name>.yaml` if `rules/tenants/<tenant>/<rule_name>.yaral`
       is a symlink to shared rules
    3. Empty dict `{}` if no YAML sidecar is present
    """
    tenant_dir = rules_path / "tenants" / tenant
    tenant_yaml = tenant_dir / f"{rule_name}.yaml"
    tenant_yaral = tenant_dir / f"{rule_name}.yaral"
    shared_yaml = rules_path / "shared" / f"{rule_name}.yaml"

    config_path: Path | None = None
    if tenant_yaml.exists():
        config_path = tenant_yaml
    elif tenant_yaral.is_symlink() and shared_yaml.exists():
        config_path = shared_yaml

    if config_path is None:
        return {}

    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    validate_rule_config_dict(rule_name, loaded, strict=False)
    return loaded


def format_rule_config_yaml(rule_cfg: dict[str, Any]) -> str:
    """Serialize a rule deployment config dictionary to YAML with license header."""
    ordered: dict[str, Any] = {}
    for key in ("enabled", "alerting", "archived", "run_frequency", "scope"):
        if key in rule_cfg and rule_cfg[key] is not None:
            ordered[key] = rule_cfg[key]
    tags = rule_cfg.get("tags")
    if isinstance(tags, list) and tags:
        ordered["tags"] = [extract_tag_id(t) for t in tags]
    sc = rule_cfg.get("schedule_customizations")
    if isinstance(sc, dict) and sc:
        ordered_sc: dict[str, Any] = {}
        for sc_key in (
            "ensure_enrichment_completeness",
            "late_arriving_data_adjustment",
        ):
            if sc_key in sc and sc[sc_key] is not None:
                ordered_sc[sc_key] = sc[sc_key]
        if ordered_sc:
            ordered["schedule_customizations"] = ordered_sc

    body = yaml.safe_dump(ordered, sort_keys=False, default_flow_style=False)
    return YAML_BOILERPLATE_HEADER + body


def create_rule_v1(
    chronicle_client: ChronicleClient,
    rule_text: str,
    scope: str | None = None,
) -> dict[str, Any]:
    """Create a rule via Chronicle v1 API with optional DataAccessScope."""
    payload: dict[str, Any] = {"text": rule_text}
    if scope:
        payload["scope"] = scope
    return chronicle_request(
        chronicle_client,
        method="POST",
        endpoint_path="rules",
        api_version=APIVersion.V1,
        json=payload,
        error_message="Failed to create rule",
    )


def update_rule_v1(
    chronicle_client: ChronicleClient,
    rule_id: str,
    *,
    rule_text: str | None = None,
    scope: str | None = None,
    update_scope: bool = False,
) -> dict[str, Any]:
    """Update rule text and/or scope via Chronicle v1 PATCH."""
    body: dict[str, Any] = {}
    fields: list[str] = []
    if rule_text is not None:
        body["text"] = rule_text
        fields.append("text")
    if update_scope:
        body["scope"] = scope or ""
        fields.append("scope")
    if not fields:
        raise SecOpsError("No rule fields provided to update")
    return chronicle_request(
        chronicle_client,
        method="PATCH",
        endpoint_path=f"rules/{rule_id}",
        api_version=APIVersion.V1,
        params={"update_mask": ",".join(fields)},
        json=body,
        error_message="Failed to update rule",
    )


def update_rule_deployment_v1(
    chronicle_client: ChronicleClient,
    rule_id: str,
    *,
    enabled: bool | None = None,
    alerting: bool | None = None,
    archived: bool | None = None,
    run_frequency: str | None = None,
    schedule_customizations: dict[str, Any] | None = None,
    update_schedule_customizations: bool = False,
) -> dict[str, Any]:
    """
    Update a Chronicle v1 RuleDeployment, supporting customizable schedules.

    Note: Per Chronicle v1 RuleDeployment API semantics, `scheduleCustomizations`
    shares the `"runFrequency"` update mask path (there is no separate
    `"scheduleCustomizations"` mask path), so both fields are sent together
    whenever either is updated.
    """
    body: dict[str, Any] = {}
    fields: list[str] = []

    if enabled is not None:
        body["enabled"] = enabled
        fields.append("enabled")
    if alerting is not None:
        body["alerting"] = alerting
        fields.append("alerting")
    if archived is not None:
        body["archived"] = archived
        fields.append("archived")

    if run_frequency is not None or update_schedule_customizations:
        fields.append("runFrequency")
        if run_frequency is not None:
            body["runFrequency"] = run_frequency
        api_sc = schedule_customizations_yaml_to_api(schedule_customizations)
        if api_sc is not None:
            body["scheduleCustomizations"] = api_sc
        elif update_schedule_customizations:
            body["scheduleCustomizations"] = {}

    if not fields:
        raise SecOpsError("No deployment fields provided to update")

    return chronicle_request(
        chronicle_client,
        method="PATCH",
        endpoint_path=f"rules/{rule_id}/deployment",
        api_version=APIVersion.V1,
        params={"update_mask": ",".join(fields)},
        json=body,
        error_message="Failed to update rule deployment",
    )


def verify_rule_text_v1alpha(
    chronicle_client: ChronicleClient, rule_text: str
) -> dict[str, Any]:
    """Call Chronicle v1alpha instances:verifyRuleText and return the full response."""
    cleaned = rule_text.strip("` \n\t\r")
    return chronicle_request(
        chronicle_client,
        method="POST",
        endpoint_path=":verifyRuleText",
        api_version=APIVersion.V1ALPHA,
        json={"ruleText": cleaned},
        error_message="Failed to validate rule",
    )


def list_tags_v1alpha(chronicle_client: ChronicleClient) -> set[str]:
    """List existing Tag IDs in the SecOps instance via Chronicle v1alpha tags.list."""
    raw_items = chronicle_paginated_request(
        chronicle_client,
        path="tags",
        items_key="tags",
        api_version=APIVersion.V1ALPHA,
        as_list=True,
    )
    items = (
        raw_items.get("tags", [])
        if isinstance(raw_items, Mapping)
        else (raw_items or [])
    )
    existing: set[str] = set()
    for item in items:
        if isinstance(item, Mapping) and item.get("name"):
            existing.add(extract_tag_id(str(item["name"])))
    return existing


def _rule_recency_key(rule_dict: Mapping[str, Any]) -> tuple[str, str]:
    """Return a comparison tuple favoring the most recently created/revised rule."""
    return (
        str(rule_dict.get("createTime") or ""),
        str(rule_dict.get("revisionCreateTime") or ""),
    )


def list_customer_rules_with_tags_v1alpha(
    chronicle_client: ChronicleClient,
) -> list[dict[str, Any]]:
    """
    List active (non-archived) customer rules via v1alpha, merging `CONFIG_ONLY` and `FULL`.

    In Chronicle v1alpha `rules.list`, `view=FULL` populates `text`, `scope`,
    `createTime`, and `ruleTextTags` (without `tags` or `archived`), whereas
    `view=CONFIG_ONLY` populates `tags` and `archived` (without `ruleTextTags`).
    Joining both views avoids per-rule `rules.get` calls, excludes archived rules,
    and deduplicates rules sharing the same `displayName` to the newest active rule.
    """
    raw_full = chronicle_client.list_rules(
        view="FULL", api_version=APIVersion.V1ALPHA, as_list=True
    )
    full_list = (
        raw_full.get("rules", []) if isinstance(raw_full, Mapping) else (raw_full or [])
    )

    raw_cfg = chronicle_client.list_rules(
        view="CONFIG_ONLY", api_version=APIVersion.V1ALPHA, as_list=True
    )
    cfg_list = (
        raw_cfg.get("rules", []) if isinstance(raw_cfg, Mapping) else (raw_cfg or [])
    )

    cfg_by_id: dict[str, Mapping[str, Any]] = {}
    for cfg_rule in cfg_list:
        if not isinstance(cfg_rule, Mapping) or not cfg_rule.get("name"):
            continue
        rid = get_rule_id_from_location(str(cfg_rule["name"]))
        if rid:
            cfg_by_id[rid] = cfg_rule

    deduped_by_name: dict[str, dict[str, Any]] = {}
    unnamed_rules: list[dict[str, Any]] = []
    for rule in full_list:
        if not isinstance(rule, Mapping) or rule.get("ruleOwner") == "GOOGLE":
            continue
        rid = get_rule_id_from_location(str(rule.get("name", "")))
        if not rid or rid.startswith("ur_"):
            continue
        rule_copy = dict(rule)
        cfg_rule = cfg_by_id.get(rid)
        if cfg_rule is not None:
            if cfg_rule.get("tags") is not None:
                rule_copy["tags"] = list(cfg_rule.get("tags") or [])
            if cfg_rule.get("archived") is not None:
                rule_copy["archived"] = bool(cfg_rule.get("archived"))

        if rule_copy.get("archived", False):
            continue

        display_name = str(rule_copy.get("displayName") or "").strip()
        if not display_name:
            unnamed_rules.append(rule_copy)
            continue

        existing = deduped_by_name.get(display_name)
        if existing is None or _rule_recency_key(rule_copy) > _rule_recency_key(
            existing
        ):
            deduped_by_name[display_name] = rule_copy

    return list(deduped_by_name.values()) + unnamed_rules


def ensure_custom_tags_v1alpha(
    chronicle_client: ChronicleClient,
    desired_tag_ids: Iterable[str],
) -> list[str]:
    """Auto-create missing customer Tag resources via v1alpha (skipping `google.*` tags)."""
    custom_ids = sorted(
        {
            extract_tag_id(t)
            for t in desired_tag_ids
            if t and not is_google_tag_id(extract_tag_id(t))
        }
    )
    if not custom_ids:
        return []

    existing_ids = list_tags_v1alpha(chronicle_client)
    missing_ids = [tag_id for tag_id in custom_ids if tag_id not in existing_ids]
    created: list[str] = []

    for tag_id in missing_ids:
        if verbose:
            print(f"Creating missing custom Tag '{tag_id}'")
        try:
            chronicle_request(
                chronicle_client,
                method="POST",
                endpoint_path="tags",
                api_version=APIVersion.V1ALPHA,
                params={"tagId": tag_id},
                json={"displayName": tag_id},
                error_message=f"Failed to create custom tag '{tag_id}'",
            )
            created.append(tag_id)
        except APIError as exc:
            err_text = str(exc)
            if "status=409" not in err_text and "ALREADY_EXISTS" not in err_text:
                raise
    return created


def modify_rule_tags_v1alpha(
    chronicle_client: ChronicleClient,
    project_id: str,
    region: str,
    customer_id: str,
    updates: Sequence[tuple[str, str, Sequence[str]]],
    *,
    batch_size: int = 200,
) -> list[str]:
    """
    Batch-update rule tags via POST /v1alpha/{parent}/rules:modifyRules.

    Raises SecOpsError if `failedRequests` / `failed_requests` reports partial failures.
    """
    if not updates:
        return []

    parent = f"projects/{project_id}/locations/{region}/instances/{customer_id}"
    updated_names: list[str] = []
    failures: list[str] = []

    for start in range(0, len(updates), batch_size):
        chunk = updates[start : start + batch_size]
        requests_payload = [
            {
                "rule": {
                    "name": f"{parent}/rules/{rule_id}",
                    "tags": [
                        format_tag_resource(project_id, region, customer_id, t)
                        for t in desired_tags
                    ],
                },
                "updateMask": "tags",
            }
            for _rule_name, rule_id, desired_tags in chunk
        ]

        response = chronicle_request(
            chronicle_client,
            method="POST",
            endpoint_path="rules:modifyRules",
            api_version=APIVersion.V1ALPHA,
            json={"requests": requests_payload},
            error_message="Failed to batch-modify rule tags",
        )

        failed_map = (
            response.get("failedRequests") or response.get("failed_requests") or {}
        )
        failed_indices: set[int] = set()
        for raw_idx, status_obj in failed_map.items():
            idx = int(raw_idx)
            failed_indices.add(idx)
            failed_rule_name, failed_rule_id, _ = chunk[idx]
            msg = (
                status_obj.get("message", str(status_obj))
                if isinstance(status_obj, Mapping)
                else str(status_obj)
            )
            failures.append(f"{failed_rule_name} ({failed_rule_id}): {msg}")

        for idx, (rule_name, _rule_id, _desired) in enumerate(chunk):
            if idx not in failed_indices:
                updated_names.append(rule_name)

    if failures:
        raise SecOpsError("rules:modifyRules reported failures: " + "; ".join(failures))

    return updated_names


def create_chronicle_client(
    tenant_details: dict[str, str], service_account=""
) -> ChronicleClient:
    secops_client = SecOpsClient(
        impersonate_service_account=service_account if service_account else None,
        retry_config=RetryConfig(backoff_factor=3, total=3),
    )
    region = tenant_details.get("region", REGION)
    chronicle_client = secops_client.chronicle(
        customer_id=tenant_details["customerId"],
        project_id=tenant_details["gcpProject"],
        region=region,
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

    with open(args.tenants_file, "r", encoding="utf-8") as tenants_file:
        all_tenants = json.load(tenants_file)

    if affects_tenants:
        if args.stage:
            all_tenants_names = all_tenants[env].keys()
            match args.stage:
                case "all":
                    selected_tenants_names = list(all_tenants_names)
                case "build":
                    selected_tenants_names = list(
                        get_build_tenant_ids(all_tenants_names)
                    )
                case "live":
                    selected_tenants_names = list(get_live_tenant_ids())
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

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
"""Manage Chronicle v1alpha Rule Tags for Google SecOps Detection-as-Code."""

import logging
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from secops.chronicle.models import APIVersion
from secops.chronicle.utils.request_utils import (
    chronicle_paginated_request,
    chronicle_request,
)
from secops.exceptions import APIError

_LOGGER = logging.getLogger(__name__)
if not _LOGGER.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    _LOGGER.addHandler(_handler)
    _LOGGER.setLevel(logging.INFO)

CUSTOM_TAG_ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,98}$")
GOOGLE_TAG_ID_PATTERN = re.compile(r"^google\.[a-zA-Z0-9][a-zA-Z0-9._-]*$")
FULL_TAG_RESOURCE_PATTERN = re.compile(
    r"^projects/[^/]+/locations/[^/]+/instances/[^/]+/tags/(.+)$"
)
RULE_NAME_PATTERN = re.compile(r"rule\s+([a-zA-Z0-9_]+)\s*\{")


class RuleTagsError(Exception):
    """Raised when synchronizing or validating rule tags fails."""


def extract_tag_id(tag: str) -> str:
    """Extract the short tag ID from a short tag ID or full Tag resource name."""
    cleaned = tag.strip()
    match = FULL_TAG_RESOURCE_PATTERN.match(cleaned)
    if match:
        return match.group(1)
    return cleaned


def is_google_tag_id(tag_id: str) -> bool:
    """Return True if tag_id belongs to the Google-managed `google.*` namespace."""
    return bool(GOOGLE_TAG_ID_PATTERN.match(tag_id))


def is_valid_tag_identifier(tag: str) -> bool:
    """Return True if tag is a valid short tag ID or full Chronicle Tag resource name."""
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


def format_tag_resource(instance_id: str, tag: str) -> str:
    """Format a short tag ID or full Tag resource path into a full resource name."""
    cleaned = tag.strip()
    if FULL_TAG_RESOURCE_PATTERN.match(cleaned):
        return cleaned
    return f"{instance_id}/tags/{extract_tag_id(cleaned)}"


def validate_rule_tags(rule_name: str, tags: Any, *, strict: bool = False) -> list[str]:
    """
    Validate a rule's `tags` list from YAML and return normalized short tag IDs.

    Raises:
        TypeError: If tags is not None and not a list of strings.
        ValueError: If any tag identifier is malformed (or duplicated under strict=True).
    """
    if tags is None:
        return []
    if not isinstance(tags, list):
        raise TypeError(f"Rule '{rule_name}': 'tags' must be a YAML list of strings.")

    normalized: list[str] = []
    seen_keys: set[str] = set()
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
        if key in seen_keys:
            msg = f"Rule '{rule_name}' contains duplicate tag entry {raw_tag!r}."
            if strict:
                raise ValueError(msg)
            _LOGGER.warning(msg)
            continue
        seen_keys.add(key)
        normalized.append(extract_tag_id(raw_tag))

    return normalized


def extract_api_rule_tags(rule_dict: Mapping[str, Any]) -> list[str]:
    """
    Extract API-managed rule tags (`tags` minus `ruleTextTags`) as short tag IDs.

    Tags defined inside the YARA-L `meta` block appear in `ruleTextTags` and are
    read-only in the Rules API; excluding them prevents duplicating `meta` tags in YAML.
    """
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


def tags_equal(desired_tags: Sequence[str], remote_api_tags: Sequence[str]) -> bool:
    """Return True if two tag sequences represent the same set of rule tags."""
    return {canonical_tag_key(t) for t in desired_tags} == {
        canonical_tag_key(t) for t in remote_api_tags
    }


def list_remote_tags(chronicle_client: Any) -> set[str]:
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


def list_customer_rules_with_tags(chronicle_client: Any) -> list[dict[str, Any]]:
    """
    List customer rules via v1alpha, merging `CONFIG_ONLY` `tags` with `FULL` `ruleTextTags`.

    In the Chronicle v1alpha `rules.list` endpoint, `view=FULL` populates `text`,
    `scope`, and `ruleTextTags` (omitting `tags`), while `view=CONFIG_ONLY` populates
    `tags` (omitting `ruleTextTags`). Joining both views yields full rule content
    plus accurate `tags` and `ruleTextTags` without per-rule `rules.get` calls.
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

    cfg_tags_by_id: dict[str, list[str]] = {}
    for cfg_rule in cfg_list:
        if (
            not isinstance(cfg_rule, Mapping)
            or not cfg_rule.get("name")
            or cfg_rule.get("tags") is None
        ):
            continue
        rid = _extract_rule_id(str(cfg_rule["name"]))
        if rid:
            cfg_tags_by_id[rid] = list(cfg_rule.get("tags") or [])

    merged: list[dict[str, Any]] = []
    for rule in full_list:
        if not isinstance(rule, Mapping) or rule.get("ruleOwner") == "GOOGLE":
            continue
        rid = _extract_rule_id(str(rule.get("name", "")))
        if not rid or rid.startswith("ur_"):
            continue
        rule_copy = dict(rule)
        if rid in cfg_tags_by_id:
            rule_copy["tags"] = cfg_tags_by_id[rid]
        merged.append(rule_copy)

    return merged


def ensure_custom_tags_exist(
    chronicle_client: Any,
    desired_tag_ids: Iterable[str],
    *,
    dry_run: bool = False,
) -> list[str]:
    """
    Auto-create any missing custom (`TAG_OWNER_CUSTOMER`) Tag resources via v1alpha.

    Google-managed tags (`google.*`) are skipped and never passed to `tags.create`.
    """
    custom_ids = sorted(
        {
            extract_tag_id(t)
            for t in desired_tag_ids
            if t and not is_google_tag_id(extract_tag_id(t))
        }
    )
    if not custom_ids:
        return []

    existing_ids = list_remote_tags(chronicle_client)
    missing_ids = [tag_id for tag_id in custom_ids if tag_id not in existing_ids]
    if not missing_ids:
        return []

    created: list[str] = []
    for tag_id in missing_ids:
        if dry_run:
            _LOGGER.info("[DRY RUN] Would create custom Tag resource '%s'.", tag_id)
            created.append(tag_id)
            continue

        _LOGGER.info("Creating missing custom Tag resource '%s'...", tag_id)
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
            if "status=409" in err_text or "ALREADY_EXISTS" in err_text:
                _LOGGER.info("Custom Tag '%s' already exists; continuing.", tag_id)
            else:
                raise

    return created


def modify_rule_tags_batch(
    chronicle_client: Any,
    instance_id: str,
    updates: Sequence[tuple[str, str, Sequence[str]]],
    *,
    batch_size: int = 200,
) -> list[str]:
    """
    Batch-update rule tags via POST /v1alpha/{parent}/rules:modifyRules.

    Inspects `failedRequests` / `failed_requests` in the response and raises
    RuleTagsError if any individual rule update failed.
    """
    if not updates:
        return []

    updated_rule_names: list[str] = []
    failures: list[str] = []

    for start in range(0, len(updates), batch_size):
        chunk = updates[start : start + batch_size]
        requests_payload = [
            {
                "rule": {
                    "name": f"{instance_id}/rules/{rule_id}",
                    "tags": [format_tag_resource(instance_id, t) for t in desired_tags],
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
            if isinstance(status_obj, Mapping):
                code = status_obj.get("code", "UNKNOWN")
                message = status_obj.get("message", str(status_obj))
            else:
                code = "UNKNOWN"
                message = str(status_obj)
            _LOGGER.error(
                "Failed to update tags for rule '%s' (%s): code=%s, message=%s",
                failed_rule_name,
                failed_rule_id,
                code,
                message,
            )
            failures.append(f"{failed_rule_name} ({failed_rule_id}): {message}")

        for idx, (rule_name, _rule_id, _desired) in enumerate(chunk):
            if idx not in failed_indices:
                updated_rule_names.append(rule_name)

    if failures:
        raise RuleTagsError(
            "rules:modifyRules reported partial or full failures: "
            + "; ".join(failures)
        )

    return updated_rule_names


def _extract_rule_id(resource_name: str) -> str:
    if not resource_name:
        return ""
    return resource_name.removesuffix("/deployment").split("/")[-1]


def _extract_rule_name(rule_dict: Mapping[str, Any]) -> str:
    display_name = rule_dict.get("displayName")
    if isinstance(display_name, str) and display_name.strip():
        return display_name.strip()
    rule_text = rule_dict.get("text", "")
    if isinstance(rule_text, str):
        match = RULE_NAME_PATTERN.search(rule_text)
        if match:
            return match.group(1)
    return ""


def sync_rule_tags(
    chronicle_client: Any,
    rules_config: Mapping[str, Any],
    *,
    instance_id: str,
    dry_run: bool = False,
) -> dict[str, list[str]]:
    """
    Synchronize rule `tags` declared in `secops_rules.yaml` with Google SecOps v1alpha.

    Returns:
        Dictionary with keys `created_tags`, `updated_rules`, and `pending_new_rules`.
    """
    summary: dict[str, list[str]] = {
        "created_tags": [],
        "updated_rules": [],
        "pending_new_rules": [],
    }
    if not rules_config:
        _LOGGER.info("No rules configured in secops_rules.yaml; skipping tag sync.")
        return summary

    # Validate all local tag declarations upfront before making remote mutations
    desired_by_rule: dict[str, list[str]] = {}
    for rule_name, raw_cfg in rules_config.items():
        if raw_cfg is not None and not isinstance(raw_cfg, Mapping):
            raise TypeError(
                f"Rule '{rule_name}': configuration must be a YAML mapping."
            )
        raw_tags = (raw_cfg or {}).get("tags")
        desired_by_rule[rule_name] = validate_rule_tags(rule_name, raw_tags)

    rules_list = list_customer_rules_with_tags(chronicle_client)

    remote_by_name: dict[str, dict[str, Any]] = {}
    for rule in rules_list:
        rule_id = _extract_rule_id(str(rule.get("name", "")))
        r_name = _extract_rule_name(rule)
        if r_name and rule_id:
            remote_by_name[r_name] = {
                "id": rule_id,
                "api_tags": extract_api_rule_tags(rule),
            }

    pending_updates: list[tuple[str, str, list[str]]] = []
    all_needed_tags: set[str] = set()

    for rule_name, desired_tags in desired_by_rule.items():
        remote_info = remote_by_name.get(rule_name)
        if remote_info is None:
            if dry_run:
                if desired_tags:
                    _LOGGER.info(
                        "[DRY RUN] Rule '%s' is not yet deployed in SecOps; "
                        "tags %s will be applied after 'terraform apply'.",
                        rule_name,
                        desired_tags,
                    )
                    all_needed_tags.update(desired_tags)
                    summary["pending_new_rules"].append(rule_name)
                continue
            raise RuleTagsError(
                f"Rule '{rule_name}' is configured in secops_rules.yaml but was not "
                "found in SecOps. Run 'terraform apply' before 'update-rule-tags'."
            )

        current_api_tags = remote_info["api_tags"]
        if not tags_equal(desired_tags, current_api_tags):
            all_needed_tags.update(desired_tags)
            pending_updates.append((rule_name, remote_info["id"], desired_tags))
            if dry_run:
                _LOGGER.info(
                    "[DRY RUN] Would update tags on rule '%s' (%s): %s -> %s",
                    rule_name,
                    remote_info["id"],
                    current_api_tags,
                    desired_tags,
                )
            else:
                _LOGGER.info(
                    "Queueing tag update for rule '%s' (%s): %s -> %s",
                    rule_name,
                    remote_info["id"],
                    current_api_tags,
                    desired_tags,
                )

    if all_needed_tags:
        summary["created_tags"] = ensure_custom_tags_exist(
            chronicle_client,
            all_needed_tags,
            dry_run=dry_run,
        )

    if not pending_updates:
        _LOGGER.info("All deployed rule tags are in sync.")
        return summary

    if dry_run:
        summary["updated_rules"] = [name for name, _, _ in pending_updates]
        return summary

    summary["updated_rules"] = modify_rule_tags_batch(
        chronicle_client,
        instance_id,
        pending_updates,
    )
    _LOGGER.info(
        "Successfully updated tags on %d rule(s): %s",
        len(summary["updated_rules"]),
        ", ".join(summary["updated_rules"]),
    )
    return summary

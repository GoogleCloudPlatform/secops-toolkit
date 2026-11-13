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
"""Unit tests for pipelines/detection-as-code CLI (pull-rules & verify-rules)."""

import inspect
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

MULTI_EVENT_RULE_TEXT = """rule network_traffic_to_specific_country {
  meta:
    author = "Google Cloud Security"
    description = "Identify network traffic based on target country"
  events:
    $e.metadata.event_type = "NETWORK_CONNECTION"
    $e.target.ip = $ip
  match:
    $ip over 30m
  condition:
    #e > 1
}
"""

SINGLE_EVENT_RULE_TEXT = """rule single_event_ssh_login {
  meta:
    author = "Google Cloud Security"
  events:
    $e.metadata.event_type = "USER_LOGIN"
  condition:
    $e
}
"""


def _configure_temp_paths(config_mod, tmp_path: Path) -> tuple[Path, Path]:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    rules_yaml = tmp_path / "secops_rules.yaml"
    ref_yaml = tmp_path / "secops_reference_lists.yaml"
    dt_yaml = tmp_path / "secops_data_tables.yaml"

    config_mod.BASE_RULES_DIR = rules_dir
    config_mod.SECOPS_RULES_CONFIG_PATH = rules_yaml
    config_mod.SECOPS_REFERENCE_LISTS_CONFIG_PATH = ref_yaml
    config_mod.SECOPS_DATA_TABLES_CONFIG_PATH = dt_yaml
    return rules_dir, rules_yaml


def test_pull_rules_live_customizable_payload(
    dac_single_tenant_modules, tmp_path, monkeypatch, capsys
):
    """Verify pull-rules maps full RuleDeployment resource names, LIVE_CUSTOMIZABLE, and scheduleCustomizations."""
    config_mod, main_mod = dac_single_tenant_modules
    rules_dir, rules_yaml = _configure_temp_paths(config_mod, tmp_path)

    monkeypatch.setenv("SECOPS_PROJECT_ID", "123456789012")
    monkeypatch.setenv("SECOPS_REGION", "eu")
    monkeypatch.setenv("SECOPS_CUSTOMER_ID", "00000000-0000-0000-0000-000000000001")

    rule_id = "ru_00000000-1111-2222-3333-444444444444"
    instance_prefix = (
        "projects/123456789012/locations/eu/"
        "instances/00000000-0000-0000-0000-000000000001"
    )

    mock_client = MagicMock()
    mock_client.list_rules.return_value = {
        "rules": [
            {
                "name": f"{instance_prefix}/rules/{rule_id}",
                "text": MULTI_EVENT_RULE_TEXT,
                "scope": f"{instance_prefix}/dataAccessScopes/eu-soc-scope",
            }
        ]
    }
    mock_client.list_rule_deployments.return_value = {
        "ruleDeployments": [
            {
                "name": f"{instance_prefix}/rules/{rule_id}/deployment",
                "enabled": True,
                "alerting": True,
                "runFrequency": "LIVE_CUSTOMIZABLE",
                "executionState": "DEFAULT",
                "lastAlertStatusChangeTime": "2025-12-19T08:09:59.366066Z",
                "scheduleCustomizations": {
                    "lateArrivingDataAdjustment": "300s",
                },
            }
        ]
    }

    ctx = main_mod.AppContext()
    ctx.chronicle_client = mock_client
    inspect.unwrap(main_mod.pull_rules.callback)(ctx)

    saved_yaral = rules_dir / "network_traffic_to_specific_country.yaral"
    assert saved_yaral.is_file()
    assert saved_yaral.read_text(encoding="utf-8") == MULTI_EVENT_RULE_TEXT

    loaded_cfg = yaml.safe_load(rules_yaml.read_text(encoding="utf-8"))
    assert loaded_cfg == {
        "network_traffic_to_specific_country": {
            "enabled": True,
            "alerting": True,
            "archived": False,
            "run_frequency": "LIVE_CUSTOMIZABLE",
            "schedule_customizations": {
                "late_arriving_data_adjustment": "300s",
            },
            "scope": "eu-soc-scope",
        }
    }

    out = capsys.readouterr().out
    assert (
        "terraform import 'google_chronicle_rule.rule[\"network_traffic_to_specific_country\"]'"
        in out
    )
    assert (
        "terraform import 'google_chronicle_rule_deployment.rule_deployment[\"network_traffic_to_specific_country\"]'"
        in out
    )


def test_verify_rules_allowed_run_frequencies_and_strict_mode(
    dac_single_tenant_modules, tmp_path, monkeypatch
):
    """Verify legacy coerced frequencies warn by default and fail under --strict, while matching frequencies pass."""
    config_mod, main_mod = dac_single_tenant_modules
    rules_dir, rules_yaml = _configure_temp_paths(config_mod, tmp_path)

    (rules_dir / "network_traffic_to_specific_country.yaral").write_text(
        MULTI_EVENT_RULE_TEXT, encoding="utf-8"
    )

    mock_request = MagicMock(
        return_value={
            "success": True,
            "allowedRunFrequencies": ["LIVE_CUSTOMIZABLE", "HOURLY_CUSTOMIZABLE"],
            "nearRealTimeLiveRuleEligible": False,
        }
    )
    monkeypatch.setattr(main_mod, "chronicle_request", mock_request)

    ctx = main_mod.AppContext()
    ctx.chronicle_client = MagicMock()
    verify_fn = inspect.unwrap(main_mod.verify_rules.callback)

    # 1. Valid LIVE_CUSTOMIZABLE + schedule_customizations passes in --strict mode
    rules_yaml.write_text(
        yaml.safe_dump(
            {
                "network_traffic_to_specific_country": {
                    "enabled": True,
                    "alerting": True,
                    "archived": False,
                    "run_frequency": "LIVE_CUSTOMIZABLE",
                    "schedule_customizations": {
                        "ensure_enrichment_completeness": True,
                        "late_arriving_data_adjustment": "300s",
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    verify_fn(ctx, strict=True, offline=False)
    assert mock_request.call_args.kwargs["endpoint_path"] == ":verifyRuleText"
    assert mock_request.call_args.kwargs["api_version"] == main_mod.APIVersion.V1ALPHA

    # 2. Legacy coerced DAILY warns and exits 0 without --strict, but exits 1 with --strict
    rules_yaml.write_text(
        yaml.safe_dump(
            {
                "network_traffic_to_specific_country": {
                    "enabled": True,
                    "alerting": True,
                    "archived": False,
                    "run_frequency": "DAILY",
                }
            }
        ),
        encoding="utf-8",
    )
    verify_fn(ctx, strict=False, offline=False)

    with pytest.raises(SystemExit) as exc_info:
        verify_fn(ctx, strict=True, offline=False)
    assert exc_info.value.code == 1


def test_verify_rules_hard_invalid_frequency_fails_without_strict(
    dac_single_tenant_modules, tmp_path, monkeypatch
):
    """LIVE_CUSTOMIZABLE on a single-event rule (allowedRunFrequencies=['LIVE']) must always fail."""
    config_mod, main_mod = dac_single_tenant_modules
    rules_dir, rules_yaml = _configure_temp_paths(config_mod, tmp_path)

    (rules_dir / "single_event_ssh_login.yaral").write_text(
        SINGLE_EVENT_RULE_TEXT, encoding="utf-8"
    )
    rules_yaml.write_text(
        yaml.safe_dump(
            {
                "single_event_ssh_login": {
                    "enabled": True,
                    "alerting": True,
                    "archived": False,
                    "run_frequency": "LIVE_CUSTOMIZABLE",
                    "schedule_customizations": {
                        "late_arriving_data_adjustment": "300s",
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        main_mod,
        "chronicle_request",
        MagicMock(
            return_value={
                "success": True,
                "allowedRunFrequencies": ["LIVE"],
                "nearRealTimeLiveRuleEligible": True,
            }
        ),
    )

    ctx = main_mod.AppContext()
    ctx.chronicle_client = MagicMock()
    verify_fn = inspect.unwrap(main_mod.verify_rules.callback)
    with pytest.raises(SystemExit) as exc_info:
        verify_fn(ctx, strict=False, offline=False)
    assert exc_info.value.code == 1


@pytest.mark.parametrize(
    "bad_cfg",
    [
        # schedule_customizations on non-customizable DAILY frequency
        {
            "enabled": True,
            "alerting": True,
            "archived": False,
            "run_frequency": "DAILY",
            "schedule_customizations": {"late_arriving_data_adjustment": "300s"},
        },
        # Invalid duration syntax (must end in 's')
        {
            "enabled": True,
            "alerting": True,
            "archived": False,
            "run_frequency": "LIVE_CUSTOMIZABLE",
            "schedule_customizations": {"late_arriving_data_adjustment": "5m"},
        },
        # archived=true while enabled=true
        {
            "enabled": True,
            "alerting": False,
            "archived": True,
            "run_frequency": "LIVE_CUSTOMIZABLE",
        },
        # Invalid custom tag ID (contains hyphen, which v1alpha tags.create rejects)
        {
            "enabled": True,
            "alerting": True,
            "archived": False,
            "run_frequency": "LIVE_CUSTOMIZABLE",
            "tags": ["invalid-hyphen-tag"],
        },
        # Invalid tags type (scalar string instead of YAML list)
        {
            "enabled": True,
            "alerting": True,
            "archived": False,
            "run_frequency": "LIVE_CUSTOMIZABLE",
            "tags": "soc_tier1",
        },
    ],
)
def test_verify_rules_offline_rejects_invalid_yaml_configs(
    dac_single_tenant_modules, tmp_path, bad_cfg
):
    """Offline validation catches invalid scheduler and archive configurations without API calls."""
    config_mod, main_mod = dac_single_tenant_modules
    rules_dir, rules_yaml = _configure_temp_paths(config_mod, tmp_path)

    (rules_dir / "network_traffic_to_specific_country.yaral").write_text(
        MULTI_EVENT_RULE_TEXT, encoding="utf-8"
    )
    rules_yaml.write_text(
        yaml.safe_dump({"network_traffic_to_specific_country": bad_cfg}),
        encoding="utf-8",
    )

    ctx = main_mod.AppContext()
    verify_fn = inspect.unwrap(main_mod.verify_rules.callback)
    with pytest.raises(SystemExit) as exc_info:
        verify_fn(ctx, strict=False, offline=True)
    assert exc_info.value.code == 1


def test_pull_rules_extracts_api_tags_excluding_rule_text_tags(
    dac_single_tenant_modules, tmp_path, monkeypatch
):
    """pull-rules persists API-applied tags while filtering out YARA-L meta ruleTextTags."""
    config_mod, main_mod = dac_single_tenant_modules
    _rules_dir, rules_yaml = _configure_temp_paths(config_mod, tmp_path)

    monkeypatch.setenv("SECOPS_PROJECT_ID", "123456789012")
    monkeypatch.setenv("SECOPS_REGION", "eu")
    monkeypatch.setenv("SECOPS_CUSTOMER_ID", "00000000-0000-0000-0000-000000000001")

    rule_id = "ru_00000000-1111-2222-3333-444444444444"
    instance_prefix = (
        "projects/123456789012/locations/eu/"
        "instances/00000000-0000-0000-0000-000000000001"
    )

    mock_client = MagicMock()

    # Simulate live v1alpha split: FULL populates text + ruleTextTags (omitting tags),
    # while CONFIG_ONLY populates tags (omitting ruleTextTags).
    def _mock_list_rules(*, view="FULL", api_version=None, as_list=False):
        assert api_version == main_mod.APIVersion.V1ALPHA
        assert as_list is True
        if view == "FULL":
            return [
                {
                    "name": f"{instance_prefix}/rules/{rule_id}",
                    "text": MULTI_EVENT_RULE_TEXT,
                    "ruleTextTags": [
                        f"{instance_prefix}/tags/google.mitre.tactic.TA0001",
                    ],
                }
            ]
        if view == "CONFIG_ONLY":
            return [
                {
                    "name": f"{instance_prefix}/rules/{rule_id}",
                    "tags": [
                        f"{instance_prefix}/tags/google.mitre.tactic.ta0001",
                        f"{instance_prefix}/tags/soc_tier1",
                        f"{instance_prefix}/tags/google.mitre.tactic.ta0011",
                    ],
                }
            ]
        raise AssertionError(f"Unexpected view: {view}")

    mock_client.list_rules.side_effect = _mock_list_rules
    mock_client.list_rule_deployments.return_value = {
        "ruleDeployments": [
            {
                "name": f"{instance_prefix}/rules/{rule_id}/deployment",
                "enabled": True,
                "alerting": False,
                "runFrequency": "LIVE_CUSTOMIZABLE",
            }
        ]
    }

    ctx = main_mod.AppContext()
    ctx.chronicle_client = mock_client
    inspect.unwrap(main_mod.pull_rules.callback)(ctx)

    assert mock_client.list_rules.call_count == 2
    loaded_cfg = yaml.safe_load(rules_yaml.read_text(encoding="utf-8"))
    assert loaded_cfg["network_traffic_to_specific_country"]["tags"] == [
        "soc_tier1",
        "google.mitre.tactic.ta0011",
    ]


def test_update_rule_tags_auto_creates_custom_tags_and_batches_modify_rules(
    dac_single_tenant_modules, tmp_path, monkeypatch
):
    """update-rule-tags handles dry-run, auto-creates custom tags, batches modifyRules, and checks failedRequests."""
    import sys as _sys

    config_mod, main_mod = dac_single_tenant_modules
    rule_tags_mod = _sys.modules["rule_tags"]
    _rules_dir, rules_yaml = _configure_temp_paths(config_mod, tmp_path)

    monkeypatch.setenv("SECOPS_PROJECT_ID", "123456789012")
    monkeypatch.setenv("SECOPS_REGION", "eu")
    monkeypatch.setenv("SECOPS_CUSTOMER_ID", "00000000-0000-0000-0000-000000000001")

    instance_prefix = (
        "projects/123456789012/locations/eu/"
        "instances/00000000-0000-0000-0000-000000000001"
    )
    rule_1_id = "ru_00000000-1111-2222-3333-444444444444"
    rule_2_id = "ru_00000000-1111-2222-3333-555555555555"

    mock_client = MagicMock()
    mock_client.instance_id = instance_prefix
    mock_client.list_rules.return_value = [
        {
            "name": f"{instance_prefix}/rules/{rule_1_id}",
            "displayName": "network_traffic_to_specific_country",
            "tags": [f"{instance_prefix}/tags/existing_tag"],
            "ruleTextTags": [],
        },
        {
            "name": f"{instance_prefix}/rules/{rule_2_id}",
            "displayName": "single_event_ssh_login",
            "tags": [f"{instance_prefix}/tags/stale_tag"],
            "ruleTextTags": [],
        },
    ]

    monkeypatch.setattr(
        rule_tags_mod,
        "chronicle_paginated_request",
        MagicMock(return_value=[{"name": f"{instance_prefix}/tags/existing_tag"}]),
    )

    api_calls: list[dict] = []

    def _fake_request(_client, **kwargs):
        api_calls.append(kwargs)
        if kwargs["endpoint_path"] == "rules:modifyRules":
            return {"ruleUpdates": [{"tagsUpdated": True}, {"tagsUpdated": True}]}
        return {"name": f"{instance_prefix}/tags/{kwargs['params']['tagId']}"}

    monkeypatch.setattr(rule_tags_mod, "chronicle_request", _fake_request)

    # 1. Dry-run succeeds even if a brand-new PR rule does not exist in SecOps yet, with zero POST calls
    rules_yaml.write_text(
        yaml.safe_dump(
            {
                "network_traffic_to_specific_country": {
                    "enabled": True,
                    "tags": [
                        "existing_tag",
                        "new_custom_tag",
                        "google.mitre.tactic.TA0011",
                    ],
                },
                "brand_new_pr_rule": {
                    "enabled": True,
                    "tags": ["new_custom_tag"],
                },
            }
        ),
        encoding="utf-8",
    )

    ctx = main_mod.AppContext()
    ctx.chronicle_client = mock_client
    update_fn = inspect.unwrap(main_mod.update_rule_tags.callback)

    update_fn(ctx, dry_run=True)
    assert api_calls == []

    # 2. Apply mode auto-creates only `new_custom_tag` (skipping `existing_tag` and `google.*`)
    #    and clears `stale_tag` on `single_event_ssh_login` (which omits `tags` in YAML)
    rules_yaml.write_text(
        yaml.safe_dump(
            {
                "network_traffic_to_specific_country": {
                    "enabled": True,
                    "tags": [
                        "existing_tag",
                        "new_custom_tag",
                        "google.mitre.tactic.TA0011",
                    ],
                },
                "single_event_ssh_login": {
                    "enabled": True,
                },
            }
        ),
        encoding="utf-8",
    )
    update_fn(ctx, dry_run=False)
    assert len(api_calls) == 2

    tag_create_call = api_calls[0]
    assert tag_create_call["method"] == "POST"
    assert tag_create_call["endpoint_path"] == "tags"
    assert tag_create_call["api_version"] == main_mod.APIVersion.V1ALPHA
    assert tag_create_call["params"] == {"tagId": "new_custom_tag"}
    assert tag_create_call["json"] == {"displayName": "new_custom_tag"}

    modify_call = api_calls[1]
    assert modify_call["method"] == "POST"
    assert modify_call["endpoint_path"] == "rules:modifyRules"
    assert modify_call["api_version"] == main_mod.APIVersion.V1ALPHA
    assert modify_call["json"] == {
        "requests": [
            {
                "rule": {
                    "name": f"{instance_prefix}/rules/{rule_1_id}",
                    "tags": [
                        f"{instance_prefix}/tags/existing_tag",
                        f"{instance_prefix}/tags/new_custom_tag",
                        f"{instance_prefix}/tags/google.mitre.tactic.TA0011",
                    ],
                },
                "updateMask": "tags",
            },
            {
                "rule": {
                    "name": f"{instance_prefix}/rules/{rule_2_id}",
                    "tags": [],
                },
                "updateMask": "tags",
            },
        ]
    }

    # 3. Partial batch failure in `failedRequests` exits 1 instead of silently succeeding
    monkeypatch.setattr(
        rule_tags_mod,
        "chronicle_request",
        MagicMock(
            return_value={
                "failedRequests": {
                    "0": {"code": 7, "message": "permission denied"},
                }
            }
        ),
    )
    with pytest.raises(SystemExit) as exc_info:
        update_fn(ctx, dry_run=False)
    assert exc_info.value.code == 1


def test_duplicate_display_names_ignore_archived_and_rule_text_tag_overlap(
    dac_single_tenant_modules, tmp_path, monkeypatch
):
    """Active rules are preferred over archived/older duplicates, and YAML tags overlapping ruleTextTags do not drift."""
    import sys as _sys

    config_mod, main_mod = dac_single_tenant_modules
    rule_tags_mod = _sys.modules["rule_tags"]
    _rules_dir, rules_yaml = _configure_temp_paths(config_mod, tmp_path)

    monkeypatch.setenv("SECOPS_PROJECT_ID", "123456789012")
    monkeypatch.setenv("SECOPS_REGION", "eu")
    monkeypatch.setenv("SECOPS_CUSTOMER_ID", "00000000-0000-0000-0000-000000000001")

    instance_prefix = (
        "projects/123456789012/locations/eu/"
        "instances/00000000-0000-0000-0000-000000000001"
    )
    active_rule_id = "ru_aaaaaaaa-1111-2222-3333-444444444444"
    older_active_id = "ru_bbbbbbbb-1111-2222-3333-444444444444"
    archived_rule_id = "ru_cccccccc-1111-2222-3333-444444444444"

    mock_client = MagicMock()
    mock_client.instance_id = instance_prefix

    def _mock_list_rules(*, view="FULL", api_version=None, as_list=False):
        assert api_version == main_mod.APIVersion.V1ALPHA
        assert as_list is True
        if view == "FULL":
            return [
                {
                    "name": f"{instance_prefix}/rules/{active_rule_id}",
                    "displayName": "network_traffic_to_specific_country",
                    "text": MULTI_EVENT_RULE_TEXT,
                    "createTime": "2026-09-22T10:34:21Z",
                    "ruleTextTags": [
                        f"{instance_prefix}/tags/google.mitre.tactic.ta0001",
                    ],
                },
                {
                    "name": f"{instance_prefix}/rules/{older_active_id}",
                    "displayName": "network_traffic_to_specific_country",
                    "text": MULTI_EVENT_RULE_TEXT,
                    "createTime": "2025-10-06T17:58:48Z",
                    "ruleTextTags": [],
                },
                {
                    "name": f"{instance_prefix}/rules/{archived_rule_id}",
                    "displayName": "network_traffic_to_specific_country",
                    "text": MULTI_EVENT_RULE_TEXT,
                    "createTime": "2024-12-04T08:21:47Z",
                    "ruleTextTags": [],
                },
            ]
        if view == "CONFIG_ONLY":
            return [
                {
                    "name": f"{instance_prefix}/rules/{active_rule_id}",
                    "displayName": "network_traffic_to_specific_country",
                    "tags": [
                        f"{instance_prefix}/tags/google.mitre.tactic.ta0001",
                        f"{instance_prefix}/tags/google.mitre.tactic.ta0011",
                    ],
                },
                {
                    "name": f"{instance_prefix}/rules/{older_active_id}",
                    "displayName": "network_traffic_to_specific_country",
                },
                {
                    "name": f"{instance_prefix}/rules/{archived_rule_id}",
                    "displayName": "network_traffic_to_specific_country",
                    "archived": True,
                },
            ]
        raise AssertionError(f"Unexpected view: {view}")

    mock_client.list_rules.side_effect = _mock_list_rules
    mock_client.list_rule_deployments.return_value = {
        "ruleDeployments": [
            {
                "name": f"{instance_prefix}/rules/{active_rule_id}/deployment",
                "enabled": True,
                "alerting": True,
                "runFrequency": "LIVE_CUSTOMIZABLE",
            },
            {
                "name": f"{instance_prefix}/rules/{older_active_id}/deployment",
                "enabled": False,
                "alerting": False,
                "runFrequency": "LIVE",
            },
            {
                "name": f"{instance_prefix}/rules/{archived_rule_id}/deployment",
                "enabled": False,
                "alerting": False,
                "archived": True,
                "runFrequency": "LIVE",
            },
        ]
    }

    ctx = main_mod.AppContext()
    ctx.chronicle_client = mock_client

    # 1. pull-rules selects the newest active rule (enabled=True, LIVE_CUSTOMIZABLE)
    #    rather than being overwritten by the older or archived duplicate rules
    inspect.unwrap(main_mod.pull_rules.callback)(ctx)
    pulled_cfg = yaml.safe_load(rules_yaml.read_text(encoding="utf-8"))
    assert pulled_cfg["network_traffic_to_specific_country"] == {
        "enabled": True,
        "alerting": True,
        "archived": False,
        "run_frequency": "LIVE_CUSTOMIZABLE",
        "tags": ["google.mitre.tactic.ta0011"],
    }

    # 2. If YAML also lists `google.mitre.tactic.TA0001` (already present in ruleTextTags),
    #    update-rule-tags sees zero drift and makes no modifyRules call
    rules_yaml.write_text(
        yaml.safe_dump(
            {
                "network_traffic_to_specific_country": {
                    "enabled": True,
                    "tags": [
                        "google.mitre.tactic.TA0001",
                        "google.mitre.tactic.TA0011",
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    api_calls: list[dict] = []
    monkeypatch.setattr(
        rule_tags_mod,
        "chronicle_request",
        lambda _client, **kwargs: api_calls.append(kwargs) or {},
    )
    inspect.unwrap(main_mod.update_rule_tags.callback)(ctx, dry_run=False)
    assert api_calls == []

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
"""Unit tests for pipelines/detection-as-code-multitenant YAML schedule & deployment support."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

SAMPLE_MULTI_RULE = """rule MultiEventRule {
  meta:
    author = "Google"
  events:
    $e.metadata.event_type = "NETWORK_CONNECTION"
    $e.target.ip = $ip
  match:
    $ip over 30m
  condition:
    #e > 1
}
"""


def _setup_multitenant_repo(tmp_path: Path) -> Path:
    rules_dir = tmp_path / "rules"
    (rules_dir / "shared").mkdir(parents=True)
    (rules_dir / "tenants" / "alfa").mkdir(parents=True)
    (rules_dir / "tenants" / "bravo").mkdir(parents=True)

    shared_yaral = rules_dir / "shared" / "MultiEventRule.yaral"
    shared_yaral.write_text(SAMPLE_MULTI_RULE, encoding="utf-8")

    shared_yaml = rules_dir / "shared" / "MultiEventRule.yaml"
    shared_yaml.write_text(
        yaml.safe_dump(
            {
                "enabled": True,
                "alerting": True,
                "archived": False,
                "run_frequency": "LIVE_CUSTOMIZABLE",
                "schedule_customizations": {
                    "late_arriving_data_adjustment": "300s",
                },
            }
        ),
        encoding="utf-8",
    )

    # Tenant alfa symlinks .yaral and .yaml to shared
    (rules_dir / "tenants" / "alfa" / "MultiEventRule.yaral").symlink_to(
        "../../shared/MultiEventRule.yaral"
    )
    (rules_dir / "tenants" / "alfa" / "MultiEventRule.yaml").symlink_to(
        "../../shared/MultiEventRule.yaml"
    )

    # Tenant bravo overrides .yaml with HOURLY_CUSTOMIZABLE and 600s adjustment
    (rules_dir / "tenants" / "bravo" / "MultiEventRule.yaral").write_text(
        SAMPLE_MULTI_RULE, encoding="utf-8"
    )
    (rules_dir / "tenants" / "bravo" / "MultiEventRule.yaml").write_text(
        yaml.safe_dump(
            {
                "enabled": True,
                "alerting": False,
                "archived": False,
                "run_frequency": "HOURLY_CUSTOMIZABLE",
                "schedule_customizations": {
                    "ensure_enrichment_completeness": True,
                    "late_arriving_data_adjustment": "600s",
                },
            }
        ),
        encoding="utf-8",
    )
    return rules_dir


def test_load_repo_rule_config_precedence(dac_multitenant_modules, tmp_path):
    """Tenant YAML overrides shared YAML; shared YAML applies when symlinked."""
    common = dac_multitenant_modules["common"]
    rules_dir = _setup_multitenant_repo(tmp_path)

    alfa_cfg = common.load_repo_rule_config(rules_dir, "alfa", "MultiEventRule")
    assert alfa_cfg["run_frequency"] == "LIVE_CUSTOMIZABLE"
    assert alfa_cfg["schedule_customizations"] == {
        "late_arriving_data_adjustment": "300s"
    }

    bravo_cfg = common.load_repo_rule_config(rules_dir, "bravo", "MultiEventRule")
    assert bravo_cfg["alerting"] is False
    assert bravo_cfg["run_frequency"] == "HOURLY_CUSTOMIZABLE"
    assert bravo_cfg["schedule_customizations"] == {
        "ensure_enrichment_completeness": True,
        "late_arriving_data_adjustment": "600s",
    }


def test_compare_rules_detects_schedule_customization_drift(
    dac_multitenant_modules, tmp_path
):
    """compare_rules reports changed when scheduleCustomizations drift even if YARA-L text matches."""
    compare = dac_multitenant_modules["compare"]
    rules_dir = _setup_multitenant_repo(tmp_path)

    rule_id = "ru_11111111-2222-3333-4444-555555555555"
    mock_client = MagicMock()
    mock_client.list_rules.return_value = [
        {
            "name": f"projects/p/locations/eu/instances/i/rules/{rule_id}",
            "displayName": "MultiEventRule",
            "text": SAMPLE_MULTI_RULE,
        }
    ]
    mock_client.list_rule_deployments.return_value = [
        {
            "name": f"projects/p/locations/eu/instances/i/rules/{rule_id}/deployment",
            "enabled": True,
            "alerting": True,
            "archived": False,
            "runFrequency": "LIVE_CUSTOMIZABLE",
            "scheduleCustomizations": {
                "lateArrivingDataAdjustment": "300s",
            },
        }
    ]

    # Remote matches alfa exactly -> 0 changed
    alfa_deltas, _, _ = compare.compare_rules(mock_client, rules_dir, "alfa")
    assert alfa_deltas["missing"] == {}
    assert alfa_deltas["changed"] == {}
    assert alfa_deltas["extra"] == {}

    # Remote differs from bravo on alerting, runFrequency, and scheduleCustomizations -> changed
    bravo_deltas, _, _ = compare.compare_rules(mock_client, rules_dir, "bravo")
    assert "MultiEventRule" in bravo_deltas["changed"]
    changed_rule = bravo_deltas["changed"]["MultiEventRule"]
    assert changed_rule["text_changed"] is False
    assert changed_rule["deployment_changed"] is True

    # Protobuf3 default omission: local `ensure_enrichment_completeness: false` matches
    # Chronicle v1 response omitting `ensureEnrichmentCompleteness` -> 0 changed
    (rules_dir / "shared" / "MultiEventRule.yaml").write_text(
        yaml.safe_dump(
            {
                "enabled": True,
                "alerting": True,
                "archived": False,
                "run_frequency": "LIVE_CUSTOMIZABLE",
                "schedule_customizations": {
                    "ensure_enrichment_completeness": False,
                    "late_arriving_data_adjustment": "300.0s",
                },
            }
        ),
        encoding="utf-8",
    )
    alfa_deltas_false, _, _ = compare.compare_rules(mock_client, rules_dir, "alfa")
    assert alfa_deltas_false["changed"] == {}

    # Conversely, if remote has ensureEnrichmentCompleteness=True while local has False -> drift detected
    mock_client.list_rule_deployments.return_value[0]["scheduleCustomizations"][
        "ensureEnrichmentCompleteness"
    ] = True
    alfa_deltas_drift, _, _ = compare.compare_rules(mock_client, rules_dir, "alfa")
    assert "MultiEventRule" in alfa_deltas_drift["changed"]


def test_deploy_rules_sends_run_frequency_mask_and_sequences_archive(
    dac_multitenant_modules, tmp_path, monkeypatch
):
    """update_rule_deployment_v1 includes runFrequency mask with scheduleCustomizations and sequences archiving."""
    common = dac_multitenant_modules["common"]
    compare = dac_multitenant_modules["compare"]
    deploy = dac_multitenant_modules["deploy"]
    rules_dir = _setup_multitenant_repo(tmp_path)

    captured_calls: list[dict] = []

    def _fake_chronicle_request(_client, **kwargs):
        captured_calls.append(kwargs)
        return {}

    monkeypatch.setattr(common, "chronicle_request", _fake_chronicle_request)

    rule_id = "ru_11111111-2222-3333-4444-555555555555"
    mock_client = MagicMock()
    mock_client.list_rules.return_value = [
        {
            "name": f"projects/p/locations/eu/instances/i/rules/{rule_id}",
            "displayName": "MultiEventRule",
            "text": SAMPLE_MULTI_RULE,
        }
    ]
    mock_client.list_rule_deployments.return_value = [
        {
            "name": f"projects/p/locations/eu/instances/i/rules/{rule_id}/deployment",
            "enabled": True,
            "alerting": True,
            "archived": False,
            "runFrequency": "DAILY",
        }
    ]

    deltas, repo_rules, _ = compare.compare_rules(mock_client, rules_dir, "bravo")
    rule_details = deltas["changed"]["MultiEventRule"]
    repo_cfg = repo_rules["MultiEventRule"]["config"]

    deploy.update_rule(
        mock_client,
        rule_details,
        SAMPLE_MULTI_RULE,
        repo_cfg,
        {"gcpProject": "p", "customerId": "i", "region": "eu"},
        "prod",
    )
    assert len(captured_calls) == 1

    patch_call = captured_calls[0]
    assert patch_call["method"] == "PATCH"
    assert patch_call["endpoint_path"] == f"rules/{rule_id}/deployment"
    assert patch_call["api_version"] == common.APIVersion.V1
    mask_fields = set(patch_call["params"]["update_mask"].split(","))
    assert "runFrequency" in mask_fields
    assert "scheduleCustomizations" not in mask_fields
    assert patch_call["json"]["runFrequency"] == "HOURLY_CUSTOMIZABLE"
    assert patch_call["json"]["scheduleCustomizations"] == {
        "ensureEnrichmentCompleteness": True,
        "lateArrivingDataAdjustment": "600s",
    }

    # Verify archive sequencing: enabled=False must be PATCHed BEFORE archived=True
    captured_calls.clear()
    archive_cfg = {
        "enabled": False,
        "alerting": False,
        "archived": True,
        "run_frequency": "HOURLY_CUSTOMIZABLE",
    }
    deploy.apply_rule_deployment_config(
        mock_client,
        rule_id,
        archive_cfg,
        env="prod",
        current_rule=rule_details,
    )
    assert len(captured_calls) == 2
    assert captured_calls[0]["json"]["enabled"] is False
    assert "archived" not in captured_calls[0]["json"]
    assert captured_calls[1]["json"] == {"archived": True}


def test_pull_rules_writes_companion_yaml_with_license_header(
    dac_multitenant_modules, tmp_path
):
    """write_rule_config_file breaks symlinks and writes <RuleName>.yaml with Apache 2.0 header."""
    compare = dac_multitenant_modules["compare"]
    pull = dac_multitenant_modules["pull"]
    rules_dir = _setup_multitenant_repo(tmp_path)

    rule_id = "ru_00000000-1111-2222-3333-444444444444"
    mock_client = MagicMock()
    mock_client.list_rules.return_value = [
        {
            "name": f"projects/p/locations/eu/instances/i/rules/{rule_id}",
            "displayName": "MultiEventRule",
            "text": SAMPLE_MULTI_RULE,
        }
    ]
    mock_client.list_rule_deployments.return_value = [
        {
            "name": f"projects/p/locations/eu/instances/i/rules/{rule_id}/deployment",
            "enabled": True,
            "alerting": True,
            "runFrequency": "LIVE_CUSTOMIZABLE",
            "scheduleCustomizations": {
                "lateArrivingDataAdjustment": "450s",
            },
        }
    ]

    alfa_deltas, _, _ = compare.compare_rules(mock_client, rules_dir, "alfa")
    assert "MultiEventRule" in alfa_deltas["changed"]
    pull.write_rule_config_file(
        rules_dir,
        "alfa",
        "MultiEventRule",
        alfa_deltas["changed"]["MultiEventRule"],
    )

    yaml_path = rules_dir / "tenants" / "alfa" / "MultiEventRule.yaml"
    assert yaml_path.is_file()
    assert not yaml_path.is_symlink()
    raw_yaml = yaml_path.read_text(encoding="utf-8")
    assert raw_yaml.startswith("# Copyright ")
    parsed = yaml.safe_load(raw_yaml)
    assert parsed == {
        "enabled": True,
        "alerting": True,
        "archived": False,
        "run_frequency": "LIVE_CUSTOMIZABLE",
        "schedule_customizations": {
            "late_arriving_data_adjustment": "450s",
        },
    }


def test_verify_rules_and_code_quality_checks(
    dac_multitenant_modules, tmp_path, monkeypatch
):
    """verify_tenant_rules, check_rule_configs, and check_live validate YAML sidecars."""
    common = dac_multitenant_modules["common"]
    verify = dac_multitenant_modules["verify"]
    check_configs = dac_multitenant_modules["check_configs"]
    check_live = dac_multitenant_modules["check_live"]

    rules_dir = _setup_multitenant_repo(tmp_path)
    tables_dir = tmp_path / "tables"

    # 1. Offline code-quality check succeeds on valid repo
    assert check_configs.check_rule_configs(rules_dir, strict=True) == 0

    # Orphan .yaml without matching .yaral is flagged
    orphan_yaml = rules_dir / "tenants" / "bravo" / "OrphanRule.yaml"
    orphan_yaml.write_text("enabled: true\n", encoding="utf-8")
    assert check_configs.check_rule_configs(rules_dir, strict=False) == 1
    orphan_yaml.unlink()

    # 2. Live tenant symlink check catches symlinked .yaral and .yaml in live tenant
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(check_live, "get_live_tenant_ids", lambda: {"alfa"})
    with pytest.raises(SystemExit) as exc_info:
        check_live.check_live(enforce=True)
    assert exc_info.value.code == 3

    # 3. Remote verify_tenant_rules via verifyRuleText
    monkeypatch.setattr(
        common,
        "verify_rule_text_v1alpha",
        MagicMock(
            return_value={
                "success": True,
                "allowedRunFrequencies": ["LIVE_CUSTOMIZABLE", "HOURLY_CUSTOMIZABLE"],
            }
        ),
    )
    verified, errors = verify.verify_tenant_rules(
        MagicMock(), rules_dir, tables_dir, "alfa", strict=True
    )
    assert (verified, errors) == (1, 0)

    # Legacy DAILY warns (0 errors) without --strict, fails (1 error) with --strict
    (rules_dir / "tenants" / "bravo" / "MultiEventRule.yaml").write_text(
        yaml.safe_dump(
            {
                "enabled": True,
                "alerting": True,
                "archived": False,
                "run_frequency": "DAILY",
            }
        ),
        encoding="utf-8",
    )
    assert verify.verify_tenant_rules(
        MagicMock(), rules_dir, tables_dir, "bravo", strict=False
    ) == (1, 0)
    assert verify.verify_tenant_rules(
        MagicMock(), rules_dir, tables_dir, "bravo", strict=True
    ) == (0, 1)


def test_multitenant_rule_tags_compare_deploy_and_pull(
    dac_multitenant_modules, tmp_path, monkeypatch
):
    """Verify v1alpha rule tag validation, drift detection, batch deploy, and pull sync."""
    common = dac_multitenant_modules["common"]
    compare = dac_multitenant_modules["compare"]
    deploy = dac_multitenant_modules["deploy"]
    pull = dac_multitenant_modules["pull"]
    check_configs = dac_multitenant_modules["check_configs"]

    rules_dir = _setup_multitenant_repo(tmp_path)

    # 1. Invalid tag in companion YAML is caught by check_rule_configs
    (rules_dir / "tenants" / "bravo" / "MultiEventRule.yaml").write_text(
        yaml.safe_dump(
            {
                "enabled": True,
                "alerting": False,
                "archived": False,
                "run_frequency": "LIVE_CUSTOMIZABLE",
                "tags": ["invalid-hyphen-custom-tag"],
            }
        ),
        encoding="utf-8",
    )
    assert check_configs.check_rule_configs(rules_dir, strict=False) == 1

    # Configure valid tags on shared (inherited by alfa) and tenant bravo (plus a missing rule)
    (rules_dir / "shared" / "MultiEventRule.yaml").write_text(
        yaml.safe_dump(
            {
                "enabled": True,
                "alerting": True,
                "archived": False,
                "run_frequency": "LIVE_CUSTOMIZABLE",
                "tags": ["soc_tier1", "google.mitre.tactic.TA0011"],
                "schedule_customizations": {
                    "late_arriving_data_adjustment": "300s",
                },
            }
        ),
        encoding="utf-8",
    )
    (rules_dir / "tenants" / "bravo" / "MultiEventRule.yaml").write_text(
        yaml.safe_dump(
            {
                "enabled": True,
                "alerting": True,
                "archived": False,
                "run_frequency": "LIVE_CUSTOMIZABLE",
                "tags": ["soc_tier2", "google.mitre.technique.T1078"],
                "schedule_customizations": {
                    "late_arriving_data_adjustment": "300s",
                },
            }
        ),
        encoding="utf-8",
    )
    (rules_dir / "tenants" / "bravo" / "NewRule.yaral").write_text(
        SAMPLE_MULTI_RULE.replace("MultiEventRule", "NewRule"), encoding="utf-8"
    )
    (rules_dir / "tenants" / "bravo" / "NewRule.yaml").write_text(
        yaml.safe_dump(
            {
                "enabled": True,
                "alerting": True,
                "archived": False,
                "run_frequency": "LIVE_CUSTOMIZABLE",
                "tags": ["soc_tier2"],
            }
        ),
        encoding="utf-8",
    )
    assert check_configs.check_rule_configs(rules_dir, strict=True) == 0

    rule_id = "ru_11111111-2222-3333-4444-555555555555"
    new_rule_id = "ru_22222222-3333-4444-5555-666666666666"
    instance_prefix = "projects/p/locations/eu/instances/i"

    mock_client = MagicMock()
    mock_client.list_rules.return_value = [
        {
            "name": f"{instance_prefix}/rules/{rule_id}",
            "displayName": "MultiEventRule",
            "text": SAMPLE_MULTI_RULE,
            "tags": [
                f"{instance_prefix}/tags/soc_tier1",
                f"{instance_prefix}/tags/google.mitre.tactic.ta0011",
                f"{instance_prefix}/tags/google.mitre.tactic.ta0001",
            ],
            "ruleTextTags": [
                f"{instance_prefix}/tags/google.mitre.tactic.TA0001",
            ],
        }
    ]
    mock_client.list_rule_deployments.return_value = [
        {
            "name": f"{instance_prefix}/rules/{rule_id}/deployment",
            "enabled": True,
            "alerting": True,
            "archived": False,
            "runFrequency": "LIVE_CUSTOMIZABLE",
            "scheduleCustomizations": {
                "lateArrivingDataAdjustment": "300s",
            },
        }
    ]

    # 2. Tenant alfa has 0 drift (ruleTextTags excluded & google.mitre.* case-insensitive)
    alfa_deltas, _, _ = compare.compare_rules(mock_client, rules_dir, "alfa")
    assert alfa_deltas["changed"] == {}

    # 2b. Even if YAML explicitly includes `google.mitre.tactic.TA0001` (which is also in
    #     ruleTextTags), compare_rules does not report false-positive tag drift
    (rules_dir / "shared" / "MultiEventRule.yaml").write_text(
        yaml.safe_dump(
            {
                "enabled": True,
                "alerting": True,
                "archived": False,
                "run_frequency": "LIVE_CUSTOMIZABLE",
                "tags": [
                    "soc_tier1",
                    "google.mitre.tactic.TA0001",
                    "google.mitre.tactic.TA0011",
                ],
                "schedule_customizations": {
                    "late_arriving_data_adjustment": "300s",
                },
            }
        ),
        encoding="utf-8",
    )
    alfa_deltas_overlap, _, _ = compare.compare_rules(mock_client, rules_dir, "alfa")
    assert alfa_deltas_overlap["changed"] == {}

    # 3. Tenant bravo has tag-only drift on MultiEventRule + missing NewRule
    bravo_deltas, _, _ = compare.compare_rules(mock_client, rules_dir, "bravo")
    assert "NewRule" in bravo_deltas["missing"]
    assert "MultiEventRule" in bravo_deltas["changed"]
    assert bravo_deltas["changed"]["MultiEventRule"]["text_changed"] is False
    assert bravo_deltas["changed"]["MultiEventRule"]["deployment_changed"] is False
    assert bravo_deltas["changed"]["MultiEventRule"]["tags_changed"] is True

    # 4. deploy_tenant_rules creates NewRule, auto-creates custom tag `soc_tier2`,
    #    and batches both NewRule and MultiEventRule in a single `rules:modifyRules` call
    monkeypatch.setattr(
        common,
        "chronicle_paginated_request",
        MagicMock(return_value=[{"name": f"{instance_prefix}/tags/soc_tier1"}]),
    )
    captured_requests: list[dict] = []

    def _fake_request(_client, **kwargs):
        captured_requests.append(kwargs)
        if kwargs["endpoint_path"] == "rules" and kwargs["method"] == "POST":
            return {"name": f"{instance_prefix}/rules/{new_rule_id}"}
        if kwargs["endpoint_path"] == "rules:modifyRules":
            return {"ruleUpdates": [{"tagsUpdated": True}, {"tagsUpdated": True}]}
        return {}

    monkeypatch.setattr(common, "chronicle_request", _fake_request)
    tenant_details = {"gcpProject": "p", "customerId": "i", "region": "eu"}
    _, had_errors = deploy.deploy_tenant_rules(
        mock_client, rules_dir, "bravo", tenant_details, env="prod"
    )
    assert had_errors is False

    tag_creates = [c for c in captured_requests if c["endpoint_path"] == "tags"]
    assert len(tag_creates) == 1
    assert tag_creates[0]["params"] == {"tagId": "soc_tier2"}

    modify_calls = [
        c for c in captured_requests if c["endpoint_path"] == "rules:modifyRules"
    ]
    assert len(modify_calls) == 1
    assert modify_calls[0]["api_version"] == common.APIVersion.V1ALPHA
    assert modify_calls[0]["json"] == {
        "requests": [
            {
                "rule": {
                    "name": f"{instance_prefix}/rules/{new_rule_id}",
                    "tags": [f"{instance_prefix}/tags/soc_tier2"],
                },
                "updateMask": "tags",
            },
            {
                "rule": {
                    "name": f"{instance_prefix}/rules/{rule_id}",
                    "tags": [
                        f"{instance_prefix}/tags/soc_tier2",
                        f"{instance_prefix}/tags/google.mitre.technique.T1078",
                    ],
                },
                "updateMask": "tags",
            },
        ]
    }

    # 5. Partial failure in `failedRequests` surfaces tenant_errors=True
    monkeypatch.setattr(
        common,
        "chronicle_request",
        MagicMock(
            return_value={
                "name": f"{instance_prefix}/rules/{new_rule_id}",
                "failedRequests": {"0": {"code": 7, "message": "denied"}},
            }
        ),
    )
    _, had_errors_fail = deploy.deploy_tenant_rules(
        mock_client, rules_dir, "bravo", tenant_details, env="prod"
    )
    assert had_errors_fail is True

    # 6. pull_rules write_rule_config_file persists API-applied tags (excluding ruleTextTags)
    pull.write_rule_config_file(
        rules_dir,
        "bravo",
        "MultiEventRule",
        bravo_deltas["changed"]["MultiEventRule"],
    )
    pulled_yaml = yaml.safe_load(
        (rules_dir / "tenants" / "bravo" / "MultiEventRule.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert pulled_yaml["tags"] == [
        "soc_tier1",
        "google.mitre.tactic.ta0011",
    ]

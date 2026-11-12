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

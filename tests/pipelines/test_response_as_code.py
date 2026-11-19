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
"""Unit tests for pipelines/response-as-code local playbook storage helpers."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _sample_workflow_payload(
    name: str = "TriageAlert", category: str = "Standard"
) -> dict:
    return {
        "id": 1,
        "identifier": "00000000-1111-4222-8333-444444444444",
        "name": name,
        "description": "Sample playbook description",
        "playbookType": "REGULAR",
        "priority": 2,
        "isDebugMode": False,
        "version": 1,
        "trigger": {
            "id": 10,
            "identifier": "00000000-1111-4222-8333-555555555555",
            "type": "ALERT",
            "logicalOperator": "AND",
            "conditions": [],
        },
        "steps": [],
        "stepsRelations": [],
        "isEnabled": True,
        "categoryName": category,
        "environments": ["*"],
        "modificationTimeUnixTimeInMs": "1700000000000",
        "overviewTemplates": [],
        "permissions": [],
        "entityAccessLevel": [],
        "defaultAccessLevel": [],
        "creationSource": "USER",
        "hasRestrictedEnvironments": False,
        "executionScope": "ALL",
    }


def _make_response_manager(manager_mod):
    mgr = manager_mod.ResponseManager.__new__(manager_mod.ResponseManager)
    mgr.client = MagicMock()
    return mgr


def test_store_playbook_and_readme_write_expected_files(
    rac_modules, tmp_path: Path, monkeypatch
):
    """Verify valid playbooks and root README are written under Playbooks/."""
    models_mod = rac_modules["models"]
    utils_mod = rac_modules["utils"]
    manager_mod = rac_modules["manager"]

    workdir = tmp_path / "repo"
    workdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(utils_mod, "WD", str(workdir))

    workflow = models_mod.Workflow(
        _sample_workflow_payload(name="EnrichHost", category="Enrichment")
    )
    mgr = _make_response_manager(manager_mod)
    mgr.store_playbook(workflow)
    mgr.update_readme("# Playbooks Index\n", "Playbooks")

    playbook_dir = workdir / "Playbooks" / "Enrichment" / "EnrichHost"
    assert (playbook_dir / "EnrichHost.json").is_file()
    assert (playbook_dir / "README.md").is_file()
    assert (workdir / "Playbooks" / "README.md").read_text(encoding="utf-8") == (
        "# Playbooks Index\n"
    )

    loaded = list(utils_mod.get_local_playbooks())
    assert len(loaded) == 1
    assert loaded[0].name == "EnrichHost"
    assert loaded[0].category == "Enrichment"


@pytest.mark.parametrize(
    ("category", "name"),
    [
        ("../../../../outside", "SamplePlaybook"),
        ("../.github/workflows", "SamplePlaybook"),
        ("Standard", "../SamplePlaybook"),
        ("Standard/Nested", "SamplePlaybook"),
        ("Standard", "Nested/Playbook"),
        ("..", "SamplePlaybook"),
        ("Standard", ".."),
        ("", "SamplePlaybook"),
        ("   ", "SamplePlaybook"),
        ("Standard", ""),
    ],
)
def test_store_and_push_playbook_reject_invalid_segments(
    rac_modules, tmp_path: Path, monkeypatch, category: str, name: str
):
    """Verify category and playbook names cannot traverse directories or contain separators."""
    models_mod = rac_modules["models"]
    utils_mod = rac_modules["utils"]
    manager_mod = rac_modules["manager"]

    workdir = tmp_path / "workspace" / "repo"
    workdir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(utils_mod, "WD", str(workdir))

    workflow = models_mod.Workflow(
        _sample_workflow_payload(name=name, category=category)
    )
    mgr = _make_response_manager(manager_mod)

    with pytest.raises(ValueError):
        mgr.store_playbook(workflow)

    with pytest.raises(ValueError):
        utils_mod.push_playbook(workflow)

    assert not (tmp_path / "outside").exists()
    assert not (workdir / ".github").exists()


def test_update_objects_and_read_helpers_confine_paths_to_working_directory(
    rac_modules, tmp_path: Path, monkeypatch
):
    """Verify update_objects and get_file_objects_from_path enforce working-directory confinement."""
    models_mod = rac_modules["models"]
    utils_mod = rac_modules["utils"]

    workdir = tmp_path / "workspace" / "repo"
    outside_dir = tmp_path / "outside"
    workdir.mkdir(parents=True, exist_ok=True)
    outside_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(utils_mod, "WD", str(workdir))

    sample_file = models_mod.File("item.json", b"{}")

    invalid_base_paths = [
        "Playbooks/../../../../outside/sub",
        "Playbooks/../other",
        "../outside",
        str(outside_dir),
    ]
    for bad_base in invalid_base_paths:
        with pytest.raises(ValueError):
            utils_mod.update_objects([sample_file], base_path=bad_base)
        with pytest.raises(ValueError):
            utils_mod.get_file_objects_from_path(bad_base)

    assert list(outside_dir.iterdir()) == []

    # Symlinked subdirectory pointing outside WD must also be rejected.
    (workdir / "Playbooks").mkdir(parents=True, exist_ok=True)
    (workdir / "Playbooks" / "LinkedCat").symlink_to(
        outside_dir, target_is_directory=True
    )
    with pytest.raises(ValueError):
        utils_mod.update_objects([sample_file], base_path="Playbooks/LinkedCat/Sub")

    # Replacing content at WD root via "." must be refused.
    sentinel = workdir / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError):
        utils_mod.update_objects(
            [sample_file], base_path=".", replace_content_in_base_path=True
        )
    assert sentinel.is_file()

    # Escaping file paths inside files list must be skipped without writing outside target dir.
    target_sub = workdir / "Playbooks" / "ValidCat" / "ValidItem"
    target_sub.mkdir(parents=True, exist_ok=True)
    (target_sub / "linked_out.json").symlink_to(outside_dir / "linked_out.json")
    utils_mod.update_objects(
        [
            models_mod.File("../escaped.json", b"{}"),
            models_mod.File("linked_out.json", b"{}"),
            models_mod.File("valid.json", b'{"ok": true}'),
        ],
        base_path="Playbooks/ValidCat/ValidItem",
    )
    assert not (workdir / "Playbooks" / "ValidCat" / "escaped.json").exists()
    assert not (outside_dir / "linked_out.json").exists()
    assert (target_sub / "valid.json").is_file()

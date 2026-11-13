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
"""Security and workflow regression tests for pipelines/parsers-as-code."""

import os
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = (
    REPO_ROOT
    / "pipelines"
    / "parsers-as-code"
    / ".github"
    / "workflows"
    / "secops.yaml"
)


def _load_commit_and_push_step() -> dict:
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["secops-pr"]["steps"]
    for step in steps:
        if step.get("name") == "Commit and push event file changes":
            return step
    raise AssertionError("Step 'Commit and push event file changes' not found")


def _init_git_fixture(tmp_path: Path, branch_name: str = "feat/legit-branch") -> Path:
    remote_dir = tmp_path / "remote.git"
    seed_dir = tmp_path / "seed"
    runner_dir = tmp_path / "runner"
    home_dir = tmp_path / "home"
    for d in (remote_dir, seed_dir, runner_dir, home_dir):
        d.mkdir(parents=True, exist_ok=True)

    base_env = {
        **os.environ,
        "HOME": str(home_dir),
        "GIT_CONFIG_GLOBAL": str(home_dir / ".gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
    }

    def git(cwd: Path, *args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=base_env,
            check=True,
            capture_output=True,
            text=True,
        )

    git(remote_dir, "init", "--bare", "-b", "main")
    git(seed_dir, "init", "-b", "main")
    git(seed_dir, "config", "user.name", "seed")
    git(seed_dir, "config", "user.email", "seed@example.com")
    git(seed_dir, "remote", "add", "origin", f"file://{remote_dir}")

    events_file = seed_dir / "parsers" / "TEST_LOG" / "events" / "logs.yaml"
    events_file.parent.mkdir(parents=True, exist_ok=True)
    events_file.write_text("events: []\n", encoding="utf-8")
    git(seed_dir, "add", ".")
    git(seed_dir, "commit", "-m", "initial")
    git(seed_dir, "push", "origin", "main")

    git(seed_dir, "checkout", "-b", branch_name)
    events_file.write_text("events:\n  - id: 1\n", encoding="utf-8")
    git(seed_dir, "commit", "-am", "pr change")
    git(seed_dir, "push", "origin", f"HEAD:refs/heads/{branch_name}")

    git(runner_dir, "init")
    git(runner_dir, "remote", "add", "origin", f"file://{remote_dir}")
    git(runner_dir, "fetch", "--depth=1", "origin", f"refs/heads/{branch_name}")
    git(runner_dir, "checkout", "--detach", "FETCH_HEAD")

    runner_events = runner_dir / "parsers" / "TEST_LOG" / "events" / "logs.yaml"
    runner_events.write_text("events:\n  - id: 2\n", encoding="utf-8")
    return runner_dir


def test_workflow_never_interpolates_head_ref_in_run_blocks():
    """Verify ${{ github.head_ref }} is bound via env: rather than interpolated in run:."""
    raw_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    workflow = yaml.safe_load(raw_text)
    for job_name, job in workflow.get("jobs", {}).items():
        for step in job.get("steps", []):
            run_script = step.get("run", "")
            assert "github.head_ref" not in run_script, (
                f"Job '{job_name}' step '{step.get('name')}' interpolates github.head_ref "
                "directly inside a run: block"
            )

    step = _load_commit_and_push_step()
    assert step.get("env", {}).get("HEAD_REF") == "${{ github.head_ref }}"
    assert "${{" not in step["run"]


def test_commit_and_push_step_succeeds_for_valid_branch(tmp_path: Path):
    """Verify the workflow shell block commits, rebases, and pushes to a valid PR branch."""
    step = _load_commit_and_push_step()
    branch_name = "feat/parser-update"
    runner_dir = _init_git_fixture(tmp_path, branch_name=branch_name)
    home_dir = tmp_path / "home"

    res = subprocess.run(
        ["bash", "-eo", "pipefail", "-c", step["run"]],
        cwd=runner_dir,
        env={
            **os.environ,
            "HOME": str(home_dir),
            "GIT_CONFIG_GLOBAL": str(home_dir / ".gitconfig"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "HEAD_REF": branch_name,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Expected exit 0, got {res.returncode}: {res.stderr}"


def test_commit_and_push_step_blocks_shell_and_option_injection(tmp_path: Path):
    """Verify shell metacharacters and leading-dash git options in HEAD_REF never execute."""
    step = _load_commit_and_push_step()
    canary = tmp_path / "pwned"

    payloads = [
        f"x;touch${{IFS}}{canary};true",
        f'a"b;touch {canary};true',
        f"--upload-pack=touch {canary}",
        "-leading-dash",
        "foo:refs/heads/main",
        "",
    ]

    for idx, payload in enumerate(payloads):
        case_dir = tmp_path / f"case_{idx}"
        runner_dir = _init_git_fixture(case_dir)
        home_dir = case_dir / "home"

        res = subprocess.run(
            ["bash", "-eo", "pipefail", "-c", step["run"]],
            cwd=runner_dir,
            env={
                **os.environ,
                "HOME": str(home_dir),
                "GIT_CONFIG_GLOBAL": str(home_dir / ".gitconfig"),
                "GIT_CONFIG_NOSYSTEM": "1",
                "HEAD_REF": payload,
            },
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode != 0, f"Payload {payload!r} unexpectedly succeeded"
        assert not canary.exists(), (
            f"Command/option injection fired for payload {payload!r}"
        )

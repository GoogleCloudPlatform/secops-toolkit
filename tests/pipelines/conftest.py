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
"""Shared test helpers and optional dependency shims for pipeline unit tests."""

import enum
import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SINGLE_TENANT_SCRIPTS_DIR = REPO_ROOT / "pipelines" / "detection-as-code" / "scripts"
MULTITENANT_DIR = REPO_ROOT / "pipelines" / "detection-as-code-multitenant"
MULTITENANT_DEPLOYMENT_DIR = MULTITENANT_DIR / "pipelines" / "deployment"
MULTITENANT_QUALITY_DIR = MULTITENANT_DIR / "pipelines" / "code-quality"


def _new_shim_module(name: str, *, is_package: bool = False) -> types.ModuleType:
    """Create a synthetic ModuleType with a valid ModuleSpec so find_spec never fails."""
    mod = types.ModuleType(name)
    mod.__spec__ = importlib.machinery.ModuleSpec(
        name, loader=None, is_package=is_package
    )
    if is_package:
        mod.__path__ = []  # type: ignore[attr-defined]
    return mod


def _ensure_optional_pipeline_dependencies() -> None:
    """Install lightweight shims only when optional pipeline packages are absent."""
    if "dotenv" not in sys.modules and importlib.util.find_spec("dotenv") is None:
        dotenv_mod = _new_shim_module("dotenv")
        dotenv_mod.load_dotenv = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
        sys.modules["dotenv"] = dotenv_mod

    if (
        "argcomplete" not in sys.modules
        and importlib.util.find_spec("argcomplete") is None
    ):
        argcomplete_mod = _new_shim_module("argcomplete")
        argcomplete_mod.autocomplete = lambda *_args, **_kwargs: None  # type: ignore[attr-defined]
        sys.modules["argcomplete"] = argcomplete_mod

    if "click" not in sys.modules and importlib.util.find_spec("click") is None:
        click_mod = _new_shim_module("click")

        def _identity_decorator(*_dargs, **_dkwargs):
            def _wrap(fn):
                fn.callback = fn
                fn.command = lambda *_ca, **_ckw: _identity_decorator()
                return fn

            return _wrap

        click_mod.group = _identity_decorator  # type: ignore[attr-defined]
        click_mod.option = _identity_decorator  # type: ignore[attr-defined]
        click_mod.make_pass_decorator = (  # type: ignore[attr-defined]
            lambda _cls, **_kw: lambda fn: fn
        )
        click_mod.echo = print  # type: ignore[attr-defined]
        sys.modules["click"] = click_mod

    if "ruamel.yaml" not in sys.modules and importlib.util.find_spec("ruamel") is None:
        ruamel_pkg = _new_shim_module("ruamel", is_package=True)
        ruamel_yaml_mod = _new_shim_module("ruamel.yaml")

        class _YAMLShim:
            def __init__(self, **_kwargs):
                self.preserve_quotes = False

            def load(self, stream):
                return yaml.safe_load(stream)

            def dump(self, data, stream):
                yaml.safe_dump(data, stream, sort_keys=False)

        ruamel_yaml_mod.YAML = _YAMLShim  # type: ignore[attr-defined]
        ruamel_pkg.yaml = ruamel_yaml_mod  # type: ignore[attr-defined]
        sys.modules["ruamel"] = ruamel_pkg
        sys.modules["ruamel.yaml"] = ruamel_yaml_mod

    if "pydantic" not in sys.modules and importlib.util.find_spec("pydantic") is None:
        pydantic_mod = _new_shim_module("pydantic")

        class _BaseModel:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        pydantic_mod.BaseModel = _BaseModel  # type: ignore[attr-defined]
        pydantic_mod.Field = lambda *_a, **_kw: None  # type: ignore[attr-defined]
        pydantic_mod.ConfigDict = dict  # type: ignore[attr-defined]
        sys.modules["pydantic"] = pydantic_mod

    if "secops" not in sys.modules and importlib.util.find_spec("secops") is None:

        class _APIVersion(enum.StrEnum):
            V1 = "v1"
            V1ALPHA = "v1alpha"
            V1BETA = "v1beta"

        class _SecOpsError(Exception):
            pass

        class _APIError(_SecOpsError):
            pass

        secops_pkg = _new_shim_module("secops", is_package=True)
        secops_pkg.SecOpsClient = MagicMock  # type: ignore[attr-defined]

        auth_mod = _new_shim_module("secops.auth")
        auth_mod.RetryConfig = MagicMock  # type: ignore[attr-defined]

        exceptions_mod = _new_shim_module("secops.exceptions")
        exceptions_mod.SecOpsError = _SecOpsError  # type: ignore[attr-defined]
        exceptions_mod.APIError = _APIError  # type: ignore[attr-defined]

        chronicle_pkg = _new_shim_module("secops.chronicle", is_package=True)
        chronicle_pkg.ChronicleClient = MagicMock  # type: ignore[attr-defined]

        client_mod = _new_shim_module("secops.chronicle.client")
        client_mod.ChronicleClient = MagicMock  # type: ignore[attr-defined]

        models_mod = _new_shim_module("secops.chronicle.models")
        models_mod.APIVersion = _APIVersion  # type: ignore[attr-defined]

        dt_mod = _new_shim_module("secops.chronicle.data_table")
        dt_mod.DataTableColumnType = MagicMock()  # type: ignore[attr-defined]

        utils_pkg = _new_shim_module("secops.chronicle.utils", is_package=True)
        req_mod = _new_shim_module("secops.chronicle.utils.request_utils")
        req_mod.chronicle_request = MagicMock()  # type: ignore[attr-defined]
        req_mod.chronicle_paginated_request = MagicMock()  # type: ignore[attr-defined]

        sys.modules["secops"] = secops_pkg
        sys.modules["secops.auth"] = auth_mod
        sys.modules["secops.exceptions"] = exceptions_mod
        sys.modules["secops.chronicle"] = chronicle_pkg
        sys.modules["secops.chronicle.client"] = client_mod
        sys.modules["secops.chronicle.models"] = models_mod
        sys.modules["secops.chronicle.data_table"] = dt_mod
        sys.modules["secops.chronicle.utils"] = utils_pkg
        sys.modules["secops.chronicle.utils.request_utils"] = req_mod


def load_module_from_path(
    module_name: str, file_path: Path, extra_sys_path: Path | None = None
) -> Any:
    """Dynamically load a Python module from an explicit file path."""
    _ensure_optional_pipeline_dependencies()
    added_path = False
    if extra_sys_path is not None and str(extra_sys_path) not in sys.path:
        sys.path.insert(0, str(extra_sys_path))
        added_path = True
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        if added_path:
            sys.path.remove(str(extra_sys_path))


@pytest.fixture(scope="module")
def dac_single_tenant_modules():
    """Load config.py and main.py from pipelines/detection-as-code/scripts."""
    _ensure_optional_pipeline_dependencies()
    sys.path.insert(0, str(SINGLE_TENANT_SCRIPTS_DIR))
    try:
        config_mod = load_module_from_path(
            "config", SINGLE_TENANT_SCRIPTS_DIR / "config.py"
        )
        load_module_from_path(
            "data_tables", SINGLE_TENANT_SCRIPTS_DIR / "data_tables.py"
        )
        load_module_from_path("rule_tags", SINGLE_TENANT_SCRIPTS_DIR / "rule_tags.py")
        load_module_from_path("rule_tags", SINGLE_TENANT_SCRIPTS_DIR / "rule_tags.py")
        main_mod = load_module_from_path(
            "dac_single_main", SINGLE_TENANT_SCRIPTS_DIR / "main.py"
        )
        return config_mod, main_mod
    finally:
        sys.path.remove(str(SINGLE_TENANT_SCRIPTS_DIR))


@pytest.fixture(scope="module")
def dac_multitenant_modules():
    """Load deployment and code-quality modules from pipelines/detection-as-code-multitenant."""
    _ensure_optional_pipeline_dependencies()
    sys.path.insert(0, str(MULTITENANT_DEPLOYMENT_DIR))
    try:
        common_mod = load_module_from_path(
            "deployment_common", MULTITENANT_DEPLOYMENT_DIR / "deployment_common.py"
        )
        compare_mod = load_module_from_path(
            "mt_compare_rules", MULTITENANT_DEPLOYMENT_DIR / "compare_rules.py"
        )
        deploy_mod = load_module_from_path(
            "mt_deploy_rules", MULTITENANT_DEPLOYMENT_DIR / "deploy_rules.py"
        )
        pull_mod = load_module_from_path(
            "mt_pull_rules", MULTITENANT_DEPLOYMENT_DIR / "pull_rules.py"
        )
        verify_mod = load_module_from_path(
            "mt_verify_rules", MULTITENANT_DEPLOYMENT_DIR / "verify_rules.py"
        )
        check_configs_mod = load_module_from_path(
            "mt_check_rule_configs", MULTITENANT_QUALITY_DIR / "check_rule_configs.py"
        )
        check_live_mod = load_module_from_path(
            "mt_check_live_tenants", MULTITENANT_QUALITY_DIR / "check_live_tenants.py"
        )
        return {
            "common": common_mod,
            "compare": compare_mod,
            "deploy": deploy_mod,
            "pull": pull_mod,
            "verify": verify_mod,
            "check_configs": check_configs_mod,
            "check_live": check_live_mod,
        }
    finally:
        sys.path.remove(str(MULTITENANT_DEPLOYMENT_DIR))

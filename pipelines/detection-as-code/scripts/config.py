#! /usr/bin/env python3
# Copyright 2025 Google LLC
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

import os
from pathlib import Path
import logging
import sys
from dotenv import load_dotenv

load_dotenv()


# --- Configuration ---
# Environment variables are checked first.
def get_env_variable(name: str, default: str | None = None) -> str:
    """Get an environment variable or raise an error if it's not set."""
    value = os.getenv(name)
    if not value:
        if default:
            return default
        raise ValueError(f"Environment variable {name} not set.")
    return value


CUSTOMER_ID = get_env_variable("SECOPS_CUSTOMER_ID")
PROJECT_ID = get_env_variable("SECOPS_PROJECT_ID")
REGION = get_env_variable("SECOPS_REGION")
LOGGING_LEVEL = get_env_variable("LOGGING_LEVEL", "INFO").upper()

# --- Path Configuration ---
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_RULES_DIR = SCRIPT_DIR.parent / "rules"
SECOPS_RULES_CONFIG_PATH = SCRIPT_DIR.parent / "secops_rules.yaml"
SECOPS_REFERENCE_LISTS_CONFIG_PATH = SCRIPT_DIR.parent / "secops_reference_lists.yaml"
SECOPS_DATA_TABLES_CONFIG_PATH = SCRIPT_DIR.parent / "secops_data_tables.yaml"

DATA_TABLES_DIR = SCRIPT_DIR.parent / "data_tables"
DATA_TABLE_CONFIG_FILE = SCRIPT_DIR.parent / "secops_data_tables.yaml"

#! /usr/bin/env python3
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

import os
from dotenv import load_dotenv

load_dotenv()

# --- Environment Variables ---
# These variables must be set in the environment where the script is run.
SECOPS_CUSTOMER_ID = os.environ.get("SECOPS_CUSTOMER_ID")
SECOPS_PROJECT_ID = os.environ.get("SECOPS_PROJECT_ID")
SECOPS_REGION = os.environ.get("SECOPS_REGION")

# --- Application Constants ---
# Scopes for Google Cloud authentication
SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

# Filesystem paths and filenames
PARSERS_ROOT_DIR = "./parsers"
PARSER_CONFIG_FILENAME = "parser.conf"
PARSER_EXT_CONFIG_FILENAME = "parser_extension.conf"
PARSER_YAML_FILENAME = "parser.yaml"
LOGS_FOLDER_NAME = "logs"
EVENTS_FOLDER_NAME = "events"

# Environment variable to get the path to the GitHub Actions output file
GITHUB_OUTPUT_FILE = os.getenv('GITHUB_OUTPUT')

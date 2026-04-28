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
PLAYBOOKS_PATH = "Playbooks"
INCLUDE_BLOCKS = os.getenv('INCLUDE_BLOCKS', 'true').lower() == 'true'
EXCLUDE_FOLDER = os.getenv('EXCLUDE_FOLDER')

GITHUB_OUTPUT_FILE = os.getenv('GITHUB_OUTPUT')

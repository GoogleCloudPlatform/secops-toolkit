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

#!/bin/bash

# Check if exactly 3 arguments are provided
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <secops_project_id> <secops_region> <secops_instance>"
    exit 1
fi

SECOPS_PROJECT="$1"
SECOPS_REGION="$2"
SECOPS_INSTANCE="$3"

# Get directory of the script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

TEMPLATE_FILE="$DIR/.gemini/settings.json.template"
OUTPUT_FILE="$DIR/.gemini/settings.json"

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "Error: Template file $TEMPLATE_FILE not found."
    exit 1
fi

# Generate settings content
SETTINGS_CONTENT=$(sed -e "s/\${SECOPS_PROJECT}/$SECOPS_PROJECT/g" \
    -e "s/\${SECOPS_REGION}/$SECOPS_REGION/g" \
    -e "s/\${SECOPS_INSTANCE}/$SECOPS_INSTANCE/g" \
    "$TEMPLATE_FILE")

# Handle .gemini
if [ -d "$DIR/.gemini" ]; then
    echo "$SETTINGS_CONTENT" > "$OUTPUT_FILE"
    echo "Successfully generated $OUTPUT_FILE"
else
    echo "Skipping Gemini settings: .gemini directory does not exist."
fi

# Handle .antigravitycli
OUTPUT_FILE_ANTIGRAVITY="$DIR/.antigravitycli/settings.json"
if [ -d "$DIR/.antigravitycli" ]; then
    echo "$SETTINGS_CONTENT" > "$OUTPUT_FILE_ANTIGRAVITY"
    echo "Successfully generated $OUTPUT_FILE_ANTIGRAVITY"
else
    echo "Skipping Antigravity settings: .antigravitycli directory does not exist."
fi

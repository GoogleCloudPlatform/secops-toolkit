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

# Check if exactly 2 arguments are provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <secops_project_id> <secops_region>"
    exit 1
fi

SECOPS_PROJECT="$1"
SECOPS_REGION="$2"

# Get directory of the script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

TEMPLATE_FILE="$DIR/.gemini/settings.json.template"
OUTPUT_FILE="$DIR/.gemini/settings.json"

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "Error: Template file $TEMPLATE_FILE not found."
    exit 1
fi

# Replace variables in the template and output to settings.json
sed -e "s/\${SECOPS_PROJECT}/$SECOPS_PROJECT/g" \
    -e "s/\${SECOPS_REGION}/$SECOPS_REGION/g" \
    "$TEMPLATE_FILE" > "$OUTPUT_FILE"

echo "Successfully generated $OUTPUT_FILE"

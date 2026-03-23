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

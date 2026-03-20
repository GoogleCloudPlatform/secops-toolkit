#!/bin/bash

# ==============================================================================
# SecOps AI Rule Recommendation Helper
# ==============================================================================

# Save original directory and arguments
ORIGINAL_PWD=$(pwd)
ARG_PATH="$1"

# If argument provided, resolve to absolute path (if relative) before we cd
if [[ -n "$ARG_PATH" ]]; then
    if [[ "$ARG_PATH" != /* ]]; then
        ARG_PATH="$ORIGINAL_PWD/$ARG_PATH"
    fi
fi

# 1. Verification & Setup

# Set the working directory to ./recommender_curated_community
if [ -d "./recommender_curated_community" ]; then
    echo "Moving to recommender_curated_community directory..."
    cd "./recommender_curated_community" || { echo "Error: Failed to enter directory ./recommender_curated_community"; exit 1; }
elif [ -f "recommender_curated_community.py" ]; then
    echo "Notice: Already in recommender_curated_community directory."
else
    echo "Error: Directory ./recommender_curated_community not found and recommender_curated_community.py not found in current directory."
    echo "Please run this script from the project root."
    exit 1
fi

# Confirm authentication
read -p "Have you authenticated to Google Cloud (gcloud auth application-default login)? [Y/n]: " auth_confirm
auth_confirm="${auth_confirm:-y}"
if [[ "$auth_confirm" != "y" && "$auth_confirm" != "Y" ]]; then
    echo "Please run:gcloud auth application-default login"
    exit 1
fi

# Check default project
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
if [[ -z "$CURRENT_PROJECT" ]]; then
    echo "Default GCP project is not configured."
    read -p "Please enter your GCP Project ID to set it: " prompt_project
    if [[ -z "$prompt_project" ]]; then
        echo "Error: Project ID is required."
        exit 1
    fi
    gcloud config set project "$prompt_project"
else
    echo "Default GCP project is configured: $CURRENT_PROJECT"
fi

# Check env vars
check_env_var() {
    local var_name=$1
    if [[ -z "${!var_name}" ]]; then
        read -p "$var_name is missing. Please enter its value: " var_val
        if [[ -z "$var_val" ]]; then
            echo "Error: $var_name is required."
            exit 1
        fi
        export "$var_name"="$var_val"
    fi
}

check_env_var "CONTENTHUB_PROJECT_ID"
check_env_var "CONTENTHUB_LOCATION"
check_env_var "CONTENTHUB_INSTANCE_ID"

# Activate venv if exists
if [ -d ".venv" ]; then
    echo "Found local virtual environment .venv. Activating..."
    source .venv/bin/activate
fi

# Check requirements
if [[ -f "requirements.txt" ]]; then
    echo "Checking/Installing requirements..."
    python3 -m pip install -r requirements.txt
else
    echo "Warning: requirements.txt not found."
fi

# 2. Execution Preparation

if [[ -z "$ARG_PATH" ]]; then
    echo "Error: Path to customer rules JSON file is missing."
    read -p "Please provide the path to the JSON file: " prompt_file
    ARG_PATH="$prompt_file"
    if [[ -z "$ARG_PATH" ]]; then
        echo "Error: JSON file path is required."
        exit 1
    fi
fi

if [[ ! -f "$ARG_PATH" ]]; then
    echo "Error: File not found at '$ARG_PATH'"
    exit 1
fi

export CUSTOMER_RULES_TO_EVALUATE="$ARG_PATH"

# 3. Execution

echo "Executing recommender_curated_community.py..."
python3 recommender_curated_community.py

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

from google.auth import default
import vertexai
from vertexai.preview.language_models import TextEmbeddingModel
from vertexai.preview.language_models import TextGenerationModel
#from vertexai.preview.language_models import HarmCategory, HarmBlockThreshold
from vertexai.generative_models import (
    FinishReason,
    GenerationConfig,
    GenerativeModel,
    HarmBlockThreshold,
    HarmCategory,
    Part,
)
from vertexai.generative_models._generative_models import SafetySettingsType
import os
import json
import re
import sys
import google.auth
import google.auth.transport.requests
import requests
import csv
import subprocess
import secops_resources_helper
import ai_helper

# CONSTANTS

# SecOps ContentHub instance in order to download the latest version
contenthub_project_id = os.getenv("CONTENTHUB_PROJECT_ID")
contenthub_location = os.getenv("CONTENTHUB_LOCATION")
contenthub_instance_id = os.getenv("CONTENTHUB_INSTANCE_ID")

if "--help" not in sys.argv:
    missing_vars = []
    if not contenthub_project_id: missing_vars.append("CONTENTHUB_PROJECT_ID")
    if not contenthub_location: missing_vars.append("CONTENTHUB_LOCATION")
    if not contenthub_instance_id:
        missing_vars.append("CONTENTHUB_INSTANCE_ID")
    if missing_vars:
        raise ValueError(
            f"Required environment variables are not set: {', '.join(missing_vars)}"
        )

# AI configuration
ai_model = os.getenv("AI_MODEL", "gemini-2.5-pro")

# File will all community rules
customer_rules_to_evaluate = os.getenv("CUSTOMER_RULES_TO_EVALUATE",
                                       "./resources/sample_input_rules.json")
community_rules = os.getenv("COMMUNITY_RULES",
                            "./resources/all_community_rules_20250816.txt")

# optional if provided it will not be downloaded from content hub
curated_use_preloaded_file = os.getenv("CURATED_USE_PRELOADED_FILE",
                                       "False")  # True or False
curated_rules_file = os.getenv("CURATED_RULES_FILE",
                               "./resources/curated_rules.json")
curated_rulesets_file = os.getenv("CURATED_RULESETS_FILE",
                                  "./resources/curated_rulesets.json")

# Output files
curated_rules_output_file = os.getenv("CURATED_RULES_OUTPUT_FILE",
                                      "./work_dir/curated_rules.json")
curated_rulesets_output_file = os.getenv("CURATED_RULESETS_OUTPUT_FILE",
                                         "./work_dir/curated_rulesets.json")
recommendations_json_output_file = os.getenv(
    "RECOMMENDATIONS_JSON_OUTPUT_FILE",
    "./work_dir/recommendation_curated_community_rules.json")
recommendations_csv_output_file = os.getenv(
    "RECOMMENDATIONS_CSV_OUTPUT_FILE",
    "./work_dir/recommendation_curated_community_rules.csv")
recommendations_ruleset_csv_output_file = os.getenv(
    "RECOMMENDATIONS_CSV_OUTPUT_FILE",
    "./work_dir/recommendation_curated_rulesets.csv")


def load_curated_rules_description():
    """
        Loads all curated rules and rules sets 
        Returns curated rules enriched with log sources 
    """
    chronicle_client = secops_resources_helper.get_chronicle_client(
        contenthub_project_id, contenthub_location, contenthub_instance_id)
    if not chronicle_client:
        sys.exit(1)

    all_curated_rules = secops_resources_helper.get_featured_content_rules(
        chronicle_client)
    all_curated_rulesets = secops_resources_helper.get_curated_rule_sets(
        chronicle_client)
    all_curated_rules = secops_resources_helper.add_log_sources_to_curated_list(
        all_curated_rulesets, all_curated_rules)

    return (all_curated_rules, all_curated_rulesets)


def print_help():
    """Prints the help message for the script."""
    # Using __file__ allows the script name to be dynamic
    script_name = os.path.basename(__file__)
    help_text = f"""
USAGE:
  python {script_name}

DESCRIPTION:
  This script analyzes a set of customer-provided detection rules, like KQL etc, and recommends relevant 
  curated and community rules. It can fetch curated rules live from the Chronicle SecOps content hub or 
  use pre-loaded local files. The final recommendations are saved in both JSON and CSV formats.

CONFIGURATION (via Environment Variables):
  The script's behavior is configured through environment variables. 
  Default values are shown in parentheses.

  [Content Hub Connection]
  CONTENTHUB_PROJECT_ID:      Google Cloud Project ID for the content hub. (Required)
  CONTENTHUB_LOCATION:        Location of the content hub. (Required)
  CONTENTHUB_INSTANCE_ID:     Instance ID for the content hub. (Required)

  [AI Configuration]
  AI_MODEL:                   The Vertex AI model to use for generation. (Default: "{ai_model}")

  [Input Files]
  CUSTOMER_RULES_TO_EVALUATE: Path to the JSON file with customer rules. (Default: "{customer_rules_to_evaluate}")
  COMMUNITY_RULES:            Path to the text file with all community rules. (Default: "{community_rules}")

  [Preloaded Curated Rules (Optional)]
  CURATED_USE_PRELOADED_FILE: Set to "True" to use local files instead of fetching from the API. (Default: "{curated_use_preloaded_file}")
  CURATED_RULES_FILE:         Path to the preloaded curated rules JSON file. (Default: "{curated_rules_file}")
  CURATED_RULESETS_FILE:      Path to the preloaded curated rulesets JSON file. (Default: "{curated_rulesets_file}")

  [Output Files]
  CURATED_RULES_OUTPUT_FILE:       Where to save fetched curated rules. (Default: "{curated_rules_output_file}")
  CURATED_RULESETS_OUTPUT_FILE:    Where to save fetched curated rulesets. (Default: "{curated_rulesets_output_file}")
  RECOMMENDATIONS_JSON_OUTPUT_FILE: Path for the final JSON recommendations. (Default: "{recommendations_json_output_file}")
  RECOMMENDATIONS_CSV_OUTPUT_FILE:  Path for the final CSV recommendations. (Default: "{recommendations_csv_output_file}")
"""
    print(help_text)


if __name__ == "__main__":

    # Check if the --help flag is provided
    if "--help" in sys.argv:
        print_help()
        sys.exit(0)

    # load from secops or file and save curated rules
    if curated_use_preloaded_file == "True":
        with open(curated_rules_file, 'r') as f:
            all_curated_rules = json.load(f)
            print(
                f"\nSuccessfully loaded curated rule form file {curated_rules_file}"
            )
        # Corrected variable name from curated_rulesets_files to curated_rulesets_file
        with open(curated_rulesets_file, 'r') as f:
            all_curated_rulesets = json.load(f)
            print(
                f"\nSuccessfully loaded curated ruleset form file {curated_rulesets_file}"
            )
    else:
        all_curated_rules, all_curated_rulesets = load_curated_rules_description(
        )

        with open(curated_rules_output_file, 'w', encoding='utf-8') as f:
            json.dump(all_curated_rules, f, indent=2)
        print(
            f"\nSuccessfully curated rules saved to {curated_rules_output_file}"
        )

        with open(curated_rulesets_output_file, 'w', encoding='utf-8') as f:
            json.dump(all_curated_rulesets, f, indent=2)
        print(
            f"\nSuccessfully curated rulesets saved to {curated_rulesets_output_file}"
        )

    # make recommendation
    print("Start processing")
    recommendation_curated_community = []

    # load rules
    with open(customer_rules_to_evaluate, 'r') as f:
        customer_rules = json.load(f)
        print(f"Successfully loaded data from {customer_rules_to_evaluate}")

    with open(community_rules, 'r') as f:
        all_community_rules = f.read()
        print(
            f"\nSuccessfully loaded community rules form file {community_rules}"
        )

    # Enrich the input rules with the sources
    unique_log_types = secops_resources_helper.get_unique_log_sources(
        all_curated_rulesets)
    customer_rules_with_log_sources = ai_helper.find_log_sources_needed(
        customer_rules, unique_log_types)
    print("Logs sources identified")

    import time

    def call_with_backoff(func, *args, max_retries=5, base_delay=2):
        """Calls a function with exponential backoff on failure to handle rate limits."""
        delay = base_delay
        for attempt in range(max_retries):
            try:
                return func(*args)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                print(
                    f"    Rate limit or error encountered ({e}). Retrying in {delay}s..."
                )
                time.sleep(delay)
                delay *= 2

    for i, rule in enumerate(customer_rules):
        try:
            print(f"Start working on rule ucid:{rule['ucid']}")
            rule_str = json.dumps(rule)
            curated_filtered = secops_resources_helper.filter_curated_rules_log_source(
                customer_rules_with_log_sources[i], all_curated_rules)

            print("  Evaluating curated rules...")
            curated_sugg_str = call_with_backoff(
                ai_helper.generate_curated_rules_recommendation, rule_str,
                curated_filtered)
            curated_sugg = json.loads(curated_sugg_str)

            print("  Evaluating community rules...")
            community_sugg_str = call_with_backoff(
                ai_helper.generate_community_rules_recommendation, rule_str,
                all_community_rules)
            community_sugg = json.loads(community_sugg_str)

            # Merge results for the CSV/JSON output
            combined_suggestion = {**curated_sugg, **community_sugg}
            recommendation_curated_community.append(combined_suggestion)

        except Exception as e:
            print(f"Erorr on rule #{i}, content{rule}")
            print(e)

        print(f"Processed {i+1}/{len(customer_rules)}")

    # with open("recommendations_json_output_file", 'r') as f:
    #         recommendation_curated_community = json.load(f)

    print("Finshed processing")

    # Saving to files
    secops_resources_helper.write_results_file(
        recommendation_curated_community, recommendations_json_output_file,
        recommendations_csv_output_file,
        recommendations_ruleset_csv_output_file)

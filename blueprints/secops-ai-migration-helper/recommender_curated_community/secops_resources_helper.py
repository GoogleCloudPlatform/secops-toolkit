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

from secops import SecOpsClient
from google.auth.exceptions import DefaultCredentialsError
import os
import json
import re
import sys
import csv
import subprocess


def get_chronicle_client(project_id, location, instance_id):
    print(
        "Attempting to authenticate using Application Default Credentials with secops SDK..."
    )

    try:
        client = SecOpsClient()
        chronicle = client.chronicle(customer_id=instance_id,
                                     project_id=project_id,
                                     region=location)
        print("Successfully obtained credentials.")
        return chronicle
    except DefaultCredentialsError:
        print("\n--- Authentication Failed ---")
        print(
            "Please run the following command in your terminal to authenticate:"
        )
        print("gcloud auth application-default login")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def get_curated_rule_sets(chronicle_client):
    print(f"\nFetching curated rule sets using secops SDK...")
    try:
        result = chronicle_client.list_curated_rule_sets(as_list=True)
        print(f"Fetched rule sets")
        return {"curatedRuleSets": result}
    except Exception as e:
        print(f"\n--- An Unexpected Error Occurred ---")
        print(f"Error: {e}")
        return {"curatedRuleSets": []}


def get_featured_content_rules(chronicle_client):
    """
    Calls the Google Chronicle API to fetch all featured content rules using the secops SDK,
    authenticating using Application Default Credentials (ADC), and returns
    the results to a JSON.
    """
    print(f"\nFetching featured content rules using secops SDK...")
    try:
        all_rules = chronicle_client.list_featured_content_rules(as_list=True)
        print(f"Fetched {len(all_rules)} featured content rules.")
        return all_rules
    except Exception as e:
        print(f"\n--- An Unexpected Error Occurred ---")
        print(f"Error: {e}")
        return []


# Adding to curated rules the log source extracted from the description of the ruleSet, aka merging
def add_log_sources_to_curated_list(all_curated_ruleset, all_curated_rules):
    rule_set_lookup = {
        rule_set['name']: rule_set.get('logSources', [])
        for rule_set in all_curated_ruleset.get('curatedRuleSets', [])
    }

    # Iterate through each rule in the first data set
    for rule in all_curated_rules:
        # Check if the rule has the necessary structure
        if 'ruleSet' in rule and 'curatedRuleSet' in rule['ruleSet']:
            rule_set_key = rule['ruleSet']['curatedRuleSet']

            # Find the matching rule set in our lookup dictionary
            if rule_set_key in rule_set_lookup:
                # Add the 'logSources' to the rule's 'ruleSet' object
                rule['ruleSet']['logSources'] = rule_set_lookup[rule_set_key]

    return all_curated_rules


# Extract the unique log sources from the rulesSets
def get_unique_log_sources(parsed_data) -> list[str]:
    """
    Parses extract a unique list of logSources.

    Args:
      data: JSON data.

    Returns:
      A list of unique log source strings.
    """

    # Use a set to automatically handle uniqueness of log sources
    unique_sources = set()

    # Iterate through each rule set in the 'curatedRuleSets' list
    # .get() is used to avoid errors if 'curatedRuleSets' key is missing
    for rule_set in parsed_data.get("curatedRuleSets", []):
        # Extend the set with the list of log sources for the current rule set
        # .get() is used to avoid errors if 'logSources' key is missing
        for source in rule_set.get("logSources", []):
            splited_values = source.split(
                ","
            )  # bug in the documentaiton somce values are one string comma separated
            for s in splited_values:
                unique_sources.add(s.strip())

    # Convert the set to a list and return it
    return sorted(list(unique_sources))


def filter_curated_rules_log_source(log_sources, allrules):
    """
    Filters the all curated list only to provided log sources
  """
    filtered_data = [
        element for element in allrules
        if 'ruleSet' in element and 'logSources' in element['ruleSet'] and
        (any(source in element['ruleSet']['logSources']
             for source in log_sources) or not element['ruleSet']['logSources']
         or "N/A" in element['ruleSet']['logSources'])
    ]

    return filtered_data


def write_results_file(recommendation_curated_community,
                       recommendations_json_output_file,
                       recommendations_csv_output_file,
                       recommendations_ruleset_csv_output_file):
    """
        Export the result to file 
    """
    # Saving to files
    # Export the result to JSON
    with open(recommendations_json_output_file, 'w') as f:
        json.dump(recommendation_curated_community, f, indent=2)
        print(
            f"Successfully saved recommendations to {recommendations_json_output_file}"
        )

    # Export the results to CSV
    with open(recommendations_csv_output_file, 'w', newline='') as csvfile:
        fieldnames = [
            'ucid', 'title', 'description', 'curated rules',
            'curated rules coverage', 'curated rationale', 'community rules',
            'community rules coverage', 'community rationale'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()

        for row in recommendation_curated_community:
            writer.writerow(row)

    print(
        f"JSON data converted to CSV and saved to {recommendations_csv_output_file}"
    )

    # Generate reverse mapping RuleSet to customer rule

    with open(recommendations_ruleset_csv_output_file, 'w',
              newline='') as csvfile:
        fieldnames = [
            'curated rulesSet', 'curated rule', 'ucid', 'title',
            'curated rules coverage', 'curated rationale'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in recommendation_curated_community:
            curated_rules = row.get('curated rules', '').split(',')
            for curated_rule in curated_rules:
                # Extracting ruleSet and rule name from the format "category/ruleset/rule name"
                parts = curated_rule.strip().split('/')
                curated_ruleset = f"{parts[0]}/{parts[1]}" if len(
                    parts) > 1 else 'N/A'
                rule_name = parts[-1] if parts else 'N/A'

                writer.writerow({
                    'curated rulesSet':
                    curated_ruleset,
                    'curated rule':
                    curated_rule,
                    'ucid':
                    row.get('ucid', 'N/A'),
                    'title':
                    row.get('title', 'N/A'),
                    'curated rules coverage':
                    row.get('curated rules coverage', 'N/A'),
                    'curated rationale':
                    row.get('curated rationale', 'N/A')
                })

    print(
        f"Successfully converted rule sets recommendations to CSV and saved to {recommendations_ruleset_csv_output_file}"
    )

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

"""
Generates summary in CSV format for curated rules from the Google SecOps .

"""

import json
import csv
import re
import os
import argparse


def extract_udm_fields(events_text):
    if not events_text:
        return []
    # Find all occurrences of $var.field.path...
    # We match $[a-zA-Z0-9_]+ followed by a dot and then the field path.
    # The field path can contain letters, numbers, underscores and dots.
    fields = re.findall(r"\$[a-zA-Z0-9_]+\.([a-zA-Z0-9_\.]+)", events_text)
    # Filter out common false positives if any, but here we assume they are all fields
    return list(set(fields))


def extract_metadata_field(rule_text, field_name):
    # Look for lines like $e.metadata.log_type = "AZURE_ACTIVITY"
    # or similar assignments/comparisons.
    # Support both = and == operators
    pattern = r"\$[a-zA-Z0-9_]+\.metadata\." + field_name + r'\s*={1,2}\s*"([^"]+)"'
    matches = re.findall(pattern, rule_text)
    return list(set(matches))


def main():
    parser = argparse.ArgumentParser(
        description="Generates summary in CSV format for curated rules."
    )
    parser.add_argument(
        "--rules",
        default=os.environ.get("CURATED_RULES_PATH", "./work_dir/curated_rules.json"),
        help="Path to curated_rules.json (env: CURATED_RULES_PATH)",
    )
    parser.add_argument(
        "--rulesets",
        default=os.environ.get(
            "CURATED_RULESETS_PATH", "./work_dir/curated_rulesets.json"
        ),
        help="Path to curated_rulesets.json (env: CURATED_RULESETS_PATH)",
    )
    parser.add_argument(
        "--output",
        default=os.environ.get(
            "RESULTS_PATH", "./work_dir/curated_detations_rules_summary.csv"
        ),
        help="Path to output CSV file (env: RESULTS_PATH)",
    )
    parser.add_argument(
        "--output-agg",
        default=os.environ.get(
            "RESULTS_AGG_PATH", "./work_dir/curated_rulesets_aggregation_summary.csv"
        ),
        help="Path to output aggregated CSV file (env: RESULTS_AGG_PATH)",
    )

    args = parser.parse_args()

    rules_path = args.rules
    rulesets_path = args.rulesets
    output_path = args.output
    output_agg_path = args.output_agg

    # Ensure output directories exist
    for p in [output_path, output_agg_path]:
        d = os.path.dirname(p)
        if d and not os.path.exists(d):
            os.makedirs(d, exist_ok=True)

    print(f"Loading rules from {rules_path}")
    try:
        with open(rules_path, "r") as f:
            rules = json.load(f)
    except FileNotFoundError:
        print(f"Error: {rules_path} not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from {rules_path}")
        return

    print(f"Loading rulesets from {rulesets_path}")
    rulesets_lookup = {}
    try:
        with open(rulesets_path, "r") as f:
            rulesets_data = json.load(f)
            for rs in rulesets_data.get("curatedRuleSets", []):
                name = rs.get("name")
                if name:
                    rulesets_lookup[name] = rs
    except FileNotFoundError:
        print(f"Warning: {rulesets_path} not found. Proceeding without it.")
    except json.JSONDecodeError:
        print(
            f"Warning: Failed to decode JSON from {rulesets_path}. Proceeding without it."
        )

    headers = [
        "rule.contentMetadata.displayName",
        "rule.contentMetadata.id",
        "ruleSet.displayName",
        "ruleSet.id",
        "rule.contentMetadata.category",
        "curatedRuleContent.precision",
        "curatedRuleContent.tactics",
        "curatedRuleContent.techniques",
        "metadata.product_event_type",
        "metadata.log_type",
        "metadata.product_name",
        "unique UDM fields from events section",
        "ruleset.logSources",
    ]

    ruleset_agg = {}

    print(f"Generating summary to {output_path}")
    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)

        for rule in rules:
            content_metadata = rule.get("contentMetadata", {})
            rule_set = rule.get("ruleSet", {})
            curated_content = rule.get("curatedRuleContent", {})
            rule_text = rule.get("ruleText", "")

            display_name = content_metadata.get("displayName", "N/A")
            rule_id = content_metadata.get("id", "N/A")

            rs_display_name = rule_set.get("displayName", "N/A")
            rs_id = rule_set.get("id", "N/A")

            categories = content_metadata.get("categories", [])
            category = categories[0] if categories else "N/A"

            precision = curated_content.get("precision", "N/A")

            tactics = curated_content.get("tactics", [])
            tactic_ids = [t.get("id", "N/A") for t in tactics]
            tactics_str = ", ".join(tactic_ids) if tactics else "N/A"

            techniques = curated_content.get("techniques", [])
            technique_ids = [t.get("id", "N/A") for t in techniques]
            techniques_str = ", ".join(technique_ids) if techniques else "N/A"

            # Extract from ruleText
            product_event_types = extract_metadata_field(
                rule_text, "product_event_type"
            )
            event_types = extract_metadata_field(rule_text, "event_type")
            combined_event_types = list(set(product_event_types + event_types))
            product_event_types_str = (
                ", ".join(combined_event_types) if combined_event_types else "N/A"
            )

            log_types = extract_metadata_field(rule_text, "log_type")
            log_types_str = ", ".join(log_types) if log_types else "N/A"

            product_names = extract_metadata_field(rule_text, "product_name")
            product_names_str = ", ".join(product_names) if product_names else "N/A"

            # Extract UDM fields from events section
            events_section = ""
            events_match = re.search(
                r"events:(.*?)(?:match:|outcome:|condition:)", rule_text, re.DOTALL
            )
            if events_match:
                events_section = events_match.group(1)
            else:
                events_match = re.search(r"events:(.*)", rule_text, re.DOTALL)
                if events_match:
                    events_section = events_match.group(1)

            udm_fields = extract_udm_fields(events_section)
            udm_fields_str = ", ".join(udm_fields) if udm_fields else "N/A"

            # Get logSources from lookup or ruleSet
            curated_ruleset_path = rule_set.get("curatedRuleSet")
            sources_list = []
            if curated_ruleset_path and curated_ruleset_path in rulesets_lookup:
                sources_list = rulesets_lookup[curated_ruleset_path].get(
                    "logSources", []
                )
            else:
                sources_list = rule_set.get("logSources", [])
            log_sources = ", ".join(sources_list) if sources_list else "N/A"

            # Update aggregation
            if rs_id != "N/A" or rs_display_name != "N/A":
                key = (rs_id, rs_display_name)
                if key not in ruleset_agg:
                    ruleset_agg[key] = {
                        "categories": set(),
                        "precisions": set(),
                        "tactics": set(),
                        "techniques": set(),
                        "product_event_types": set(),
                        "log_types": set(),
                        "product_names": set(),
                        "udm_fields": set(),
                        "log_sources": set(),
                        "rule_count": 0,
                    }

                ruleset_agg[key]["rule_count"] += 1
                if category != "N/A":
                    ruleset_agg[key]["categories"].add(category)
                if precision != "N/A":
                    ruleset_agg[key]["precisions"].add(precision)
                ruleset_agg[key]["tactics"].update(tactic_ids)
                ruleset_agg[key]["techniques"].update(technique_ids)
                ruleset_agg[key]["product_event_types"].update(combined_event_types)
                ruleset_agg[key]["log_types"].update(log_types)
                ruleset_agg[key]["product_names"].update(product_names)
                ruleset_agg[key]["udm_fields"].update(udm_fields)
                ruleset_agg[key]["log_sources"].update(sources_list)

            row = [
                display_name,
                rule_id,
                rs_display_name,
                rs_id,
                category,
                precision,
                tactics_str,
                techniques_str,
                product_event_types_str,
                log_types_str,
                product_names_str,
                udm_fields_str,
                log_sources,
            ]
            writer.writerow(row)

    # Write aggregated CSV
    headers_agg = [
        "ruleSet.displayName",
        "ruleSet.id",
        "number of rules in the ruleset",
        "rule.contentMetadata.category",
        "curatedRuleContent.precision",
        "curatedRuleContent.tactics",
        "curatedRuleContent.techniques",
        "metadata.product_event_type",
        "metadata.log_type",
        "metadata.product_name",
        "unique UDM fields from events section",
        "ruleset.logSources",
    ]

    print(f"Generating aggregated summary to {output_agg_path}")
    with open(output_agg_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers_agg)

        # Sort by ruleset display name for better readability
        sorted_keys = sorted(ruleset_agg.keys(), key=lambda x: x[1])
        for rs_id, rs_display_name in sorted_keys:
            data = ruleset_agg[(rs_id, rs_display_name)]
            row = [
                rs_display_name,
                rs_id,
                str(data["rule_count"]),
                ", ".join(sorted([x for x in data["categories"] if x != "N/A"])),
                ", ".join(sorted([x for x in data["precisions"] if x != "N/A"])),
                ", ".join(sorted([x for x in data["tactics"] if x != "N/A"])),
                ", ".join(sorted([x for x in data["techniques"] if x != "N/A"])),
                ", ".join(
                    sorted([x for x in data["product_event_types"] if x != "N/A"])
                ),
                ", ".join(sorted([x for x in data["log_types"] if x != "N/A"])),
                ", ".join(sorted([x for x in data["product_names"] if x != "N/A"])),
                ", ".join(sorted([x for x in data["udm_fields"] if x != "N/A"])),
                ", ".join(sorted([x for x in data["log_sources"] if x != "N/A"])),
            ]
            # Fallback to N/A if empty
            row = [x if x else "N/A" for x in row]
            writer.writerow(row)

    print("Done.")


if __name__ == "__main__":
    main()

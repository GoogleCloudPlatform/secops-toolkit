---
name: migration_helper_recommend
description: Run the recommender script to generate recommendations for SecOps curated/community rules based on custom rules.
---

# Curated & Community Rules Recommender

## Description
Runs the interactive recommender tool to match legacy custom SIEM rules in JSON format with equivalent Google SecOps Curated or Community rules.

## When to Use This Skill
- Use this skill to evaluate curated/community coverage for legacy rules, in order to decide which rules need migration or decommissioning.
- Triggered by `/migration_helper_recommend <json_rules_path>` or when recommending rules.

## Instructions
Your objective is to execute the interactive recommender script using the provided input rules file `<json_rules_path>`.

### Steps:
1. **Argument Check:** If `<json_rules_path>` is empty, stop and ask the user to provide the path to the JSON file containing their customer rules.
2. **Execute Recommender:** Execute the bash script `run_recommender.sh <json_rules_path>` from the workspace directory or inside the `recommender_curated_community` folder.
   - Stream the script output directly to the user so they can monitor the process and interactive input.
   - Inform the user to use `TAB` to focus on the terminal/script interface if they need to interact.
3. **Completion:** When the script finishes, inform the user that the operation is complete and provide the file paths for the final CSV and JSON recommendation files (as output by the script).

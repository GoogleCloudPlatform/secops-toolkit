---
name: migration_helper_extract
description: Extract unstructured legacy rules from a raw text file and structure them into valid JSON.
---

# Extract Unstructured SIEM Rules

## Description
Parses a file containing unstructured customer SIEM rules and formats them into a clean, structured JSON file that can be ingested by the recommender.

## When to Use This Skill
- Use this skill to prepare a raw text file of customer legacy rules for Curated/Community mapping.
- Triggered by `/migration_helper_extract <source_rules_file_path>` or when extracting custom rules from loose text format.

## Instructions
Your goal is to extract legacy rules from the provided `<source_rules_file_path>` and structure them into a valid JSON file.

### Steps & Guidelines:
1. **Load File:** Load the file `<source_rules_file_path>` and process it record by record, keeping in mind that different rule syntaxes may be mixed.
2. **Field Extraction:** Understand each rule and extract/generate the following fields for each:
   - `ucid`: The Case or rule ID (or suggest/generate one if missing).
   - `title`: A one-sentence title of the rule.
   - `description`: The rule's description (analyze the rule and suggest one if missing, or put `"N/A"` if not sure).
   - `rule`: The exact original input rule logic, completely unmodified.
   - *Do not use RegEx scripts in the rules, extract the literal rule content.*
3. **Save to JSON:** Write the structured records into a JSON file under `./recommender_curated_community/work_dir/input_rules_YYYYMMDD.json` (replacing `YYYYMMDD` with the current date).
   - *CRITICAL:* Ensure you output fully valid, properly escaped JSON.
   
   Format template:
   ```json
   [
     {
       "ucid": "<Case or rule ID>",
       "title": "<Title of the rule>",
       "description": "<Description>",
       "rule": "<Original input rule logic without modifications>"
     }
   ]
   ```
4. **Validate JSON:** Double check that the final JSON file is syntactically valid and parses correctly.
5. **Report Results:** Print the exact absolute or relative file path where you saved the structured JSON results.

---
name: migration_helper_format
description: Take a source SIEM rule and format its content for readability, then insert it into a YARA-L rule template.
---

# Format SIEM Rule inside Template

## Description
Formats a source rule from a legacy SIEM and inserts it into a specified YARA-L template file.

## When to Use This Skill
- Use this when formatting a legacy SIEM rule and placing it into the `SOURCE RULE` metadata section of an initialized YARA-L template file.
- Triggered by `/migration_helper_format <migrating_rule_path> <new_rule_name>` (where `<new_rule_name>` points to the target YARA-L file, i.e., `rules/<new_rule_name>/<new_rule_name>.yaral`).

## Instructions
Your task is to take the rule content provided in `<migrating_rule_path>` and insert it into the template structure of the target rule file `<new_rule_name>` (usually `rules/<new_rule_name>/<new_rule_name>.yaral`).

### Constraints & Steps:
1. **Content Integrity:** You are strictly forbidden from shortening, trimming, or modifying the logic/code within the source rule. Every character of the original rule logic must be fully preserved.
2. **Formatting:** Improve the indentation and spacing of the source rule to achieve maximum readability before insertion.
3. **Placement:** Locate the placeholder `<original formated source rule>` inside the target rule file and replace it with the newly formatted source rule content.
4. **Error Handling:** If the input in the source rule file appears truncated, incomplete, or corrupted, stop immediately and alert the user.
5. **Output:** Output the final merged result as a single code block, and write it back to the target rule file.

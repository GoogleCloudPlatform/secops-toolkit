---
name: migration_helper_validate
description: Validate a YARA-L rule's syntax against the Google SecOps MCP server and self-correct any errors.
---

# Validate YARA-L Rule Syntax

## Description
Uses the Google SecOps MCP server integration to validate the syntax of a migrated YARA-L 2.0 rule, iteratively fixing errors.

## When to Use This Skill
- Use this skill to ensure the YARA-L rule conforms to valid Google SecOps syntax before final deployment.
- Triggered by `/migration_helper_validate <rule_name>` (where `<rule_name>` is the name of the rule directory, i.e., `rules/<rule_name>/<rule_name>.yaral`).

## Instructions
Your task is to use the `<rule_name>.yaral` file to validate the YARA-L 2.0 Google SecOps syntax using the MCP SecOps server tool `validate_rule`.

### Steps:
1. **Read Rule:** Read the content of the rule file at `rules/<rule_name>/<rule_name>.yaral`.
2. **Execute Validation:** Use the available `validate_rule` tool in the MCP SecOps server to validate the YARA-L 2.0 Google SecOps syntax. Do not consider `.tf` files or config files.
3. **Handle Errors (Self-Correction Loop):** If validation fails:
   - Analyze the error message, extract the line number, and consult the codebase or search the web for YARA-L 2.0 Google SecOps syntax documentation.
   - Correct the rule. Confirm that the line you are changing is the exact line that you extracted as problematic.
4. **Repeat:** Repeat the validation and correction process until the rule is completely valid. To break any impasse, simplify the logic and test the core syntax issues in isolation.

---
name: migration_helper_migrate_rule
description: Full orchestration workflow to migrate a custom SIEM rule to YARA-L, running all sub-steps sequentially.
---

# Orchestrate YARA-L Rule Migration

## Description
Executes the full multi-step migration workflow of a legacy rule to YARA-L, including structure initialization, rule formatting, code generation, note authoring, and raw log generation.

## When to Use This Skill
- Use this skill to fully migrate a custom SIEM rule to a customized YARA-L rule along with a sample raw log.
- Triggered by `/migration_helper_migrate_rule <legacy_rule_file_path>` or whenever the user requests a full migration of a rule.

## Instructions
Your task is to take the rule content provided in `<legacy_rule_file_path>` and orchestrate its complete migration to YARA-L.

### Steps:
1. **Rule Name Selection:** Read the rule file provided in `<legacy_rule_file_path>`. Use the UCID and rule title inside it to determine the target YARA-L rule name (`target_rule_name`) using the notation `<UCID>_<KeyWords>`.
   - *Example:* If UCID is `9101` and title is `Rare Scripting Software Detected`, the `target_rule_name` is `9101_RareScriptingSoftwareDetected`.
2. **Execute Init:** Run the `migration_helper_init` skill using the `target_rule_name` as the argument to establish the directories and files.
3. **Execute Format:** Run the `migration_helper_format` skill using the `<legacy_rule_file_path>` and `target_rule_name` to insert the original rule logic into the template.
4. **Execute Generate YARA-L:** Run the `migration_helper_generate_yaral` skill using the `target_rule_name` as the argument to generate the YARA-L 2.0 code.
5. **Execute Author Notes:** Run the `migration_helper_author_notes` skill using the `target_rule_name` to document and enrich the YARA-L metadata.
6. **Execute Generate Log:** Run the `migration_helper_generate_log` skill using the `target_rule_name` to create a matching raw source log.
7. **Manual Validation:** Validate without tools (MCP) the generated YARA-L rule against the generated raw log. Update log sample if needed to ensure correct triggering. If you see flas in logic ask the use the validate manually. 

### Output:
- Present the final YARA-L rule and the raw log content to the user.
- Provide the following exact instruction message to the user:
  > "The next step is validation. If you have an MCP server with a YARA-L plugin, you can execute the step validate with argument target_rule_name (/migration_helper_validate <target_rule_name>). If you don't have an MCP server with a YARA-L plugin, you can manually validate the rule by following the instructions in the author_notes section."

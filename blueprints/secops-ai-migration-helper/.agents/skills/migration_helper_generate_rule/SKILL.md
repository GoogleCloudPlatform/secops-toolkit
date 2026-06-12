---
name: migration_helper_generate_rule
description: Migrate a source rule section in a YARA-L file into YARA-L 2.0, adhering to precise Google SecOps schemas.
---

# Generate YARA-L 2.0 Rule (Alias)

## Description
Migrates the legacy source rule section inside the `<rule_name>.yaral` template file to a valid Google SecOps YARA-L 2.0 detection rule.

## When to Use This Skill
- Use this skill to translate the original logic of a legacy rule into YARA-L 2.0 syntax.
- Triggered by `/migration_helper_generate_rule <rule_name>` (where `<rule_name>` is the name of the rule directory, i.e., `rules/<rule_name>/<rule_name>.yaral`).

## Instructions
Please refer to the main skill `migration_helper_generate_yaral` for full instructions.

Your primary role is to migrate the **Source Rule** section in `rules/<rule_name>/<rule_name>.yaral` into YARA-L 2.0. Be sure to present your plan and await approval.

### Steps:
1. **Rule File Reading:** Read the file `rules/<rule_name>/<rule_name>.yaral`. If lines are shortened or you receive a truncation error, immediately stop.
2. **Detailed Analysis:** Perform a detailed analysis of the rule under the `SOURCE RULE` block.
3. **Context-Aware Reference Searching:** Search for the most similar existing YARA-L rules (excluding the current file) in your repository that contain similar description keywords, and use them as context for logic creation.
   - *Example:* For input rules with description "Rare or Never Seen EventID Logged", search for rules with "first time seen window event" or "rare or never seen EventID".
4. **Logic Planning:** Plan for an exact like-for-like migration to YARA-L 2.0. Refer to YARA-L 2.0 syntax conventions and examples. You are forbidden from simplifying rule logic or taking shortcuts.
5. **Placement:** Place the migrated YARA-L 2.0 rule content between the first and last line at `<YARA-L 2.0 rule content>` in the existing file `rules/<rule_name>/<rule_name>.yaral`.

### Meta Schema Requirements:
Ensure the `meta` block of the migrated YARA-L 2.0 rule follows this exact schema:
- `author` = must be `"Google Professional Services"`
- `description` = must be the exact like-for-like description as the source rule.
- `title` = must be the exact like-for-like title as the source rule.
- `tactic` = must be `"TO-BE-FIXED"`
- `technique` = must be `"TO-BE-FIXED"`
- `mitre_attack_url` = must be `"https://attack.mitre.org/techniques"`
- `mitre_attack_version` = must be `"TO-BE-FIXED"`
- `old_ucid` = must be `"TO-BE-FIXED"`
- `secops_ucid` = must be `"TO-BE-FIXED"`
- `type` = must be `"Alert"`
- `data_source` = must be `"TO-BE-FIXED"`
- `responsible` = must be `"SOC1"`
- `creation_date` = Must contain exact like-for-like creation as the source rule in DD.MM.YYYY format (Example: `"16.06.2025"`). Can be empty (`""`) if not found.
- `last_rework_date` = Today's date in DD.MM.YYYY format (Example: `"16.06.2025"`). Can be empty (`""`).
- `severity` = must be exact like-for-like severity as the source rule ("Medium", "High", "Low"). If not set, use `"TO-BE-FIXED"`.
- `status` = must be `"prototype"`
- `version` = must be `"0.5"`

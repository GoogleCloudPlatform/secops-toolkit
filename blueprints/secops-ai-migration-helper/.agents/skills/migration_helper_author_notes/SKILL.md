---
name: migration_helper_author_notes
description: Author rule notes, parameters, dependencies, tuning, and testing sections for a YARA-L rule.
---

# Author Rule Notes for YARA-L Rule

## Description
Fills in and enriches metadata and guidance sections (`RULE PARAMETERS`, `DEPENDENCIES`, `TUNING`, `TESTING`, `DOCS`, `NOTES`) inside a migrated YARA-L rule file.

## When to Use This Skill
- Use this skill to document, tune, and detail rule parameters for a migrated YARA-L rule.
- Triggered by `/migration_helper_author_notes <rule_name>` (where `<rule_name>` is the name of the rule directory, i.e., `rules/<rule_name>/<rule_name>.yaral`).
 
## Instructions
Your primary role is to update the `RULE PARAMETERS`, `DEPENDENCIES`, `TUNING`, `TESTING`, `DOCS`, and `NOTES` sections of `rules/<rule_name>/<rule_name>.yaral`.

### Steps:
1. **Read Rule:** Read `rules/<rule_name>/<rule_name>.yaral`. If lines are shortened or you receive a truncation error, immediately stop.
2. **Detailed Analysis:** Perform detailed analysis on `rules/<rule_name>/<rule_name>.yaral` and understand exactly how the rule is configured (what fields are queried, what conditions are checked, etc.).
3. **Metadata Writing:** Re-write the contents of `RULE PARAMETERS`, `DEPENDENCIES`, `TUNING`, `TESTING`, `DOCS`, and `NOTES` inside the YARA-L rule block with your findings.
4. **Constraints:** You are strictly forbidden from modifying the `SOURCE RULE` or the YARA-L rule logic blocks in any way.

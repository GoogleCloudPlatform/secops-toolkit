---
name: migration_helper_init
description: Initialize a new YARA-L rule directory structure and YARA-L rule file from the template.
---

# Initialize YARA-L Rule Directory

## Description
Initializes a new detection rule directory and `.yaral` rule template inside the workspace repository.

## When to Use This Skill
- Use this when you need to start migrating or creating a new rule and want to initialize the correct directory and file structure.
- Triggered when the user runs `/migration_helper_init <rule_name>` or requests initializing a rule directory.

## Instructions
Your primary role is to create a new directory `<rule_name>` inside `rules/` in the existing repository and initialize the `<rule_name>.yaral` file with the rule template.

1. **Autonomy & Planning:** Use absolute paths when creating folders & files. Be sure to present your plan and await approval.
2. **Directory Structure:** Create the following directory structure in the workspace repository:
   ```text
   ├── rules
   │   ├── <rule_name>
   │   │   └── <rule_name>.yaral
   │   └── sample_logs
   ```
3. **Template Copying & Replacement:** Create the file `rules/<rule_name>/<rule_name>.yaral` with the contents of the rule template located at `.agents/skills/migration_helper_init/references/rule_template.md`. Make sure to replace all instances of `{{args}}` (e.g., in `rule {{args}}`) with the actual `<rule_name>`.

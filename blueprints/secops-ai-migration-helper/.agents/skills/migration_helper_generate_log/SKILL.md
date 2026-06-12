---
name: migration_helper_generate_log
description: Generate a raw sample log entry in the original source format that will trigger the migrated YARA-L rule.
---

# Generate Sample Log for YARA-L Rule

## Description
Generates a RAW source log entry matching the legacy system format (e.g. Syslog, Windows XML, JSON, CSV) that will successfully trigger the YARA-L rule.

## When to Use This Skill
- Use this skill to produce realistic raw sample logs for rule verification, testing, and validation.
- Triggered by `/migration_helper_generate_log <rule_name>` (where `<rule_name>` is the name of the rule directory, i.e., `rules/<rule_name>/<rule_name>.yaral`).

## Instructions
You act as a Chronicle Security Engineer specializing in YARA-L rule validation. Your task is to generate a RAW source log (not UDM JSON) that will successfully trigger a specific detection rule.

### Steps:
1. **Rule Analysis:** Read `rules/<rule_name>/<rule_name>.yaral`. If the file content appears truncated or incomplete, stop and alert the user immediately. Analyze the `events` and `condition` sections to understand exactly which field values and logic will trigger a match.
2. **Identify Log Type:**
   - Extract the `log_type` from the rule metadata or event filters (e.g., `$log.metadata.log_type = "WINEVTLOG"`).
   - If the log type is explicitly defined, use it.
   - If the log type is unknown or ambiguous, **PAUSE** and propose the most likely type to the user (e.g., *"This looks like WINEVTLOG, should I proceed?"*).
3. **Multiple Log Types Handling:** 
   - If the rule requires multiple log types, generate multiple log sample files and place them in the same folder. For each log type, create a separate file named `<LOG_TYPE>.log`.
4. **Format Research:**
   - Search the local repository/workspace for existing logs matching the pattern `*<LOG_TYPE>*.log` (e.g., `IIS.log`) to use as a structural template.
   - If no local samples exist, search the internet or SecOps documentation for the official RAW schema/format for that specific log source.
5. **Multiple Log Entries from the Same Log Type Handling:** 
   - If the rule requires multiple log entries from the same log type, place them in the same file. Make sure to add a newline character after each log entry. 
   - Count carefully the number of log entries and make sure that the generated log entries reflect the expected format. If one log entry is missing, the rule will not be triggered.
6. **Log Generation:**
   - Generate a **RAW** log entry.
   - **CRITICAL:** Do NOT generate UDM JSON. The output must be in the original source format (e.g., Syslog, Windows XML/Event, JSON, CSV) as it would appear before ingestion into Chronicle.
   - Ensure the log contains the specific values required to satisfy the YARA-L rule conditions.
7. **Output & File Writing:**
   - Save the generated log to: `rules/<rule_name>/sample_logs/<LOG_TYPE>.log`.
   - *Example:* If the type is `"MICROSOFT_DEFENDER_CLOUD_ALERTS"`, save as `rules/<rule_name>/sample_logs/MICROSOFT_DEFENDER_CLOUD_ALERTS.log`.

### Constraints:
- Strict RAW format only. No UDM wrappers.
- **Validation:** Before finishing, verify that the generated log adheres to the known schema of the source log type.

```Title: Specific File Hash Detected 
   Description: Create a rule to alert when a specific file hash is present
   Severity: Medium 
   RuleId: 8301
   Source: https://docs.cloud.google.com/chronicle/docs/yara-l/transition_spl_yaral ```

| eval file_hashes="hash12345,hash67890,hashABCDE"
| makemv delim="," file_hashes
| mvexpand file_hashes
| search file_hashes="hash67890"
| table _time, file_hashes
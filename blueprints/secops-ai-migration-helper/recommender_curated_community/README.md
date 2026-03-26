# SecOps migraiton helper: recommender for curated and community rules based on custom rules  

**A GenAI powered migraiton**. The tool recommends curated and community rules that provide the simular security objective as the input rule that can be from different SIEM plattfrom, like Auzre Log Analytics, etc

**DESCRIPTION:**
  This script analyzes a set of customer-provided detection rules, like KQL, ArcSight, SPL etc, and recommends relevant
  curated and community rules. It can fetch curated rules live from the Chronicle SecOps content hub or
  use pre-loaded local files. The final recommendations are saved in both JSON and CSV formats.

**FUNCTIONALITY:**
- Loads latest curated rules from SecOps ContentHub instance. 
- Loads latest rule sets  from SecOps ContentHub instance
- Combines rule with rulesets rules with needed log sources
- Uses GenAI to classify the required log sources from the input rules
- Loads all community rules form flat file in the repo 
- Recommends curated and community rules with the same security objective to the input rules. Provides rational, log sources, rules sets, category and rule name
- Export the result to JSOn and CSV

**USAGE:**
  python recommender_curated_community.py

**CONFIGURATION (via Environment Variables)**:
  The script's behavior is configured through environment variables.
  Default values are shown in parentheses.

  [Content Hub Connection]

  - CONTENTHUB_PROJECT_ID:      Google Cloud Project ID for the content hub. 
  - CONTENTHUB_LOCATION:        Location of the content hub. (Default: "eu")
  - CONTENTHUB_INSTANCE_ID:     Instance ID for the content hub. 

  [AI Configuration]

  - AI_MODEL:                   The Vertex AI model to use for generation. (Default: "gemini-2.5-pro")

  [Input Files]

  - CUSTOMER_RULES_TO_EVALUATE: Path to the JSON file with customer rules. (Default: "./resources/sample_rules.json")
  - COMMUNITY_RULES:            Path to the text file with all community rules. (Default: "./resources/all_community_rules_20250816.txt")


  [Preloaded Curated Rules ]


  - CURATED_USE_PRELOADED_FILE: Set to "True" to use local files instead of fetching from the API. (Default: "False")
  - CURATED_RULES_FILE:         Path to the preloaded curated rules JSON file. (Default: "./resources/curated_rules.json")
  - CURATED_RULESETS_FILE:      Path to the preloaded curated rulesets JSON file. (Default: "./resources/curated_rulesets.json")

  [Output Files]

  - CURATED_RULES_OUTPUT_FILE:       Where to save fetched curated rules. (Default: "./work_dir/curated_rules.json")
  - CURATED_RULESETS_OUTPUT_FILE:    Where to save fetched curated rulesets. (Default: "./work_dir/curated_rulesets.json")
  - RECOMMENDATIONS_JSON_OUTPUT_FILE: Path for the final JSON recommendations. (Default: "./work_dir/recommendation_curated_community_rules.json")

**COMMUNITY RULES DUMP:**

Community rules are currently as one big dump file part of the repo, see file `./resources/all_community_rules_20250816.txt`  The size of file allows adding all in the LLM context. Cutomers prefer to focus on curated due to google support. You can generate the dump by 1) cloning the repo 2) `find . -type f -name "*.yaral" -print0 | xargs -0 cat > all_community_rules.txt`

**OUTPUT:**

  Files in the **work_dir**
  - **recommendation_curated_community.json** is JSON file with recommendations
    - Format:

   `[ { "ucid": "customer idenfifyer", "title": "Title of the rule" "description": "Desciption of the rule", "rule": "rule definition" }, "curated rules": "category, ruleset and rule name curated rules with same objecitve",
    "curated rules coverage": "yes|partially|no",
    "curated rationale": "crisp rationale and log sources needed",
    "community rules": "cathegory/rule_set/rules_name",
    "community rules coverage": "yes",
    "community rationale": "crisp rationale"}...]`
  - **curated_commjunity_recommendaiton.csv** is CSV file with recommendations suitable for table view 
  - **recommendation_curated_rulesets.csv** is CSV with recommended rulesets suitable a reverce lookupaka, which ruleset are recommended for the rules in thei batch


**Status:** PROTOTYPE

**TODO:**

 - (FEATURE) Missing unity tests 

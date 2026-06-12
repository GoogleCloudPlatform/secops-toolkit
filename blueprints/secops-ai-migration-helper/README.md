# SecOps AI Migration Helper 

**PROTOTYPE**

Migration helper is a tool that helps you migrate rules from a SIEM to Google SecOps and reduce the migration time significantly. It uses [Antigravity CLI](https://antigravity.google/docs/cli-overview)  or alternatively [Gemini CLI](https://github.com/google-gemini/gemini-cli) to help you migrate the rules in multiple steps. 

- The AI helper operates in clearly defined small steps, each with specific inputs and outputs. After you tune to your environment you can run all steps in one shot, see *Tune the Gemini CLI commands to your use case* .
- A SecOps Consultant (Human in the loop) validates the output after every step. For example: formatting an original rule, then manual visual validation, then adding comments, etc.
- A general all-in-one approach without tuning to your environment (e.g.  migrating everything without considering equivalence to curated rules) is counterproductive. 
- The more rules are migrated, the knowledge base of the GenAI tool increases and migration becomes more accurate. 
- The tool is flexible by understanding different formats of rules from a SIEM. It is not limited to the original language of the rule. 

**NOTE:** The step can be also executed with [Antigravity CLI](https://antigravity.google/docs/cli-overview)

Migration Steps overview ![Migration Steps Overview](./misc/yaral/images/steps_overview.png)

---

## Features

* **AI Migration helper** leveraging GenAI, SecOps MCP and Gemini CLI to automate the migration.
* **Recommender Tool**: A GenAI-powered script that maps existing rules (KQL, SPL, ArcSight, etc.) to equivalent Google SecOps Curated or Community rules.
---

## Installation

### Antigravity CLI 

Follow [Antigravity CLI](https://antigravity.google/docs/cli-getting-started)

### Gemini CLI 

Follow [Gemini CLI](https://github.com/google-gemini/gemini-cli)

### Setup SecOps MCP integration and Gemini CLI and Antigravity CLI

Before using gemini-cli or antigravity-cli please issue the following command to set the environment variable required for Vertex AI:

```bash
export GOOGLE_CLOUD_PROJECT="<your_gcp_project_id>"
export GOOGLE_CLOUD_LOCATION="global"
```

Then when you run the gemini command for the first time you might be asked to log in. When asked "How would you like to authenticate for this project?" choose "Vertex AI".

#### MCP SecOps setup 

Run the following commands:

```bash
gcloud config set project your-gcp-project
gcloud beta services mcp enable chronicle.googleapis.com --project=your-gcp-project
```

Configure GCP IAM for **SecOps MCP Access**

In order to access a Google Cloud Hosted MCP Server the principal (a user, service account, or group) will require the MCP Tool User IAM Role:
- MCP tool user

To use Google SecOps, the principal requires appropriate IAM permissions. A standard admin setup includes:

- Chronicle API Admin
- Chronicle SOAR Admin
- Service Usage Consumer
- Vertex AI User


Before accessing the Gemini CLI, make sure to configure the ~/.gemini/settings.json file leveraging the built in generate-settings.sh bash script. Execute such a script with the following parameters:

```bash
./generate_settings.sh <secops_project_id> <secops_region> <secops_instance_id>
```

The script will generate a settings.json file in the ~/.gemini/ directory and/or in the ~/.antigravitycli/ directory.

Please then run the following command to verify the MCP server integration:

```bash
/mcp list
```

It should return the Google SecOps MCP server in the list of available MCP servers. To try configuration of the SecOps MCP server, please use the following command:

```bash
"Please use the SecOps MCP to list my rules."
```

If successful, you should see a list of rules returned. If that is the case, you can proceed to the next step.


More information on how to configure gemini-cli with Google SecOps hosted MCP server integration available in the [Using Google SecOps with Gemini CLI and Hosted MCP](https://medium.com/@thatsiemguy/using-google-secops-with-gemini-cli-and-hosted-mcp-6400ec8aa99e)

---
## Usage

Start the Gemini CLI and execute a command with `/<command>` arguments. Following are described the commands and their arguments:

### Tune the skill/commands to your use case 
Every migration is different and it is very important to adapt the following Antigravity CLI skills (`.agents/skills/`) or Gemini CLI commands (`.gemini`) to your particular use case. Take several sample rules from your SIEM from different product types (e.g. EDR, WAF etc.) execute all steps one by one (/migration_helper:init, /migration_helper:format, /migration_helper:generate_yaral, /migration_helper:author_notes, /migration_helper:generate_log) and manually validate the output of each step. Adjust the command arguments accordingly until you get the desired output. After this, start the mass migration of the rules using the command /migration_helper:migrate_rule.

### Evaluate curated and community rules to replace legacy rules: 

Note: You can execute the recommendation also as a standalone Python script and set up parameters via environment variables. See [recommender_curated_community/README.md](./recommender_curated_community/README.md)

*All steps are with prefix `migration_helper` example gemini: /migration_helper:extract .. or antigravity /migration_helper_extract*

- `extract <file_path>`: Extracts the existing rules from a file in common formats like TXT, CSV, MD etc. to a structured JSON file. The input file format is not limited and automatically detected. The output format is structured JSON with the following fields:
  - **id**: Unique identifier of the rule
  - **title**: Title of the rule
  - **description**: Description of the rule
  - **rule**: Rule definition


- `recommend <file_path>`: Recommends curated and community detection rules that provide the same coverage as the input rules from the previous step. The input is a JSON file with structured rules from the previous step. The output is saved to the **work_dir** (see examples in `blueprints/secops-ai-migration-helper/recommender_curated_community/resources`): 
  - **recommendation_curated_community.json** is JSON file with recommendations
    - Format:

   `[ { "ucid": "customer identifier", "title": "Title of the rule", "description": "Description of the rule", "rule": "rule definition",
    "curated rules": "category, ruleset and rule name curated rules with same objective",
    "curated rules coverage": "yes|partially|no",
    "curated rationale": "crisp rationale and log sources needed",
    "community rules": "category/rule_set/rules_name",
    "community rules coverage": "yes",
    "community rationale": "crisp rationale"}...]`
  - **curated_community_recommendation.csv** is CSV file with recommendations suitable for table view 
  - **recommendation_curated_rulesets.csv** is CSV with recommended rulesets suitable a reverse lookup, a.k.a. which rulesets are recommended for the rules in this batch



### Migrate a rule to a custom rule: 
- `migrate <file_path>`: Migrate a rule to a custom rule, executing all the steps below in sequence.  This should be executed after you have tuned the prompt to your environment and executed all steps one by one manually multiple times. 
- `init <new_rule_name>`: Create new directory structure & `.yaral` rule from template 
- `format <migrating_rule_path> <new_rule_name>`: Take a migrating rule and format its contents for readability 
- `generate_yaral <new_rule_path>`: Generate equivalent YARA-L rule from any source 
- `generate_log <new_rule_path>`: Generate a sample log that would trigger on a given YARA-L rule 
- `author_notes <new_rule_path>`: Author rule notes, including dependencies, tuning, testing, docs and rule parameters 
- `validate <new_rule_path>`: Validate a rule’s YARA-L syntax against the SecOps MCP server, self-correcting as necessary 

### Directory Structure

Main files and directories:
- `recommender_curated_community/`: The Python recommender tool for discovering relevant curated or community rules, powered by Vertex AI models.
- `migration_rules/`: Examples and demonstration files of rules from distinct SIEM platforms (e.g., KQL, ArcSight, SPL). Place here the rule you want to migrate.
- `rules/`: Repository for the resulting YARA-L detection rules, with dedicated subdirectories for each rule including optional `sample_logs`. It contains some samples.

### Contributing
Contributions are welcome! Please feel free to submit a pull request with any improvements or bug fixes.

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature`).
3. Commit your changes (`git commit -am 'Add some feature'`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Create a new Pull Request.

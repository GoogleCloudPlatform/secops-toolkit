# 🤖 Gemini AI Integration for SecOps Parser Workflow

This directory contains configurations for integrating Google's Gemini AI directly into our SecOps parser development workflow.

The primary goal is to **automate the review of parser changes**. We use a custom `gemini-cli` command to execute an analysis and summarize the differences in normalized UDM (Unified Data Model) event output between parser versions, helping to quickly spot regressions or unintended side effects.

---

## Prerequisites

Before using this tool, you must have the following:

* **[gemini-cli](https://github.com/google/gemini-cli)**: The official command-line interface for the Gemini API.
* **git**: Required by the command to compare file versions.
* **`gemini` Command Execution**: This workflow relies on an advanced `gemini` setup that is configured to **execute local shell commands** (`git show` and file reads) as instructed by the prompt.

---

## 📊 Core Tool: Parser UDM Diff Command

The main tool in this workflow is a custom `gemini` command defined in **`.gemini/parser.toml`**. This command is aliased as `/secops:parser` for easy use.

### What it Does

The `parser.toml` prompt instructs the Gemini execution environment to perform the entire comparison task in one step:

1.  **Retrieve NEW Content**: Reads the `parsers/{{log_type}}/events/logs.yaml` file from the current directory.
2.  **Retrieve OLD Content**: Executes `git show HEAD:parsers/{{log_type}}/events/logs.yaml` to get the previous committed version.
3.  **Analyze Differences**: Compares the two versions with a specific focus on the **Important UDM Fields** critical for Google SecOps.
4.  **Generate Report**: Outputs a concise summary of all changes directly to your terminal.

### How to Use

The command is designed to be run from the **root of the repository**.

Simply execute the `gemini` command alias and the run the following command in the CLI:

```bash
 /secops:parser --log_type="WINDOWS_AD" # the log type for which gemini-cli should compare changes
 ```

```bash
# Example for OKTA parser
/secops:parser --log_type="OKTA"

# Example for Windows AD parser
/secops:parser --log_type="WINDOWS_AD"

# Example for PAN Firewall parser
/secops:parser --log_type="PAN_FIREWALL"
```

Example Output
You will see a Markdown-formatted report printed directly to your terminal:

```markdown
## 📊 UDM Change Analysis: OKTA

### 1. Executive Summary
No critical fields affected. `principal.user.userid` was modified, but this is an expected format change.

### 2. Important UDM Field Changes
* **principal.user.userid (MODIFIED):** Value format changed from 'user' to 'user@domain.com'.
* *(If no important fields were changed, state: "No changes detected in important UDM fields.")*

### 3. Other Notable Changes
* Added new field `udm.new_custom_field`.
```
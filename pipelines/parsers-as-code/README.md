# SecOps Parsers as Code

This repository provides a framework for managing SecOps parsers as code. It enables a robust GitOps workflow with
version control, automated local and remote validation, and a CI/CD pipeline that provides direct feedback on pull
requests before deploying changes.

### GitHub CICD Pipeline design

![GitHub CICD Pipeline](./images/diagram.png)

A brief workflow description:

1. **Develop and Commit:** A SOC engineer develops or modifies a parser within the Google SecOps tenant. After testing,
   the engineer brings the new or updated parser code into a local Git repository. They then upload sample logs and
   generate events leveraging an internal script, then commit the changes to a new feature branch and push it to GitHub.

2. **Create Pull Request**: The engineer creates a Pull Request (PR) in GitHub to merge the feature branch into the main
   branch.

3. **Verification and Deployment Pipeline**: Opening the PR automatically triggers a GitHub Actions pipeline. This
   pipeline uses a runner to validate the parser code and deploys the changes to a development or staging environment
   within Google SecOps for testing. The pipeline reports on the success of the validation and deployment within the PR.

4. **Review and Approval**: Another engineer reviews the proposed parser changes and the validation report from the
   pipeline directly in the PR. If the changes are acceptable and the pipeline is successful, they approve and merge the
   PR.

5. **Activation Pipeline**: Merging the PR triggers a final pipeline. This pipeline's job is to activate the newly validated
   and merged parser version in the production Google SecOps environment.

6. **Report Results**: The pipeline concludes by reporting the final activation status to the SOC engineering team, often via
   an automated notification like email.

---

## 🚀 Features

This framework is built around a two-stage deployment process managed by a CI/CD pipeline:

* **Verify and Deploy (`verify-deploy-parsers`):**
    1. **Local Validation:** Automatically runs the parser against all sample logs and compares the output with expected
       events to ensure correctness before submission.
    2. **Submit to SecOps:** Submits new or updated parsers to your SecOps instance.
    3. **Poll for Status:** Actively polls the SecOps API to get the final validation status (`PASSED`, `FAILED`,
       `INCOMPLETE`) from the SecOps backend.
    4. **PR Commenting:** Posts a detailed comment on the pull request with the outcome for each parser, using status
       emojis (✅, ❌, ⏳) for a clear and immediate feedback loop.

* **Activate Parsers (`activate-parsers`):**
    * After a pull request is merged, this command runs to activate the parsers that have been successfully validated by
      SecOps, completing the deployment process.

* **Generate Events (`generate-events`):**
    * A utility to locally generate the expected event output files in the `events/` directory by running the parser
      against the sample log files in the `logs/` directory.

---

## 📁 Folder Structure

For the scripts and pipeline to work correctly, your repository must adhere to the following structure, which now uses
dedicated `logs` and `events` subdirectories.

```
parsers-as-code/
├── .github/
│   └── workflows/
│       └── secops-pipeline.yml # Your GitHub Actions workflow file
├── parsers/
│   ├── <LOG_TYPE_A>/           # e.g., CISCO_ASA
│   │   ├── parser.conf         # The CBN parser configuration
│   │   ├── logs/               # Subdirectory for sample logs
│   │   │   ├── sample1.log
│   │   │   └── sample2.log
│   │   └── events/             # Subdirectory for expected events
│   │       ├── sample1.yaml
│   │       └── sample2.yaml
│   ├── <LOG_TYPE_B>/
│   │   └── ...
│   └── ...
├── main.py                     # Main Python script with Click commands
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

**Key components:**

* **`parsers/<LOG_TYPE>/`**: Each subdirectory under `parsers/` represents a unique log type.
    * **`parser.conf`**: Contains the actual SecOps parser configuration code.
    * **`logs/`**: A directory containing one or more files with raw sample log lines.
    * **`events/`**: A directory containing the expected normalized events in YAML format. Each `events/*.yaml` file
      corresponds to a `logs/*.log` file and is used for comparison during validation. These can be generated with the
      `generate-events` command.

---

## 🛠️ Local Setup

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd <your-repo-name>
   ```

2. **Create and activate a Python virtual environment (recommended):**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Environment Variables (for local execution):**
   To run `main.py` locally, export these variables in your shell:
   ```bash
   export SECOPS_CUSTOMER_ID="your-secops-customer-id"
   export SECOPS_PROJECT_ID="your-gcp-project-id"
   export SECOPS_REGION="your-secops-region" # e.g., eu, us

   # For local development, authenticate via the gcloud CLI
   gcloud auth application-default login
   ```
   Ensure your user has the necessary IAM permissions on the `SECOPS_PROJECT_ID` to interact with SecOps APIs.

---

## 💻 Script Usage (CLI)

The `main.py` script uses [Click](https://click.palletsprojects.com/) for its command-line interface.

**Primary Commands:**

* **Verify, Deploy, and Poll for Status:**
  This command runs the entire pre-merge workflow: local validation, submission to SecOps, and polling for the remote
  validation status.
    ```bash
    python main.py verify-deploy-parsers
    ```

* **Activate Merged Parsers:**
  This command activates parsers that have already been successfully validated. It is intended to be run by the CI/CD
  pipeline after a PR is merged.
    ```bash
    python main.py activate-parsers
    ```

* **Generate Local Event Files:**
  This command updates the `events/*.yaml` files by running the local `parser.conf` against the `logs/*.log` files. This
  is useful when you are developing or updating a parser.
    ```bash
    python main.py generate-events
    ```
  To generate events for only one specific parser:
    ```bash
    python main.py generate-events --parser <LOG_TYPE_NAME>
    ```

---

## ⚙️ GitHub Actions Pipeline

The CI/CD pipeline automates the two-stage deployment process.

### Github Actions Logic

**Stage 1: On Pull Request (Opened, Synchronized)**

1. The `verify-deploy-parsers` job is triggered.
2. It runs local validation against sample logs.
3. If local validation passes, it submits the changed parsers to SecOps.
4. It **polls** the SecOps API for up to 5 minutes, waiting for a final validation status (`PASSED` or `FAILED`).
5. It posts a **comment on the pull request** summarizing the results for each parser, indicating success (✅), failure (
   ❌), or timeout (⏳).
6. Merging is only allowed if this job succeeds.

**Stage 2: On Pull Request (Closed & Merged)**

1. The `activate-parsers` job is triggered.
2. It checks the status of the parsers from the merged branch one last time.
3. It runs the `activate-parsers` command to promote any parsers that are in a `PASSED` state to `ACTIVE` in SecOps.

### Environment Variables & Secrets

Configure the following in your GitHub repository settings (`Settings > Secrets and variables > Actions`):

**Workflow Environment Variables:**
These are non-sensitive and can be defined in the `env:` block of your workflow file.

```yaml
env:
  SECOPS_CUSTOMER_ID: "your-secops-customer-id"
  SECOPS_PROJECT_ID: "your-gcp-project-id"
  SECOPS_REGION: "your-secops-region"
  # For Workload Identity Federation (WIF)
  SERVICE_ACCOUNT: "your-gcp-service-account@your-project.iam.gserviceaccount.com"
  WIF_PROVIDER: "projects/your-gcp-project-number/locations/global/workloadIdentityPools/your-pool/providers/your-provider"
```

**IAM Permissions for Workload Identity Federation**

The GCP SERVICE_ACCOUNT used by the pipeline requires the following IAM permissions:

1- **Workload Identity User:**
Role: roles/iam.workloadIdentityUser
Principal: principalSet://iam.googleapis.com/projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/<POOL_ID>
/attribute.repository/<OWNER/REPO>

2- **SecOps API Permissions:**
Role: roles/chronicle.admin (easiest) or a custom role with the following permissions:

- chronicle.parsers.create
- chronicle.parsers.get
- chronicle.parsers.list
- chronicle.parsers.run
- chronicle.parsers.activate

## License

Copyright 2025 Google. This software is provided as-is, without warranty or representation for any use or purpose. Your
use of it is subject to your agreement with Google.  
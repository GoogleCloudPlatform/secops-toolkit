# Contributing

# How to contribute

We'd love to accept your patches and contributions to this project.

## Before you begin

### Sign our Contributor License Agreement

Contributions to this project must be accompanied by a
[Contributor License Agreement](https://cla.developers.google.com/about) (CLA).
You (or your employer) retain the copyright to your contribution; this simply
gives us permission to use and redistribute your contributions as part of the
project.

If you or your current employer have already signed the Google CLA (even if it
was for a different project), you probably don't need to do it again.

Visit <https://cla.developers.google.com/> to see your current agreements or to
sign a new one.

### Review our community guidelines

This project follows
[Google's Open Source Community Guidelines](https://opensource.google/conduct/).

## Contribution process

To ensure code quality, syntax correctness, and formatting consistency, this repository utilizes automated checks via GitHub Actions. You can run these validations locally before pushing your changes to the remote repository.

### Set up your environment

Create virtual environment for testing and generate docs

```shell
python3 -m venv ~/.venv-secops-toolkit
source ~/.venv-secops-toolkit/bin/activate
```

### Validate Python locally

We use [Ruff](https://docs.astral.sh/ruff/) as our standard Python linter to check for syntax errors, undefined names, unused imports, and code style issues.

1. **Install tool dependencies** (including Ruff):
   ```shell
   pip install -r tools/requirements.txt
   ```

2. **Run Ruff validation** across all Python scripts in the repository:
   ```shell
   ruff check .
   ```

3. **Run Ruff formatting** across all Python scripts in the repository:
   ```shell
   ruff format .
   ```

### Generate Terraform documentation

Generate tfdoc (example for `secops-tenant`)

```shell
./tools/tfdoc.py blueprints/secops-tenant
```

### Code reviews

All submissions, including submissions by project members, require review. We
use GitHub pull requests for this purpose. Consult
[GitHub Help](https://help.github.com/articles/about-pull-requests/) for more information on using pull requests.

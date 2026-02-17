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

### Useful Commands

Create virtual environment for testing and generate docs

```shell
python3 -m venv ~/.venv-secops-toolkit
source ~/.venv-secops-toolkit/bin/activate
```

Generate tfdoc (example for `secops-tenant`)

```shell
./tools/tfdoc.py blueprints/secops-tenant
```

#### Python Code formatting

```shell
yapf .  -i  --recursive     --exclude "**/.terraform/"     --exclude "tools/"     --exclude "tests/" --exclude "**/__pycache__" --exclude "**/venv/*" --exclude "**/data/" --exclude "**/**/requirements.txt"
```

### Code reviews

All submissions, including submissions by project members, require review. We
use GitHub pull requests for this purpose. Consult
[GitHub Help](https://help.github.com/articles/about-pull-requests/) for more information on using pull requests.
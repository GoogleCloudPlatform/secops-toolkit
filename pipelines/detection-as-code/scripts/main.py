#! /usr/bin/env python3
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import sys
import click
import os
import re
from secops import SecOpsClient
from pathlib import Path

logging.basicConfig(level=logging.INFO)


def initialize_chronicle_client():
  client = SecOpsClient()
  chronicle = client.chronicle(
      customer_id=os.environ.get("TF_VAR_secops_customer_id"),
      project_id=os.environ.get("TF_VAR_secops_project_id"),
      region=os.environ.get("TF_VAR_secops_region"))
  return chronicle


@click.group()
def cli():
  pass


@cli.command()
def verify_rules():
  '''Verify SecOps rules.'''
  chronicle = initialize_chronicle_client()

  for rule_file in [str(p) for p in Path("../rules").rglob("*.yaral")]:
    file_rule_name = rule_file.replace(".yaral", "").split("/")[-1]

    with open(rule_file, 'r') as rule:
      rule_text = rule.read()

      # check rule name is coherent with file name
      rule_name_match = re.search(r"rule\s+([a-zA-Z0-9_]+)\s+{", rule_text)
      if rule_name_match:
        rule_name = rule_name_match.group(1)
        if rule_name.casefold() != file_rule_name.casefold():
          logging.error(
              f"File with name {file_rule_name}.yaral contains rule which name is: {rule_name} which is not coherent, please rename file name or rule name in definition"
          )
          sys.exit(1)
      else:
        logging.info(f"Error extracting rule name from file {rule_name}.yaral")

      # check rule syntax is valid
      try:
        result = chronicle.validate_rule(rule_text=rule_text)
        if result.success:
          logging.info(f"Rule {rule_name} successfully verified")
        else:
          logging.error(f"Rule {rule_name} failed verification.")
          for diagnostic in result.compilation_diagnostics:
            logging.error(f"Error Message: {diagnostic.message}")
            logging.error(f"Position: {diagnostic.position}")
            logging.error(f"Severity: {diagnostic.severity}")
          sys.exit(1)
      except Exception as e:
        logging.error(f"Rule {rule_name} failed verification.")
        sys.exit(1)

  logging.debug("Finished")


if __name__ == "__main__":
  cli()

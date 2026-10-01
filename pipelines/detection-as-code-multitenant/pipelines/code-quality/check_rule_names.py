#!/usr/bin/env python3

# Copyright 2026 Google LLC
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
"""
Code Quality Check: YARA-L Rule Name and Filename Consistency Validator.

This script scans all YARA-L rule files (*.yaral) in the `rules/` directory tree
(excluding symbolic links) and verifies that the internal rule identifier defined
in the rule block (`rule <RuleName> {`) matches the base filename (`<RuleName>.yaral`).

Consistent naming ensures predictable rule deployments, accurate diffing against
Google SecOps APIs, and uniform rule tracking across multi-tenant environments.

Checks performed:
- Traverses `rules/` recursively, skipping symbolic links.
- Extracts rule names using regular expressions from `.yaral` content.
- Flags missing rule declarations, unreadable files, or filename mismatches.
- Exits with return code 4 if any naming discrepancies are found.
"""

import os
import re
import sys


def find_rule_name_in_content(file_content: str) -> str | None:
    """
    Extracts the rule name from the content of a YARA-L file using regex.
    The rule name is expected to be between the 'rule' keyword and the first '{'.

    Args:
        file_content: The string content of the .yaral file.

    Returns:
        The found rule name as a string, or None if not found.
    """

    # This regex finds a line starting with 'rule', captures the rule name,
    # and ends at the opening curly brace, accounting for whitespace.
    match = re.search(r"^\s*rule\s+([^\s{]+)\s*\{", file_content, re.MULTILINE)
    if match:
        return match.group(1)
    return None


def check_names():
    """
    Recursively finds .yaral files and validates that their filenames match
    the rule name defined inside the file. It skips symbolic links.
    """

    mismatch_count = 0
    file_count = 0

    for root, _, files in os.walk("rules"):
        for filename in files:
            file_path = os.path.join(root, filename)

            if os.path.islink(file_path):
                continue

            if not filename.endswith(".yaral"):
                continue

            file_count += 1

            expected_rule_name = os.path.splitext(filename)[0]

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                actual_rule_name = find_rule_name_in_content(content)

                if not actual_rule_name:
                    print(f"Could not find rule name inside {file_path}")
                    mismatch_count += 1
                elif expected_rule_name != actual_rule_name:
                    print(
                        f"Mismatch found in {file_path} (filename: {expected_rule_name}, content: {actual_rule_name})"
                    )
                    mismatch_count += 1

            except OSError as e:
                print(f"Could not read file {file_path}: {e}")
                mismatch_count += 1

    if mismatch_count == 0:
        print("All rule files are correctly named")
    else:
        print(f"Found {mismatch_count} issues")
        sys.exit(4)


if __name__ == "__main__":
    check_names()

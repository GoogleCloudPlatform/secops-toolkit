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

import difflib
import re
import yaml


def filter_lines(lines_list: list, ignore_patterns: list = None) -> list:
    """
    Filters lines from a list based on a list of regex patterns.

    Args:
        lines_list: A list of strings (lines).
        ignore_patterns: A list of regex patterns to ignore.

    Returns:
        A new list with the matching lines removed.
    """
    if not ignore_patterns:
        return lines_list
    return [
        line for line in lines_list
        if not any(re.search(pattern, line) for pattern in ignore_patterns)
    ]


def compare_yaml_files(file1_path: str,
                       file2_path: str,
                       ignore_patterns: list = None) -> list | None:
    """
    Compares two YAML files, ignoring specified patterns, and returns the differences.

    Args:
        file1_path: Path to the first YAML file.
        file2_path: Path to the second YAML file.
        ignore_patterns: A list of regex patterns to ignore in the comparison.

    Returns:
        A list of difference lines, or None if there are no differences.
    """
    with open(file1_path, 'r', encoding='utf-8') as f1:
        content1 = f1.read()
    with open(file2_path, 'r', encoding='utf-8') as f2:
        content2 = f2.read()

    try:
        data1 = yaml.safe_load(content1)
        data2 = yaml.safe_load(content2)
        processed_content1 = yaml.dump(data1,
                                       default_flow_style=False,
                                       sort_keys=True)
        processed_content2 = yaml.dump(data2,
                                       default_flow_style=False,
                                       sort_keys=True)
    except yaml.YAMLError:
        # Fallback to plain text if YAML is invalid
        processed_content1 = content1
        processed_content2 = content2

    lines1 = filter_lines(processed_content1.splitlines(), ignore_patterns)
    lines2 = filter_lines(processed_content2.splitlines(), ignore_patterns)

    diff_generator = difflib.Differ().compare(lines1, lines2)
    differences = [
        line for line in diff_generator if line.startswith(('+', '-'))
    ]
    return differences if differences else None


def process_data_for_dump(data):
    """
    Recursively processes data to be dumped to YAML.

    Currently, it sets the value of 'collectedTimestamp' to an empty string to
    ensure consistent comparisons for generated events.

    Args:
        data: The data structure (dict or list) to process.

    Returns:
        The processed data structure.
    """
    if isinstance(data, dict):
        return {
            k: '' if k == 'collectedTimestamp' else process_data_for_dump(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [process_data_for_dump(item) for item in data]
    return data

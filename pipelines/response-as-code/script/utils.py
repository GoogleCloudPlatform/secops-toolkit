#! /usr/bin/env python3
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

import difflib
import re
import yaml
import os
import logging
import json
from config import GITHUB_OUTPUT_FILE, PLAYBOOKS_PATH
from models import Workflow, File
import shutil

LOGGER = logging.getLogger("rac")
WD = os.path.abspath(".")


def get_local_playbook(playbook_name: str) -> Workflow | None:
    """Reads a playbook or block from the repo object store"""
    try:
        for playbook in get_file_objects_from_path(PLAYBOOKS_PATH):
            if playbook.path.endswith(f"/{playbook_name}.json"):
                return Workflow(json.loads(playbook.content))
    except (KeyError, FileNotFoundError):
        return None


def get_local_playbooks() -> list[Workflow]:
    try:
        for playbook in get_file_objects_from_path(PLAYBOOKS_PATH):
            if playbook.path.endswith(".json"):
                yield Workflow(json.loads(playbook.content))
    except (KeyError, FileNotFoundError):
        return []


def push_playbook(playbook: Workflow) -> None:
    """Writes a workflow to the repo"""
    _push_obj(
        playbook,
        playbook.name,
        "Playbook",
        f"{PLAYBOOKS_PATH}/{playbook.category}/{playbook.name}",
    )


def get_file_or_default(path, default=None):
    try:
        return LocalFolderManager.get_file_contents_from_path(path)
    except FileNotFoundError:
        return default


def push_obj(content, content_name, content_type, path):
    content.generate_readme(
        self.metadata.get_readme_addon(content_type, content_name))
    self.sync.update_objects(content.iter_files(), base_path=path)


def update_objects(files: list[File], base_path: str = ""):
    """Main method to edit objects in the repo."""
    return self.sync.update_objects(files=files,
                                    base_path=base_path,
                                    replace_content_in_base_path=False)


def push_file(path: str, content):
    self.sync.update_objects([File(path, self._json_encoder(content))])


@staticmethod
def _json_encoder(d: dict) -> str:
    return json.dumps(d, indent=4)


def _push_obj(content, content_name, content_type, path) -> None:
    content.generate_readme()
    update_objects(content.iter_files(),
                   base_path=path,
                   replace_content_in_base_path=False)


def update_objects(files: list[File],
                   base_path: str = "",
                   replace_content_in_base_path: bool = False) -> None:
    """
    Creates or updates specified files in the working directory, with an option
    to replace all content within a specified base_path.

    Behavior regarding existing content in `base_path` is controlled by
    the `replace_content_in_base_path` flag.

    - If `base_path` is provided (is a non-empty string) AND `replace_content_in_base_path` is True:
      The contents of the subdirectory specified by `base_path` (relative to
      `self.wd`) will be ENTIRELY REPLACED by the provided `files`. Existing items
      (files and subdirectories) in that `base_path` subdirectory not present
      in the `files` list (implicitly, as new content) will be deleted.

    - If `base_path` is provided AND `replace_content_in_base_path` is False:
      Files from the `files` list are created or updated within the `base_path`
      subdirectory. Existing items in that subdirectory not affected by the
      `files` list are unaffected (not deleted).

    - If `base_path` is empty (or not provided):
      Files are created or updated directly within the main working directory (`self.wd`).
      The `replace_content_in_base_path` flag has NO EFFECT in this case;
      existing items in `self.wd` not in the `files` list are always unaffected.

    In all cases, the `path` attribute of each `File` object in the `files` list
    is treated as relative to the `effective_target_dir` (which is `self.wd` if
    `base_path` is empty, or `os.path.join(self.wd, base_path)` if `base_path` is provided).

    Args:
        files (list[File]): A list of File objects to write.
                            Each File object must have a 'path' (str, relative)
                            and 'content' (bytes) attribute.
        base_path (str, optional): Relative path to a subdirectory within the
                                    working directory. Defaults to "".
        replace_content_in_base_path (bool, optional): If True and `base_path` is provided,
                                    the content of the `base_path` subdirectory
                                    is fully replaced. Defaults to False.
    """
    effective_target_dir = os.path.join(WD, base_path)

    if base_path:  # True if base_path is not an empty string
        if replace_content_in_base_path:
            LOGGER.info(
                f"Mode: Replace content. Target directory: {effective_target_dir}"
            )

            if os.path.exists(effective_target_dir):
                if not os.path.isdir(effective_target_dir):
                    LOGGER.error(
                        f"Path {effective_target_dir} exists but is not a directory. Cannot replace content."
                    )
                    raise NotADirectoryError(
                        f"Target path for replacement '{effective_target_dir}' is not a directory."
                    )
                try:
                    LOGGER.debug(
                        f"Clearing directory for replacement: {effective_target_dir}"
                    )
                    for item_name in os.listdir(effective_target_dir):
                        item_path = os.path.join(effective_target_dir,
                                                 item_name)
                        if os.path.isfile(item_path) or os.path.islink(
                                item_path):
                            os.unlink(item_path)
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path)  # shutil is needed here
                    LOGGER.debug(
                        f"Successfully cleared directory: {effective_target_dir}"
                    )
                except Exception as e:
                    LOGGER.error(
                        f"Failed to clear directory {effective_target_dir} for replacement: {e}"
                    )
                    raise

            # Ensure the directory exists (it might have been just cleared or never existed)
            try:
                os.makedirs(effective_target_dir, exist_ok=True)
                LOGGER.debug(
                    f"Ensured directory exists for writing new content: {effective_target_dir}"
                )
            except OSError as e:
                LOGGER.error(
                    f"Failed to create directory {effective_target_dir} after clearing/for replacement: {e}"
                )
                raise
        else:  # base_path is provided, but replace_content_in_base_path is False
            LOGGER.info(
                f"Mode: Update/Create within base_path (no replacement). Target directory: {effective_target_dir}"
            )
            try:
                os.makedirs(effective_target_dir,
                            exist_ok=True)  # Ensure base_path dir exists
                LOGGER.debug(
                    f"Ensured base directory exists: {effective_target_dir}")
            except OSError as e:
                LOGGER.error(
                    f"Failed to create base directory {effective_target_dir}: {e}"
                )
                raise
    else:  # base_path is empty
        LOGGER.info(
            f"Mode: Update/Create in working directory (no replacement). Target directory: {WD}"
        )

    # --- Common file writing loop ---
    for file_obj in files:
        if not hasattr(file_obj, 'path') or not hasattr(file_obj, 'content'):
            LOGGER.warning(
                f"Skipping object due to missing 'path' or 'content' attributes: {file_obj}"
            )
            continue
        if not isinstance(file_obj.path, str) or not isinstance(
                file_obj.content, bytes):
            LOGGER.warning(
                f"Skipping object due to incorrect type for 'path' (str expected) or 'content' (bytes expected): path='{file_obj.path}'"
            )
            continue
        if not file_obj.path:  # Path should not be empty
            LOGGER.warning(f"Skipping object with empty path: {file_obj}")
            continue

        # file_obj.path is relative to effective_target_dir.
        # Normalize to handle mixed slashes (e.g., `foo/bar` vs `foo\\bar`), ".." etc.
        relative_path_in_file_obj = os.path.normpath(file_obj.path)

        # Security check: ensure the normalized path is truly relative and does not try to escape.
        if os.path.isabs(relative_path_in_file_obj) or \
                relative_path_in_file_obj.startswith("..") or \
                (os.path.sep + ".." in relative_path_in_file_obj) or \
                (".." + os.path.sep in relative_path_in_file_obj and relative_path_in_file_obj.index(".." + os.path.sep) == 0) : # Catches "../" at start on unix
            LOGGER.error(
                f"Security risk: Invalid file path '{file_obj.path}' (normalized: '{relative_path_in_file_obj}'). "
                "Path must be relative and confined to the target directory.")
            continue

        full_file_path = os.path.join(effective_target_dir,
                                      relative_path_in_file_obj)

        try:
            # Ensure the parent directory for this specific file exists.
            parent_directory = os.path.dirname(full_file_path)

            # Only call makedirs if parent_directory is not empty and exists
            if parent_directory:  # An empty parent_directory means file is in the current dir
                os.makedirs(parent_directory, exist_ok=True)

            # Write the file (creates if new, overwrites if existing).
            with open(full_file_path, "wb") as f:
                f.write(file_obj.content)
            LOGGER.debug(
                f"Successfully wrote (created/updated) file: {full_file_path}")

        except IOError as e:  # More specific than just Exception for file I/O
            LOGGER.error(f"IOError writing file {full_file_path}: {e}")
        except OSError as e:  # Broader OS-level errors, like permission issues during makedirs
            LOGGER.error(f"OSError related to path {full_file_path}: {e}")
        except Exception as e:  # Catch-all for other unexpected errors
            LOGGER.error(
                f"Unexpected error writing file {full_file_path}: {e}")

    LOGGER.info(f"Finished all file operations for: {effective_target_dir}")


def get_file_objects_from_path(dir_path: str = "") -> list[File]:
    """
    Gets a list of File objects from a specified path relative to the working directory.
    If dir_path points to a directory, it recursively finds all files within it.
    If dir_path points to a file, it returns a list containing a single File object for that file.
    Paths in the returned File objects are relative to the working directory (self.wd).

    Args:
        dir_path (str, optional): Path relative to the working directory.
                                  Defaults to "" (representing the working directory itself).

    Returns:
        list[File]: A list of File objects.

    Raises:
        FileNotFoundError: If the initial dir_path (resolved to an absolute path) does not exist.
    """
    search_root_abs = os.path.normpath(os.path.join(WD, dir_path))

    if not os.path.exists(search_root_abs):
        LOGGER.warning(f"Path not found: {search_root_abs}")
        raise FileNotFoundError(f"Path not found: {search_root_abs}")

    files_found = []

    if os.path.isfile(search_root_abs):
        try:
            with open(search_root_abs, "rb") as f:
                content = f.read()
            relative_path = os.path.relpath(search_root_abs, WD)
            files_found.append(File(path=relative_path, content=content))
            LOGGER.debug(f"Retrieved file: {relative_path}")
        except IOError as e:
            LOGGER.error(f"Failed to read file {search_root_abs}: {e}")
    elif os.path.isdir(search_root_abs):
        LOGGER.debug(f"Searching for files in directory: {search_root_abs}")
        for root, _, filenames in os.walk(search_root_abs):
            for filename in filenames:
                file_abs_path = os.path.join(root, filename)
                # Ensure we are not picking up directories that might be named like files in some OS walk implementations
                if not os.path.isfile(file_abs_path):
                    continue
                try:
                    with open(file_abs_path, "rb") as f:
                        content = f.read()
                    relative_path = os.path.relpath(file_abs_path, WD)
                    files_found.append(
                        File(path=relative_path, contents=content))
                    LOGGER.debug(
                        f"Retrieved file from directory walk: {relative_path}")
                except IOError as e:
                    LOGGER.error(f"Failed to read file {file_abs_path}: {e}")

    return files_found


# def generate_pr_comment_output(plan: dict, submitted_info: list,
#                                has_errors: bool):
#     """Generates a structured JSON output for a GitHub PR comment."""
#     LOGGER.info("\n--- Generating output for PR comment ---")
#     submitted_map = {info['log_type']: info for info in submitted_info}
#     report_lines = ["\n"]

#     for log_type, details in sorted(plan.items()):
#         if (details.parser_operation == Operation.NONE
#                 and details.parser_ext_operation == Operation.NONE
#                 and not details.validation_failed):
#             continue

#         line_parts = [f"- **Log Type**: `{log_type}`"]

#         # --- Parser Details ---
#         if details.config.parser:
#             action = details.parser_operation
#             line_parts.append(f"  - **Parser Action**: `{action.value}`")

#             if details.validation_failed:
#                 status_text, icon = "EVENT_VALIDATION_FAILED", "❌"
#                 details_text = "Not submitted due to local event validation failure."
#             elif action in [
#                     Operation.CREATE, Operation.UPDATE, Operation.RELEASE
#             ]:
#                 if action == Operation.RELEASE:
#                     status_text = "READY_TO_RELEASE"
#                     details_text = "Pending Release Candidate matched. Ready for activation key."
#                     icon = "🚀"
#                 else:
#                     status = details.parser_validation_status or "PENDING"
#                     icon = "✅" if status == ParserValidationStatus.PASSED.value else "❌" if status == ParserValidationStatus.FAILED.value else "⏳"
#                     status_text = f"{status} {icon}"
#                     parser_id = submitted_map.get(log_type,
#                                                   {}).get('parser_id', 'N/A')
#                     details_text = f"Submitted for deployment. Parser ID: `{parser_id}`"
#             else:  # Operation is NONE, but we're here because something else happened (e.g., ext change)
#                 status_text = "NO_CHANGE"
#                 details_text = "No changes detected for the parser."

#             line_parts.append(f"  - **Validation Status**: {status_text}")
#             line_parts.append(f"  - **Details**: {details_text}")

#         # --- Parser Extension Details ---
#         if details.config.parser_ext:
#             action = details.parser_ext_operation
#             line_parts.append(
#                 f"  - **Parser Extension Action**: `{action.value}`")

#             if details.validation_failed:
#                 status_text, icon = "EVENT_VALIDATION_FAILED", "❌"
#                 details_text = "Not submitted due to local event validation failure."
#             elif action in [Operation.CREATE, Operation.UPDATE]:
#                 status = details.parser_ext_validation_status or "PENDING"
#                 icon = "✅" if status == ParserExtensionState.VALIDATED.value else "❌" if status == ParserExtensionState.REJECTED.value else "⏳"
#                 status_text = f"{status} {icon}"
#                 ext_id = submitted_map.get(log_type,
#                                            {}).get('parser_ext_id', 'N/A')
#                 details_text = f"Submitted for deployment. Extension ID: `{ext_id}`"
#             else:  # Operation is NONE
#                 status_text = "NO_CHANGE"
#                 details_text = "No changes detected for the parser extension."

#             line_parts.append(f"  - **Validation Status**: {status_text}")
#             line_parts.append(f"  - **Details**: {details_text}")

#         # --- Comparison Report ---
#         if details.comparison_report:
#             report = details.comparison_report
#             line_parts.append(
#                 f"\n<details><summary><b>📉 UDM Comparison Report</b></summary>\n\n```text\n{report}\n```\n</details>"
#             )

#         report_lines.append("\n".join(line_parts))

#     body = "\n\n".join(report_lines)

#     if has_errors:
#         title = "❌ Parser Deployment Failed"
#         summary = "Errors were encountered during the process. See action logs for details."
#     elif not submitted_info and not report_lines:
#         title = "✅ All Parsers Up-to-Date"
#         summary = "No changes were needed for any parsers or extensions."
#         body = "All configurations in the repository are in sync with the active versions in Chronicle."
#     else:
#         title = "✅ Parser Deployment Plan"
#         summary = f"{len(submitted_info)} log type(s) had changes submitted. Review validation status below."

#     comment_data = {"title": title, "summary": summary, "details": body}

#     if GITHUB_OUTPUT_FILE:
#         LOGGER.info("Writing PR comment data to GITHUB_OUTPUT.")
#         json_output = json.dumps(comment_data)
#         try:
#             with open(GITHUB_OUTPUT_FILE, "a") as f:
#                 f.write(f"pr_comment_data<<EOF\n{json_output}\nEOF\n")
#         except IOError as e:
#             LOGGER.error(f"Failed to write to GITHUB_OUTPUT file: {e}")
#             LOGGER.info(
#                 f"PR Comment Data (fallback):\n{json.dumps(comment_data, indent=2)}"
#             )
#     else:
#         LOGGER.info(
#             f"PR Comment Data (simulation - GITHUB_OUTPUT not set):\n{json.dumps(comment_data, indent=2)}"
#         )

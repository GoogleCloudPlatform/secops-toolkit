# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import shutil
import logging

# Assuming soar.definitions.File is defined elsewhere.
# If not, and for testing purposes, you can use this placeholder:
#
# class File:
#     def __init__(self, path: str, content: bytes):
#         self.path = path  # Relative path to the file
#         self.content = content # File content as bytes
#
# try:
#     from soar.definitions import File
# except ImportError:
#     # Using the placeholder File class if soar.definitions is not available
#     logging.warning(
#         "soar.definitions.File not found. Using a placeholder definition. "
#         "Ensure 'File' has 'path: str' and 'content: bytes' attributes."
#     )
#     pass # Fallback to placeholder defined above or ensure it's defined before this class

# It's good practice to ensure File is defined. For this example, let's ensure a dummy one if not imported.
from soar.definitions import File

LOGGER = logging.getLogger("soar")


class LocalFolderManager:
    """Manages files and folders in a local directory."""

    def __init__(self, working_directory: str):
        """
        Initializes the LocalFolderManager.

        Args:
            working_directory (str): Path to the local directory to manage.
                                     This directory will be created if it doesn't exist.
        """
        self.wd = os.path.abspath(working_directory)

        if not os.path.isdir(self.wd):
            try:
                os.makedirs(self.wd, exist_ok=True)
                LOGGER.info(f"Created working directory: {self.wd}")
            except OSError as e:
                LOGGER.error(
                    f"Failed to create working directory {self.wd}: {e}")
                raise
        else:
            LOGGER.info(f"Using existing working directory: {self.wd}")

    def update_objects(self,
                       files: list[File],
                       base_path: str = "",
                       replace_content_in_base_path: bool = True) -> None:
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
        effective_target_dir = os.path.join(self.wd, base_path)

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
                                shutil.rmtree(
                                    item_path)  # shutil is needed here
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
                        f"Ensured base directory exists: {effective_target_dir}"
                    )
                except OSError as e:
                    LOGGER.error(
                        f"Failed to create base directory {effective_target_dir}: {e}"
                    )
                    raise
        else:  # base_path is empty
            # effective_target_dir is self.wd. The flag has no effect here.
            LOGGER.info(
                f"Mode: Update/Create in working directory (no replacement). Target directory: {self.wd}"
            )
            # self.wd is guaranteed to exist by __init__, no need for os.makedirs(effective_target_dir, ...) here.

        # --- Common file writing loop ---
        for file_obj in files:
            if not hasattr(file_obj, 'path') or not hasattr(
                    file_obj, 'content'):
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
                    "Path must be relative and confined to the target directory."
                )
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
                    f"Successfully wrote (created/updated) file: {full_file_path}"
                )

            except IOError as e:  # More specific than just Exception for file I/O
                LOGGER.error(f"IOError writing file {full_file_path}: {e}")
            except OSError as e:  # Broader OS-level errors, like permission issues during makedirs
                LOGGER.error(f"OSError related to path {full_file_path}: {e}")
            except Exception as e:  # Catch-all for other unexpected errors
                LOGGER.error(
                    f"Unexpected error writing file {full_file_path}: {e}")

        LOGGER.info(
            f"Finished all file operations for: {effective_target_dir}")

    def get_file_objects_from_path(self, dir_path: str = "") -> list[File]:
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
        search_root_abs = os.path.normpath(os.path.join(self.wd, dir_path))

        if not os.path.exists(search_root_abs):
            LOGGER.warning(f"Path not found: {search_root_abs}")
            raise FileNotFoundError(f"Path not found: {search_root_abs}")

        files_found = []

        if os.path.isfile(search_root_abs):
            try:
                with open(search_root_abs, "rb") as f:
                    content = f.read()
                relative_path = os.path.relpath(search_root_abs, self.wd)
                files_found.append(File(path=relative_path, content=content))
                LOGGER.debug(f"Retrieved file: {relative_path}")
            except IOError as e:
                LOGGER.error(f"Failed to read file {search_root_abs}: {e}")
        elif os.path.isdir(search_root_abs):
            LOGGER.debug(
                f"Searching for files in directory: {search_root_abs}")
            for root, _, filenames in os.walk(search_root_abs):
                for filename in filenames:
                    file_abs_path = os.path.join(root, filename)
                    # Ensure we are not picking up directories that might be named like files in some OS walk implementations
                    if not os.path.isfile(file_abs_path):
                        continue
                    try:
                        with open(file_abs_path, "rb") as f:
                            content = f.read()
                        relative_path = os.path.relpath(file_abs_path, self.wd)
                        files_found.append(
                            File(path=relative_path, contents=content))
                        LOGGER.debug(
                            f"Retrieved file from directory walk: {relative_path}"
                        )
                    except IOError as e:
                        LOGGER.error(
                            f"Failed to read file {file_abs_path}: {e}")

        return files_found

    def get_file_contents_from_path(self, file_path: str) -> bytes:
        """
        Gets the content of a specific file from a path relative to the working directory.

        Args:
            file_path (str): Path to the file, relative to the working directory.

        Returns:
            bytes: File contents.

        Raises:
            FileNotFoundError: If the file is not found.
            IsADirectoryError: If the path points to a directory.
        """
        full_path = os.path.normpath(os.path.join(self.wd, file_path))
        LOGGER.debug(f"Attempting to read file: {full_path}")

        if not os.path.exists(full_path):  # Check existence first
            LOGGER.warning(f"File not found: {full_path}")
            raise FileNotFoundError(f"File not found: {full_path}")
        if not os.path.isfile(full_path):  # Then check if it's a file
            LOGGER.warning(
                f"Path is not a file (it might be a directory): {full_path}")
            # More specific error if it's a directory
            if os.path.isdir(full_path):
                raise IsADirectoryError(
                    f"Path is a directory, not a file: {full_path}")
            raise FileNotFoundError(
                f"Path is not a file: {full_path}")  # Or some other error

        try:
            with open(full_path, "rb") as f:
                content = f.read()
            LOGGER.info(f"Successfully read file: {full_path}")
            return content
        except IOError as e:
            LOGGER.error(f"Failed to read file {full_path}: {e}")
            raise

    def list_all_files(self, sub_path: str = "") -> list[str]:
        """
        Lists all file paths recursively within a given sub_path of the working directory.
        Paths returned are relative to the working directory.

        Args:
            sub_path (str, optional): Subdirectory relative to the working directory.
                                     Defaults to "" (list from root of working directory).

        Returns:
            list[str]: A list of file paths relative to self.wd. Returns empty list
                       if sub_path is not a directory or does not exist.
        """
        list_root_abs = os.path.normpath(os.path.join(self.wd, sub_path))

        if not os.path.isdir(list_root_abs):
            LOGGER.warning(
                f"Cannot list files, path is not a directory or does not exist: {list_root_abs}"
            )
            return []

        LOGGER.debug(f"Listing files in: {list_root_abs}")
        relative_file_paths = []
        for root, _, filenames in os.walk(list_root_abs):
            for filename in filenames:
                file_abs_path = os.path.join(root, filename)
                if not os.path.isfile(file_abs_path):  # Ensure it's a file
                    continue
                relative_path = os.path.relpath(file_abs_path, self.wd)
                relative_file_paths.append(relative_path)
        LOGGER.debug(
            f"Found {len(relative_file_paths)} files in {list_root_abs}.")
        return relative_file_paths

    def path_exists(self, path: str) -> bool:
        """
        Checks if a path (file or directory) exists relative to the working directory.

        Args:
            path (str): Path relative to the working directory.

        Returns:
            bool: True if the path exists, False otherwise.
        """
        full_path = os.path.normpath(os.path.join(self.wd, path))
        exists = os.path.exists(full_path)
        LOGGER.debug(
            f"Path '{full_path}' {'exists' if exists else 'does not exist'}.")
        return exists

    def is_directory(self, path: str) -> bool:
        """
        Checks if a path relative to the working directory is an existing directory.

        Args:
            path (str): Path relative to the working directory.

        Returns:
            bool: True if the path is an existing directory, False otherwise.
        """
        full_path = os.path.normpath(os.path.join(self.wd, path))
        is_dir = os.path.isdir(full_path)
        LOGGER.debug(
            f"Path '{full_path}' {'is' if is_dir else 'is not'} an existing directory."
        )
        return is_dir

    def is_file(self, path: str) -> bool:
        """
        Checks if a path relative to the working directory is an existing file.

        Args:
            path (str): Path relative to the working directory.

        Returns:
            bool: True if the path is an existing file, False otherwise.
        """
        full_path = os.path.normpath(os.path.join(self.wd, path))
        is_f = os.path.isfile(full_path)
        LOGGER.debug(
            f"Path '{full_path}' {'is' if is_f else 'is not'} an existing file."
        )
        return is_f

    def delete_path(self, path: str) -> bool:
        """
        Deletes a file or a directory (recursively) relative to the working directory.

        Args:
            path (str): Path relative to the working directory to be deleted.

        Returns:
            bool: True if deletion was successful or path didn't exist initially.
                  False if an error occurred during deletion.
        """
        full_path = os.path.normpath(os.path.join(self.wd, path))

        # Prevent accidental deletion of the entire working directory if path is empty or "."
        if full_path == self.wd and (not path or path == "."
                                     or path == os.path.sep):
            LOGGER.error(
                f"Attempt to delete the root working directory ('{full_path}') is not allowed via empty or '.' path. Specify a sub-path or use a dedicated function for clearing the root."
            )
            return False

        LOGGER.info(f"Attempting to delete path: {full_path}")

        if not os.path.exists(full_path):
            LOGGER.warning(f"Path not found, cannot delete: {full_path}")
            return True  # Considered successful as the path is already absent

        try:
            if os.path.isfile(full_path) or os.path.islink(full_path):
                os.unlink(full_path)
                LOGGER.info(f"Deleted file/link: {full_path}")
            elif os.path.isdir(full_path):
                shutil.rmtree(full_path)
                LOGGER.info(f"Deleted directory and its contents: {full_path}")
            return True
        except Exception as e:
            LOGGER.error(f"Failed to delete path {full_path}: {e}")
            return False

    def log_listed_files(self, sub_path: str = "") -> None:
        """
        Logs all file paths recursively within a given sub_path of the working directory.
        This method mirrors the logging behavior of the original `list_files` method.

        Args:
            sub_path (str, optional): Subdirectory relative to the working directory.
                                     Defaults to "" (lists from the root of the working directory).
        """
        list_root_abs = os.path.normpath(os.path.join(self.wd, sub_path))
        if not os.path.isdir(list_root_abs):
            LOGGER.warning(
                f"Cannot list files for logging, path is not a directory or does not exist: {list_root_abs}"
            )
            return

        LOGGER.info(f"Logging files in: {list_root_abs}")
        count = 0
        for root, _, filenames in os.walk(list_root_abs):
            for filename in filenames:
                file_abs_path = os.path.join(root, filename)
                if not os.path.isfile(file_abs_path):
                    continue
                relative_path = os.path.relpath(file_abs_path, self.wd)
                LOGGER.info(f"File: {relative_path}"
                            )  # Original just logged the dulwich file object
                count += 1
        LOGGER.info(f"Finished logging {count} files from {list_root_abs}.")

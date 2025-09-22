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
"""Manage data tables in Google SecOps."""

import csv
import json
import logging
import pathlib
from typing import Any, Literal, Mapping, Sequence

import pydantic
import ruamel.yaml
from secops.chronicle import ChronicleClient
from secops.chronicle.data_table import DataTableColumnType

from config import (
    CUSTOMER_ID,
    DATA_TABLE_CONFIG_FILE,
    DATA_TABLES_DIR,
    PROJECT_ID,
    REGION,
)

DATA_TABLE_COLUMN_TYPES = Literal["CIDR", "STRING", "REGEX"]

LOGGER = logging.getLogger(__name__)

# Use ruamel.yaml to raise an exception if a YAML file contains duplicate keys
ruamel_yaml = ruamel.yaml.YAML(typ="safe")


class DataTablesError(Exception):
    """Base exception for data table errors."""


class DataTableNotFoundError(DataTablesError):
    """Raised when a data table is not found."""


class InvalidDataTableConfigError(DataTablesError):
    """Raised when data table configuration is invalid."""


class DataTableColumn(pydantic.BaseModel):
    """Class for a data table column."""
    column_index: int | None
    original_column: str
    column_type: str | None
    mapped_column_path: str | None
    key_column: bool | None


class DataTable(pydantic.BaseModel):
    """Class for a data table."""
    name: str
    description: str | None
    columns: Sequence[DataTableColumn]
    row_time_to_live: str | None
    scopes: list[str] | None
    resource_name: str | None = None
    uuid: str | None = None
    create_time: str | None = None
    update_time: str | None = None
    rules: list[str] | None = None
    rule_associations_count: int | None = None


class DataTables:
    """Class used to manage data tables."""

    def __init__(self, data_tables: Sequence[DataTable]):
        self.data_tables: Sequence[DataTable] = data_tables

    @classmethod
    def parse_data_table(cls, data_table: Mapping[str, Any]) -> DataTable:
        """Parse a data table into a DataTable object."""
        try:
            return DataTable(
                name=data_table["displayName"],
                resource_name=data_table.get("name"),
                uuid=data_table.get("dataTableUuid"),
                description=data_table.get("description"),
                create_time=data_table.get("createTime"),
                update_time=data_table.get("updateTime"),
                columns=cls.parse_data_table_columns(
                    columns=data_table["columnInfo"]),
                row_time_to_live=data_table.get("rowTimeToLive"),
                rules=data_table.get("rules"),
                rule_associations_count=data_table.get(
                    "ruleAssociationsCount"),
                scopes=(data_table["scopeInfo"]["dataAccessScopes"]
                        if data_table.get("scopeInfo") else None),
            )
        except pydantic.ValidationError as e:
            LOGGER.error(
                "ValidationError occurred for data table %s\n%s",
                data_table,
                json.dumps(e.errors(), indent=4),
            )
            raise

    @classmethod
    def parse_data_tables(
            cls, data_tables: Sequence[Mapping[str, Any]]) -> list[DataTable]:
        """Parse a list of data tables into a list of DataTable objects."""
        return [cls.parse_data_table(dt) for dt in data_tables]

    @classmethod
    def load_data_table_config(
        cls,
        data_table_config_file: pathlib.Path = DATA_TABLE_CONFIG_FILE,
        data_tables_dir: pathlib.Path = DATA_TABLES_DIR,
    ) -> Mapping[str, DataTable]:
        """Load data table config from file."""
        LOGGER.info("Loading data table config from file %s",
                    data_table_config_file)
        with open(data_table_config_file, "r", encoding="utf-8") as f:
            data_table_config = ruamel_yaml.load(f)

        if not data_table_config:
            LOGGER.info("Data table config file is empty.")
            return {}

        cls.check_data_table_config(data_table_config)
        cls.validate_data_table_files(data_table_config, data_tables_dir)

        parsed_config = {}
        for name, config_entry in data_table_config.items():
            try:
                parsed_config[name] = DataTable(
                    name=name,
                    description=config_entry.get("description"),
                    columns=cls.parse_data_table_config_entry_columns(
                        columns=config_entry.get("columns")),
                    row_time_to_live=config_entry.get("row_time_to_live"),
                    scopes=config_entry.get("scopes"),
                )
            except pydantic.ValidationError as e:
                LOGGER.error(
                    "ValidationError occurred for data table config entry %s\n%s",
                    name,
                    json.dumps(e.errors(), indent=4),
                )
                raise
        LOGGER.info(
            "Loaded metadata and config for %d data tables from %s",
            len(parsed_config),
            data_tables_dir,
        )
        return parsed_config

    @classmethod
    def validate_data_table_files(cls, config: Mapping[str, Any],
                                  data_tables_dir: pathlib.Path):
        """Validate that data table files and config match."""
        csv_files = {p.stem for p in data_tables_dir.glob("*.csv")}
        config_keys = set(config.keys())

        missing_files = config_keys - csv_files
        if missing_files:
            raise InvalidDataTableConfigError(
                f"Data table files not found for: {', '.join(missing_files)}")

        extra_files = csv_files - config_keys
        if extra_files:
            raise InvalidDataTableConfigError(
                f"Data tables not in config file: {', '.join(extra_files)}")

    @classmethod
    def parse_data_table_config_entry_columns(
            cls, columns: Sequence[Mapping[str,
                                           Any]]) -> Sequence[DataTableColumn]:
        """Parse columns from the local config file."""
        if not columns:
            return []
        return [
            DataTableColumn(
                column_index=c.get("column_index"),
                original_column=c["original_column"],
                column_type=c.get("column_type"),
                mapped_column_path=c.get("mapped_column_path"),
                key_column=c.get("key_column"),
            ) for c in columns
        ]

    @classmethod
    def parse_data_table_columns(
            cls, columns: Sequence[Mapping[str,
                                           Any]]) -> list[DataTableColumn]:
        """Parse columns from the Google SecOps API response."""
        parsed_columns = []
        for i, column in enumerate(columns):
            try:
                parsed_columns.append(
                    DataTableColumn(
                        column_index=column.get("columnIndex", i),
                        original_column=column["originalColumn"],
                        column_type=column.get("columnType"),
                        mapped_column_path=column.get("mappedColumnPath"),
                        key_column=column.get("keyColumn"),
                    ))
            except pydantic.ValidationError as e:
                LOGGER.error(
                    "ValidationError for data table column %s\n%s",
                    column,
                    json.dumps(e.errors(), indent=4),
                )
                raise
        return parsed_columns

    @classmethod
    def check_data_table_config(cls, config: Mapping[str, Any]):
        """Check data table config file for invalid keys."""
        allowed_keys = {
            "description",
            "columns",
            "row_time_to_live",
            "scopes",
        }
        for name, data_table_config in config.items():
            if "columns" not in data_table_config:
                raise InvalidDataTableConfigError(
                    f"Required key 'columns' not found for data table '{name}'"
                )
            invalid_keys = set(data_table_config.keys()) - allowed_keys
            if invalid_keys:
                raise InvalidDataTableConfigError(
                    f"Invalid keys {invalid_keys} for data table '{name}'")

    @classmethod
    def get_remote_data_tables(
            cls, chronicle_client: ChronicleClient) -> "DataTables":
        """Retrieve all data tables from Google SecOps."""
        LOGGER.info("Retrieving all data tables from Google SecOps...")
        retrieved_data_tables = chronicle_client.list_data_tables() or []
        LOGGER.info("Retrieved %d data tables.", len(retrieved_data_tables))
        parsed = cls.parse_data_tables(data_tables=retrieved_data_tables)
        return DataTables(data_tables=parsed)

    @classmethod
    def get_remote_data_table_rows(
        cls,
        chronicle_client: ChronicleClient,
        data_table_name: str,
        write_to_file: bool = False,
    ) -> Sequence[list[str]]:
        """Retrieve rows for a data table and optionally write them to a file."""
        log_message = f"Retrieving all rows for data table '{data_table_name}'"
        if write_to_file:
            file_path = DATA_TABLES_DIR / f"{data_table_name}.csv"
            log_message += f" and writing to {file_path}"
        LOGGER.info(log_message)

        rows = chronicle_client.list_data_table_rows(
            name=data_table_name) or []
        row_values = [row["values"] for row in rows]

        LOGGER.info("Retrieved %d rows for data table '%s'.", len(row_values),
                    data_table_name)

        if write_to_file:
            with open(file_path, "w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerows(row_values)
            LOGGER.info("Wrote %d rows to %s.", len(row_values), file_path)

        return row_values

    @classmethod
    def are_data_tables_different(
        cls,
        data_table_1_rows: Sequence[Sequence[str]],
        data_table_2_rows: Sequence[Sequence[str]],
    ) -> bool:
        """Compare the content of two data tables."""
        set1 = {tuple(row) for row in data_table_1_rows}
        set2 = {tuple(row) for row in data_table_2_rows}
        return set1 != set2

    @classmethod
    def update_remote_data_tables(
        cls,
        chronicle_client: ChronicleClient,
        data_tables_dir: pathlib.Path = DATA_TABLES_DIR,
        data_table_config_file: pathlib.Path = DATA_TABLE_CONFIG_FILE,
    ) -> Mapping[str, list[str]]:
        """Update data tables in Google SecOps based on local files."""
        LOGGER.info(
            "Updating data tables in Google SecOps from local files...")
        local_tables = cls.load_data_table_config(data_table_config_file,
                                                  data_tables_dir)
        if not local_tables:
            return {}

        remote_tables = {
            t.name: t
            for t in cls.get_remote_data_tables(chronicle_client).data_tables
        }
        summary = {
            "created": [],
            "recreated": [],
            "config_updated": [],
            "content_updated": []
        }

        for name, local in local_tables.items():
            remote = remote_tables.get(name)
            if not remote:
                cls._create_new_data_table(chronicle_client, name, local,
                                           summary)
            else:
                cls._update_existing_data_table(chronicle_client, name, local,
                                                remote, summary)
        return summary

    @classmethod
    def _create_new_data_table(cls, chronicle_client: ChronicleClient,
                               name: str, local: DataTable, summary: dict):
        """Create a new data table."""
        LOGGER.info(f"Creating new data table '{name}'.")
        rows = cls._read_data_table_csv(name)
        header = {
            col.original_column: DataTableColumnType(col.column_type)
            for col in local.columns
        }
        scopes = [
            f"projects/{PROJECT_ID}/locations/{REGION}/instances/{CUSTOMER_ID}/dataAccessScopes/{s}"
            for s in local.scopes or []
        ]
        chronicle_client.create_data_table(
            name=name,
            description=local.description,
            header=header,
            rows=rows,
            scopes=scopes,
        )
        summary["created"].append(name)

    @classmethod
    def _update_existing_data_table(
        cls,
        chronicle_client: ChronicleClient,
        name: str,
        local: DataTable,
        remote: DataTable,
        summary: dict,
    ):
        """Update an existing data table."""
        if cls._has_schema_changed(local, remote):
            cls._recreate_data_table(chronicle_client, name, local, remote,
                                     summary)
        else:
            cls._check_and_update_config(name, local, remote, summary)
            cls._check_and_update_content(chronicle_client, name, remote,
                                          summary)

    @classmethod
    def _has_schema_changed(cls, local: DataTable, remote: DataTable) -> bool:
        """Check if the data table schema has changed."""
        local_cols = {(c.original_column, c.column_type)
                      for c in local.columns}
        remote_cols = {(c.original_column, c.column_type)
                       for c in remote.columns}
        return local_cols != remote_cols

    @classmethod
    def _recreate_data_table(
        cls,
        chronicle_client: ChronicleClient,
        name: str,
        local: DataTable,
        remote: DataTable,
        summary: dict,
    ):
        """Recreate a data table by deleting and then creating it."""
        LOGGER.info(f"Recreating data table '{name}' due to schema change.")
        chronicle_client.delete_data_table(name=remote.name, force=True)
        cls._create_new_data_table(chronicle_client, name, local, summary)
        summary["recreated"].append(name)

    @classmethod
    def _check_and_update_config(cls, name: str, local: DataTable,
                                 remote: DataTable, summary: dict):
        """Check for configuration changes and update if necessary."""
        if (local.description != remote.description
                or local.row_time_to_live != remote.row_time_to_live):
            LOGGER.info(f"Updating configuration for data table '{name}'.")
            # Placeholder for actual update logic
            summary["config_updated"].append(name)

    @classmethod
    def _check_and_update_content(cls, chronicle_client: ChronicleClient,
                                  name: str, remote: DataTable, summary: dict):
        """Check for content changes and update if necessary."""
        remote_rows = cls.get_remote_data_table_rows(chronicle_client, name)
        local_rows = cls._read_data_table_csv(name)

        if cls.are_data_tables_different(remote_rows, local_rows):
            LOGGER.info(f"Updating content for data table '{name}'.")
            cls.update_remote_data_table_rows(chronicle_client, name,
                                              local_rows)
            summary["content_updated"].append(name)

    @classmethod
    def _read_data_table_csv(cls, data_table_name: str) -> list[list[str]]:
        """Read a data table's CSV file."""
        file_path = DATA_TABLES_DIR / f"{data_table_name}.csv"
        with open(file_path, "r", encoding="utf-8") as f:
            return list(csv.reader(f))

    @classmethod
    def update_remote_data_table_rows(
        cls,
        chronicle_client: ChronicleClient,
        data_table_name: str,
        row_values: Sequence[Sequence[str]],
    ):
        """Update the content (rows) for a data table in Google SecOps."""
        if not row_values:
            raise ValueError(
                f"No rows found in local data table '{data_table_name}'")

        LOGGER.info(
            "Uploading %d rows to data table '%s'.",
            len(row_values),
            data_table_name,
        )
        # TODO: Implement bulk update and creation of data table rows
        # The following is a placeholder for the actual implementation.
        # As of now, the secops library does not support bulk row replacement.
        # This will be implemented once the library is updated.
        LOGGER.warning(
            "Bulk row update is not yet implemented in the secops library."
            " Skipping content update for '%s'.",
            data_table_name,
        )

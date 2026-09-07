# Copyright 2026 Google LLC
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

from __future__ import annotations
from typing import Iterator
from TIPCommon.types import SingleJson
import google.auth.credentials
import google.cloud.bigquery
import google.cloud.exceptions
import exceptions
import authentication as auth
import json


LIST_RESULT_LIMIT = 50


class GoogleBigQueryApiManager:
    def __init__(
        self, project_id: str, api_client: google.cloud.bigquery.Client
    ) -> None:
        self.project_id: str = project_id
        self.api_client: google.cloud.bigquery.Client = api_client

    @classmethod
    def from_config_params(
        cls, wif_email: str, project_id: str
    ) -> GoogleBigQueryApiManager:
        """Second constructor using the integration's configuration parameters"""
        credentials = auth.get_credentials_using_workload_identity_email(
            wif_email, project_id, True
        )
        api_client = auth.create_session(
            "https://bigquery.googleapis.com", credentials, project_id, True
        )
        return cls(project_id, api_client)

    def test_connectivity(self) -> None:
        """Test connectivity to Google Big Query"""
        try:
            _ = list(self.list_datasets(max_results=1))
        except google.cloud.exceptions.GoogleCloudError as e:
            raise exceptions.GoogleBigQueryManagerError(
                "Unable to connect to Google BigQuery. "
                f"Please validate your credentials. {e}"
            ) from e

    def list_datasets(
        self, max_results: int = LIST_RESULT_LIMIT
    ) -> Iterator[google.cloud.bigquery.dataset.DatasetListItem]:
        return self.api_client.list_datasets(max_results=max_results)

    def run_query(
        self, query: str, limit: int | None, dataset_name: str | None = None
    ) -> list[SingleJson]:
        """Run a query and get the results

        Args:
            dataset_name: Specify the name of the dataset, which will be used,
                when executing queries.
            query: Specify the SQL query that needs to be executed.
            limit: Max amount of results to fetch. Optional.

        Returns:
            The results of the query
        """
        job_config_params = {
            "default_dataset": (
                f"{self.project_id}.{dataset_name}" if dataset_name else None
            )
        }
        job_config = google.cloud.bigquery.QueryJobConfig(
            **{k: v for k, v in job_config_params.items() if v is not None}
        )
        query_job = self.api_client.query(query, job_config=job_config)
        rows = query_job.result(max_results=limit)
        results = rows.to_dataframe()
        return results.to_dict("records")

    def load_to_bigquery(
        self, all_agents, project_id, dataset_id, table_id, is_first_batch
    ):
        """
        Loads a list of dictionaries into BigQuery.
        First batch truncates the table, subsequent batches append.
        """
        if not all_agents:
            return

        table_ref = f"{project_id}.{dataset_id}.{table_id}"

        # Convert complex nested structures into JSON strings to prevent BQ schema errors
        flattened_agents = []
        for agent in all_agents:
            flat_agent = {}
            for key, value in agent.items():
                if isinstance(value, (dict, list)):
                    flat_agent[key] = json.dumps(value)
                else:
                    flat_agent[key] = value
            flattened_agents.append(flat_agent)

        # First batch across all projects truncates the table, the rest append
        write_disposition = (
            google.cloud.bigquery.WriteDisposition.WRITE_TRUNCATE
            if is_first_batch
            else google.cloud.bigquery.WriteDisposition.WRITE_APPEND
        )

        # Configure the load job
        job_config = google.cloud.bigquery.LoadJobConfig(
            autodetect=True,  # Automatically infer the schema
            write_disposition=write_disposition,
        )

        try:
            job = self.api_client.load_table_from_json(
                flattened_agents, table_ref, job_config=job_config
            )
            job.result()
        except Exception as e:
            raise exceptions.GoogleBigQueryManagerError(e)

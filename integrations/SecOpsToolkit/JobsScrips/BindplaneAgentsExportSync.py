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

from SiemplifyJob import SiemplifyJob
from SiemplifyUtils import output_handler
from TIPCommon.extraction import extract_action_param
from GoogleBigQueryManager import GoogleBigQueryApiManager
from SecOpsToolkitManager import SecOpsToolkitManager

import requests
import json


class JobParametersParser:
    """This class parses the input parameters of the job."""

    def __init__(self, siemplify_):
        self.bindplane_api_url = JobParametersParser.parse_bindplane_api_url(siemplify_)
        self.bindplane_projects = JobParametersParser.parse_bindplane_projects(
            siemplify_
        )
        self.projects_metadata = JobParametersParser.parse_projects_metadata(siemplify_)
        self.bq_project_id = JobParametersParser.parse_bq_project_id(siemplify_)
        self.bq_dataset = JobParametersParser.parse_bq_dataset(siemplify_)
        self.bq_table = JobParametersParser.parse_bq_table(siemplify_)
        self.wif_email = JobParametersParser.parse_wif_email(siemplify_)

        self.chronicle_customer_id = JobParametersParser.parse_chronicle_customer_id(
            siemplify_
        )
        self.chronicle_project_id = JobParametersParser.parse_chronicle_project_id(
            siemplify_
        )
        self.chronicle_region = JobParametersParser.parse_chronicle_region(siemplify_)

    @staticmethod
    def parse_bindplane_api_url(siemplify):
        return extract_action_param(
            siemplify=siemplify,
            param_name="Bindplane API URL",
            is_mandatory=True,
            print_value=True,
        )

    @staticmethod
    def parse_bindplane_projects(siemplify):
        param = extract_action_param(
            siemplify=siemplify,
            param_name="Bindplane Projects",
            is_mandatory=True,
            print_value=False,
        )
        try:
            return json.loads(param) if param else {}
        except json.JSONDecodeError:
            siemplify.LOGGER.error(
                "Failed to parse Bindplane Projects. Ensure it is a valid JSON dictionary."
            )
            return {}

    @staticmethod
    def parse_projects_metadata(siemplify):
        param = extract_action_param(
            siemplify=siemplify,
            param_name="Projects Metadata",
            is_mandatory=False,
            print_value=False,
        )
        try:
            return json.loads(param) if param else {}
        except json.JSONDecodeError:
            siemplify.LOGGER.error(
                "Failed to parse Project Metadata. Ensure it is a valid JSON dictionary."
            )
            return {}

    @staticmethod
    def parse_bq_project_id(siemplify):
        return extract_action_param(
            siemplify=siemplify,
            param_name="BQ Project ID",
            is_mandatory=True,
            print_value=True,
        )

    @staticmethod
    def parse_bq_dataset(siemplify):
        return extract_action_param(
            siemplify=siemplify,
            param_name="BQ Dataset",
            is_mandatory=True,
            print_value=True,
        )

    @staticmethod
    def parse_bq_table(siemplify):
        return extract_action_param(
            siemplify=siemplify,
            param_name="BQ Table",
            is_mandatory=True,
            print_value=True,
        )

    @staticmethod
    def parse_wif_email(siemplify):
        return extract_action_param(
            siemplify=siemplify,
            param_name="WIF Email",
            is_mandatory=True,
            print_value=False,
        )

    @staticmethod
    def parse_chronicle_customer_id(siemplify):
        return extract_action_param(
            siemplify=siemplify,
            param_name="SecOps Customer ID",
            is_mandatory=False,
            print_value=True,
        )

    @staticmethod
    def parse_chronicle_project_id(siemplify):
        return extract_action_param(
            siemplify=siemplify,
            param_name="SecOps Project ID",
            is_mandatory=False,
            print_value=True,
        )

    @staticmethod
    def parse_chronicle_region(siemplify):
        return extract_action_param(
            siemplify=siemplify,
            param_name="SecOps Region",
            is_mandatory=False,
            print_value=True,
        )


def fetch_agents_for_project(api_url, api_key, logger, limit=1000):
    """
    Fetches the list of agents from Bindplane API in batches using pagination.
    Yields lists of agents up to 'limit' size.
    """
    headers = {"x-bindplane-api-key": api_key, "Accept": "application/json"}

    endpoint = f"{api_url.rstrip('/')}/agents"
    offset = 0

    while True:
        params = {"limit": limit, "offset": offset}
        try:
            logger.info(
                f"Making request to {endpoint} with offset {offset} and limit {limit}"
            )
            response = requests.get(
                endpoint, headers=headers, params=params, timeout=30
            )
            response.raise_for_status()
            data = response.json()

            # Standardize the output since different API versions might wrap the data differently
            if isinstance(data, dict):
                if "agents" in data:
                    items = data["agents"]
                elif "data" in data:
                    items = data["data"]
                elif "items" in data:
                    items = data["items"]
                else:
                    items = [data]
            elif isinstance(data, list):
                items = data
            else:
                items = []

            if not items:
                break

            yield items

            if len(items) < limit:
                break  # We reached the end of the results

            offset += limit

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch agents from {endpoint}: {e}")
            break


@output_handler
def main():
    siemplify = SiemplifyJob()
    siemplify.script_name = "BindplaneAgentsExportSync"
    siemplify.LOGGER.info("--------------- JOB STARTED ---------------")

    try:
        job_parameters_parser = JobParametersParser(siemplify)

        if not job_parameters_parser.bindplane_projects:
            siemplify.LOGGER.error(
                "Bindplane Projects parameter is empty or invalid. Aborting."
            )
            return

        manager = GoogleBigQueryApiManager.from_config_params(
            job_parameters_parser.wif_email, job_parameters_parser.bq_project_id
        )

        is_first_batch = True
        total_loaded = 0
        all_agents_collected = []

        for proj_name, api_key in job_parameters_parser.bindplane_projects.items():
            siemplify.LOGGER.info(f"--- Processing Bindplane Project: {proj_name} ---")

            for agents_batch in fetch_agents_for_project(
                api_url=job_parameters_parser.bindplane_api_url,
                api_key=api_key,
                logger=siemplify.LOGGER,
                limit=1000,
            ):
                if not agents_batch:
                    continue

                # Process each agent in the current batch
                for agent in agents_batch:
                    agent["bindplane_project_source"] = proj_name

                    # Add region and country metadata
                    metadata = job_parameters_parser.projects_metadata.get(
                        proj_name, {}
                    )
                    agent["region"] = metadata.get("region", "Unknown")
                    agent["country"] = metadata.get("country", "Unknown")
                    agent["status_ui"] = (
                        "Disconnected" if agent["status"] == 0 else "Connected"
                    )

                    # Extract assigned configuration from configurationStatus if available
                    config_status = agent.get("configurationStatus")
                    if isinstance(config_status, dict):
                        # Check for 'current' configuration name, or fallback
                        current_config = config_status.get("assigned")
                        if current_config:
                            agent["assigned_configuration"] = current_config
                        else:
                            agent["assigned_configuration"] = ""
                    elif config_status:
                        agent["assigned_configuration"] = str(config_status)

                # Load current batch to BigQuery
                manager.load_to_bigquery(
                    all_agents=agents_batch,
                    project_id=job_parameters_parser.bq_project_id,
                    dataset_id=job_parameters_parser.bq_dataset,
                    table_id=job_parameters_parser.bq_table,
                    is_first_batch=is_first_batch,
                )

                is_first_batch = False
                total_loaded += len(agents_batch)
                all_agents_collected.extend(agents_batch)

        siemplify.LOGGER.info(
            f"Total agents collected and loaded across all projects: {total_loaded}"
        )

        # SecOps Chronicle Data Table Sync
        if job_parameters_parser.chronicle_customer_id:
            siemplify.LOGGER.info(
                "Initializing SecOps Chronicle Client to push agents data to Data Table..."
            )
            try:
                api_root = f"https://chronicle.{job_parameters_parser.chronicle_region}.rep.googleapis.com/v1alpha/projects/{job_parameters_parser.chronicle_project_id}/locations/{job_parameters_parser.chronicle_region}/instances/{job_parameters_parser.chronicle_customer_id}"

                chronicle = SecOpsToolkitManager.create_manager_instance(
                    user_service_account=None,
                    workload_identity_email=job_parameters_parser.wif_email,
                    chronicle_soar=siemplify,
                    api_root=api_root,
                    verify_ssl=True,
                )

                table_name = "bindplane_agents"
                header = {
                    "agent_id": {"type": "STRING", "keyColumn": True},
                    "name": "STRING",
                    "status": "STRING",
                    "status_ui": "STRING",
                    "version": "STRING",
                    "bindplane_project_source": "STRING",
                    "region": "STRING",
                    "country": "STRING",
                    "assigned_configuration": "STRING",
                    "platform": "STRING",
                }

                siemplify.LOGGER.info(f"Ensuring Data Table '{table_name}' exists...")
                try:
                    chronicle.create_data_table(
                        name=table_name,
                        description="Bindplane Agents Inventory",
                        header=header,
                    )
                except Exception as e:
                    siemplify.LOGGER.info(
                        f"Data Table might already exist or creation returned an error: {e}"
                    )

                # prepare rows
                dt_rows = []
                for agent in all_agents_collected:
                    dt_rows.append(
                        [
                            str(agent.get("id", "")),
                            str(agent.get("name", "")),
                            str(agent.get("status", "")),
                            str(agent.get("status_ui", "")),
                            str(agent.get("version", "")),
                            str(agent.get("bindplane_project_source", "")),
                            str(agent.get("region", "")),
                            str(agent.get("country", "")),
                            str(agent.get("assigned_configuration", "")),
                            str(agent.get("platform", "")),
                        ]
                    )

                batch_size = 1000
                siemplify.LOGGER.info(
                    f"Replacing Data Table rows for '{table_name}' with {len(dt_rows)} rows in batches of {batch_size}..."
                )

                for i in range(0, len(dt_rows), batch_size):
                    batch = dt_rows[i : i + batch_size]
                    siemplify.LOGGER.info(
                        f"Processing batch {i // batch_size + 1} ({len(batch)} rows)..."
                    )
                    chronicle.replace_data_table_rows(name=table_name, rows=batch)
                siemplify.LOGGER.info(
                    "Successfully pushed agents to Chronicle Data Table."
                )
            except Exception as e:
                siemplify.LOGGER.error(f"Failed to populate Chronicle Data Table: {e}")

        siemplify.LOGGER.info("--------------- JOB FINISHED ---------------")

    except Exception as error:
        siemplify.LOGGER.error(f"Got exception on main handler. Error: {error}")
        siemplify.LOGGER.exception(error)
        raise


if __name__ == "__main__":
    main()

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

import logging
from typing import List, Dict, Any
import requests
import google.auth
import google.auth.transport.requests

from models import SocRole, WorkflowMenuCard, APIError, Workflow, WorkflowCategory
from config import SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION

LOGGER = logging.getLogger(__name__)


class SecOpsClient:
    """A client for interacting with the Chronicle SecOps API from scratch, using google default auth."""

    def __init__(self, customer_id: str, project_id: str, region: str):
        if not all([customer_id, project_id, region]):
            raise APIError(
                "Missing SecOps client configuration: customer_id, project_id, region."
            )
        self.customer_id = customer_id
        self.project_id = project_id
        self.region = region
        self.base_url = f"https://{region}-chronicle.googleapis.com"

        try:
            google_credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"])
            self._session = google.auth.transport.requests.AuthorizedSession(
                google_credentials)
            LOGGER.info("Google AuthorizedSession initialized successfully.")
        except Exception as e:
            raise APIError(
                f"Failed to initialize Google AuthorizedSession: {e}") from e

    def _make_request(self,
                      method: str,
                      path: str,
                      params: Dict[str, Any] = None,
                      json_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Makes an authenticated request to the Chronicle API."""
        url = f"{self.base_url}{path}"
        try:
            response = self._session.request(method,
                                             url,
                                             params=params,
                                             json=json_data)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            error_message = f"{e}: {response.content.decode('utf-8')}" if response.content else str(
                e)
            raise APIError(f"API request failed: {error_message}") from e
        except Exception as e:
            raise APIError(
                f"An unexpected error occurred during API request: {e}") from e

    def list_soc_roles(self) -> List[SocRole]:
        """Retrieves a list of all available SOC roles from the Chronicle API."""
        soc_roles: List[SocRole] = []
        next_page_token = None
        try:
            while True:
                parent = f"projects/{self.project_id}/locations/{self.region}/instances/{self.customer_id}"
                api_path = f"/v1alpha/{parent}/socRoles"

                params = {}
                if next_page_token:
                    params["pageToken"] = next_page_token

                response_json = self._make_request(method="GET",
                                                   path=api_path,
                                                   params=params)

                if "socRoles" in response_json:
                    for role_data in response_json["socRoles"]:
                        soc_roles.append(
                            SocRole(
                                name=role_data.get("name", ""),
                                displayName=role_data.get("displayName", ""),
                                description=role_data.get("description", ""),
                            ))
                next_page_token = response_json.get("nextPageToken")
                if not next_page_token:
                    break
        except Exception as e:
            raise APIError(f"Failed to retrieve SOC roles: {e}") from e
        return soc_roles

    def get_playbooks(self) -> List[WorkflowMenuCard]:
        """Retrieves a list of all legacy workflow menu cards (playbooks) from the Chronicle API."""
        workflow_menu_cards: List[WorkflowMenuCard] = []
        try:
            parent = f"projects/{self.project_id}/locations/{self.region}/instances/{self.customer_id}"
            api_path = f"/v1alpha/{parent}/legacyPlaybooks:legacyGetWorkflowMenuCardsWithEnvFilter"

            # Assuming payload based on previous SiemplifyApiClient context (json=[0, 1])
            # The actual API documentation for this method is not clear on the body,
            # but a POST usually expects one.
            # If this is incorrect, it will need to be adjusted.
            payload = {"legacyPayload": ["REGULAR", "NESTED"]}

            response_json = self._make_request(method="POST",
                                               path=api_path,
                                               json_data=payload)
            print(response_json)

            if "payload" in response_json:
                for card_data in response_json["payload"]:
                    workflow_menu_cards.append(
                        WorkflowMenuCard(
                            id=card_data.get("id", ""),
                            identifier=card_data.get("identifier", ""),
                            name=card_data.get("name", ""),
                            displayName=card_data.get("displayName", ""),
                            categoryName=card_data.get("categoryName", ""),
                            modification_time=card_data.get(
                                "modificationTime", "")))
        except Exception as e:
            raise APIError(
                f"Failed to retrieve legacy workflow menu cards: {e}") from e
        return workflow_menu_cards

    def get_playbook(self, identifier: str) -> Dict[str, Any]:
        """Retrieves full information for a legacy workflow by its identifier."""
        try:
            parent = f"projects/{self.project_id}/locations/{self.region}/instances/{self.customer_id}"
            api_path = f"/v1alpha/{parent}/legacyPlaybooks:legacyGetWorkflowFullInfoWithEnvFilterByIdentifier"

            response_json = self._make_request(
                method="GET",
                path=api_path,
                params={"workflowIdentifier": identifier})
            return response_json
        except Exception as e:
            raise APIError(
                f"Failed to retrieve legacy workflow full info for {identifier}: {e}"
            ) from e

    def save_playbook(self, playbook: Workflow) -> None:
        """Creates or updates a workflow in the Siemplify API."""
        LOGGER.info(f"Saving workflow '{playbook.name}'")
        parent = f"projects/{self.project_id}/locations/{self.region}/instances/{self.customer_id}"
        api_path = f"/v1alpha/{parent}/legacyPlaybooks:legacySaveWorkflowDefinitions"

        response_json = self._make_request(method="POST",
                                           path=api_path,
                                           json_data=playbook.raw_data)
        return response_json
        LOGGER.info(
            f"New workflow '{playbook.name}' was installed successfully")

    def get_environment_names(self) -> List[str]:
        """Retrieves a list of environment names from the Chronicle API."""
        environment_names: List[str] = []
        try:
            parent = f"projects/{self.project_id}/locations/{self.region}/instances/{self.customer_id}"
            api_path = f"/v1alpha/{parent}/environments"

            response_json = self._make_request(method="GET", path=api_path)

            if "environments" in response_json:
                for environment_data in response_json["environments"]:
                    environment_names.append(
                        environment_data.get("displayName", ""))
        except Exception as e:
            raise APIError(f"Failed to retrieve environment names: {e}") from e
        return environment_names

    def get_environment_group_names(self) -> List[str]:
        """Retrieves a list of environment group names from the Chronicle API."""
        environment_group_names: List[str] = []
        try:
            parent = f"projects/{self.project_id}/locations/{self.region}/instances/{self.customer_id}"
            api_path = f"/v1alpha/{parent}/environmentGroups"

            response_json = self._make_request(method="GET", path=api_path)

            if "environmentGroups" in response_json:
                for environment_group_data in response_json[
                        "environmentGroups"]:
                    environment_group_names.append(
                        environment_group_data.get("displayName", ""))
        except Exception as e:
            raise APIError(
                f"Failed to retrieve environment group names: {e}") from e
        return environment_group_names

    def get_playbook_categories(self) -> List[WorkflowCategory]:
        """Retrieves a list of all workflow categories from the Chronicle API."""
        workflow_categories: List[WorkflowCategory] = []
        try:
            parent = f"projects/{self.project_id}/locations/{self.region}/instances/{self.customer_id}"
            api_path = f"/v1alpha/{parent}/legacyPlaybooks:legacyGetWorkflowCategories"

            response_json = self._make_request(method="GET", path=api_path)

            if "payload" in response_json:
                for category_data in response_json["payload"]:
                    workflow_categories.append(
                        WorkflowCategory(
                            id=category_data.get("id", ""),
                            name=category_data.get("name", ""),
                            categoryState=category_data.get(
                                "categoryState", ""),
                            type=category_data.get("type", ""),
                        ))
        except Exception as e:
            raise APIError(
                f"Failed to retrieve workflow categories: {e}") from e
        return workflow_categories

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

from dataclasses import dataclass
from enum import Enum
from jinja2 import Template, Environment as JinjaEnvironment
from constants import PLAYBOOK_README_TEMPLATE, TRIGGER_TYPES, CONDITION_OPERATORS, CONDITION_MATCH_TYPES
import json
from typing import Iterator

class APIError(Exception):
    """Raised for issues communicating with the SecOps API."""
    pass


@dataclass
class SocRole:
    """Represents a SOC Role in Chronicle."""
    name: str
    displayName: str
    description: str

class Content:

    def __init__(self):
        self.readme: str | None = None

class File:
    """Represents a common file object used by the GitManager"""

    def __init__(self, path: str, contents: str | bytes):
        self.path = path
        if isinstance(contents, str):
            contents = contents.encode("utf-8")
        self.content = contents

    def __repr__(self):
        return f"{{Path: {self.path} Contents head: {self.content[:15]}...}}"

@dataclass
class WorkflowMenuCard:
    """Represents a Workflow Menu Card (legacy playbook) in Chronicle."""
    id: str
    identifier: str
    name: str
    displayName: str
    categoryName: str
    modification_time: int

class WorkflowTypes(Enum):
    PLAYBOOK = 0
    BLOCK = 1

class PlaybookTypes(Enum):
    REGULAR = "REGULAR"
    NESTED = "NESTED"

class WorkflowCategory(Content):
    """Represents a workflow category in Chronicle."""

    def __init__(self, id: str, name: str, categoryState: str, type: str):
        super().__init__()
        self.id = id
        self.name = name
        self.categoryState = categoryState
        self.type = type

class Workflow(Content):

    def __init__(self, raw_data: dict):
        super().__init__()
        self.raw_data = raw_data
        self.raw_data["id"] = 0
        self.raw_data["trigger"]["id"] = 0
        self.name = self.raw_data.get("name")
        self.description = self.raw_data.get("description")
        self.type = PlaybookTypes(self.raw_data.get("playbookType"))
        self.priority = self.raw_data.get("priority")
        self.isDebugMode = self.raw_data.get("isDebugMode", None)
        self.version = self.raw_data.get("version")
        self.trigger = self.raw_data.get("trigger", {})
        self.steps = self.raw_data.get("steps", [])
        self.isEnabled = self.raw_data.get("isEnabled")
        self.category = self.raw_data.get("categoryName", "Default")
        self.environments = self.raw_data.get("environments", [])
        self.modification_time = int(self.raw_data["modificationTimeUnixTimeInMs"])
        self.overview_templates = self.raw_data.get("overviewTemplates", [])
        self.permissions = self.raw_data.get("permissions", [])
        self.entity_access_level = self.raw_data.get("entityAccessLevel", [])
        self.default_access_level = self.raw_data.get("defaultAccessLevel", [])
        self.creation_source = self.raw_data.get("creationSource")
        self.has_restricted_environments = self.raw_data.get("hasRestrictedEnvironments")
        self.execution_scope = self.raw_data.get("executionScope")

    def __hash__(self):
        """Used to remove duplicates in workflow lists"""
        return hash(self.name)

    def __eq__(self, other):
        """Used to remove duplicates in workflow lists"""
        return self.name == getattr(other, "name", None)

    def generate_readme(self, additional_info: str = None):
        env = JinjaEnvironment()
        env.globals["WorkflowTypes"] = WorkflowTypes
        env.filters.update(
            {
                "trigger_type":
                lambda x: TRIGGER_TYPES.get(x),
                "condition_operator":
                lambda x: CONDITION_OPERATORS.get(x),
                "condition_match_type":
                lambda x: CONDITION_MATCH_TYPES.get(x),
                "split_action_name":
                lambda x: x.split("_", 1)[1] if "_" in x else x,
            }, )
        template = PLAYBOOK_README_TEMPLATE
        if additional_info:
            template += additional_info
        readme = env.from_string(template)
        self.readme = readme.render(
            playbook=self.__dict__,
            involved_blocks=self.get_involved_blocks(),
        )

    def iter_files(self) -> Iterator[File]:
        yield File(self.name + ".json", json.dumps(self.raw_data, indent=4))
        yield File("README.md", self.readme)

    def get_involved_blocks(self):
        return [x for x in self.steps if x.get("type") == 5]

    # def update_instance_name_in_steps(
    #     self,
    #     client: SiemplifyApiClient,
    #     chronicle_soar: ChronicleSOAR,
    # ) -> None:
    #     """Updates name of instances in the steps."""
    #     for step in self.steps:
    #         if (step.get("type") == STEP_TYPE
    #                 and step.get("actionProvider") == "Scripts"):
    #             self._update_instance_display_names_for_step(
    #                 step, api, chronicle_soar)

    def _is_integration_instance_param(
        self,
        param_name: str | None,
        param_value: str | None,
    ) -> bool:
        """Checks if a parameter is a valid integration instance parameter."""
        return param_name in (
            "IntegrationInstance",
            "FallbackIntegrationInstance",
        ) and self._is_valid_instance_id(param_value)

    def _update_instance_display_names_for_step(
        self,
        step: dict,
        api: SiemplifyApiClient,
        chronicle_soar: ChronicleSOAR,
    ) -> None:
        """Updates display names for integration instance parameters in a step.

        Args:
            step (dict): The workflow step dictionary to process.
            api (SiemplifyApiClient): An API client instance used to fetch
                integration instance names.
        """
        integration_name = step["integration"]

        for param in step.get("parameters", []):
            param_name = param.get("name")
            param_value = param.get("value")
            try:
                if not self._is_integration_instance_param(
                        param_name, param_value):
                    continue

                display_name = api.get_integration_instance_name(
                    chronicle_soar,
                    integration_name,
                    param_value,
                    self.environments,
                )

                match param_name:
                    case "IntegrationInstance":
                        param["InstanceDisplayName"] = display_name
                    case "FallbackIntegrationInstance":
                        param["FallbackInstanceDisplayName"] = display_name
            except HTTPError as e:
                # ignoring 404 errors as they expected in migrations between instances.
                if e.response is not None and hasattr(e.response,
                                                      'status_code'):
                    status_code = e.response.status_code
                    if status_code != 404:
                        raise e
                else:
                    # TIPCommon is re-raising HTTPError without response object
                    # Try to extract status code from the error message itself
                    error_msg = str(e)
                    status_code_match = re.search(r'(\d{3})\s+Client Error',
                                                  error_msg)
                    if status_code_match:
                        status_code = int(status_code_match.group(1))
                        if status_code != 404:
                            raise e
                    else:
                        # can't determine the status code
                        raise e

    def _is_valid_instance_id(self, instance_id: str) -> bool:
        try:
            val = uuid.UUID(instance_id, version=4)

        except (TypeError, ValueError):
            return False

        return str(val) == instance_id and val.version == 4


class Job(Content):

    def __init__(self, raw_data: dict):
        super().__init__()
        raw_data["id"] = 0
        self.raw_data = raw_data
        self.name = self.raw_data.get("name")
        self.integration = self.raw_data.get("integration")
        self.description = self.raw_data.get("description")
        self.parameters = self.raw_data.get("parameters")
        self.runIntervalInSeconds = self.raw_data.get("runIntervalInSeconds")

    def generate_readme(self, additional_info: str = None) -> None:
        env = JinjaEnvironment()
        env.filters.update(
            {"base_param_type": lambda x: BASE_PARAMETER_TYPES.get(x)})
        template = JOB_README
        if additional_info:
            template += additional_info
        readme = env.from_string(template)
        self.readme = readme.render(job=self.__dict__)

    def iter_files(self) -> Iterator[File]:
        yield File(f"Jobs/{self.name}.json", json.dumps(self.raw_data,
                                                        indent=4))

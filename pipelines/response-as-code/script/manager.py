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

import os
import re
import tempfile
import uuid
import logging
from typing import TYPE_CHECKING, Any
from jinja2 import Template, Environment
from constants import (
    ALL_ENVIRONMENTS_IDENTIFIER,
    DEFAULT_AUTHOR,
    ROOT_README,
)
from models import Workflow, File
from config import SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION, PLAYBOOKS_PATH
from models import APIError
from secops_client import SecOpsClient
from models import SocRole
from models import WorkflowMenuCard
from utils import update_objects, _push_obj
from cache import Cache

LOGGER = logging.getLogger("rac")


class ResponseManager:
    """Manages the lifecycle of SecOps playbooks."""

    def __init__(self):
        if not all([SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION]):
            raise APIError(
                "Missing SecOps env vars: SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION."
            )
        try:
            self.client = SecOpsClient(customer_id=SECOPS_CUSTOMER_ID,
                                       project_id=SECOPS_PROJECT_ID,
                                       region=SECOPS_REGION)
            LOGGER.info("Custom SecOps client initialized successfully.")
        except Exception as e:
            raise APIError(
                f"Failed to initialize Custom SecOps client: {e}") from e

    def get_soc_roles(self) -> List[SocRole]:
        """Retrieves a list of all available SOC roles from the SecOps API."""
        return self.client.list_soc_roles()

    def get_playbooks(self) -> List[WorkflowMenuCard]:
        """Retrieves a list of all playbooks and blocks from the Chronicle API."""
        return self.client.get_playbooks()

    def get_playbook(self, identifier: str):
        """Retrieves full information for a legacy playbooks or block by its identifier."""
        return self.client.get_playbook(identifier)

    def store_playbook(self, playbook: Workflow) -> None:
        """Writes a workflow to the repo

        Args:
            playbook: A playbook object

        """
        _push_obj(
            playbook,
            playbook.name,
            "Playbook",
            f"{PLAYBOOKS_PATH}/{playbook.category}/{playbook.name}",
        )

    def install_playbooks(self, workflows: list[Workflow]) -> None:
        """Install or update playbooks and blocks

        Args:
            workflows: A list of workflow instances to install

        Raises:
            Exception: When a playbook environment doesn't exist

        """
        # Validate all playbook environments exist as environments or environment groups
        environments = (self.client.get_environment_names() +
                        self.client.get_environment_group_names() +
                        [ALL_ENVIRONMENTS_IDENTIFIER])
        for p in workflows:
            invalid_environments = [
                x for x in p.environments if x not in environments
            ]
            if invalid_environments:
                raise Exception(
                    f"Playbook '{p.name}' is assigned to environment(s) that don't exist: "
                    f"{', '.join(invalid_environments)}. "
                    f"Available environments: {', '.join(environments)}")

        # Remove duplicates and split by type
        workflows = list(set(workflows))
        cache: Cache[str, int] = Cache()
        playbook_installer = WorkflowInstaller(self.client, cache)
        blocks, playbooks = [], []
        for workflow in workflows:
            if workflow.type == WorkflowTypes.BLOCK:
                blocks.append(workflow)
            else:
                playbooks.append(workflow)

        # Save blocks first
        for block in blocks:
            playbook_installer.install_workflow(block)

        playbook_installer.refresh_cache_item("playbooks")

        for playbook in playbooks:
            playbook_installer.install_workflow(playbook)

    def generate_root_readme(self) -> str:
        """Generates the readme file contents for the root of the repository

        Contains all assets currently in the repository

        Returns: Readme file contents
        """

        def strip_new_lines(s: str):
            # Description might be None
            return s.replace("\n", "").strip() if s else s

        integrations = [{
            "name":
            integration.definition["DisplayName"],
            "description":
            strip_new_lines(integration.definition["Description"]),
        } for integration in self.content.get_integrations()]

        playbooks = [{
            "name": playbook.name,
            "description": strip_new_lines(playbook.description),
        } for playbook in self.content.get_playbooks()]

        connectors = [{
            "name":
            connector.name,
            "description":
            strip_new_lines(connector.description),
            "hasMappings": (True if self.content.get_mapping(
                connector.integration) else False),
        } for connector in self.content.get_connectors()]

        jobs = [{
            "name": job.name,
            "description": strip_new_lines(job.description)
        } for job in self.content.get_jobs()]

        visual_families = [{
            "name": vf.name,
            "description": strip_new_lines(vf.description)
        } for vf in self.content.get_visual_families()]

        readme = Template(ROOT_README)
        return readme.render(
            connectors=connectors,
            integrations=integrations,
            jobs=jobs,
            visualFamilies=visual_families,
            playbooks=playbooks,
        )

    def update_readme(self, readme: str, base_path: str = "") -> None:
        """Creates or updates a readme file in basePath

        Valid base_path format:
        - "Integrations"
        - "Playbooks/PlaybookName/"

        Args:
            readme: The readme contents
            base_path: Base path in the repo to write the readme file. Writes to root by default.

        """
        if base_path and not base_path.endswith(
                "/"):  # Ensure trailing slash for base_path if not empty
            base_path += "/"

        # Ensure content passed to LocalFolderManager is bytes
        readme_content_bytes = readme.encode('utf-8')
        update_objects([File("README.md", readme_content_bytes)],
                       base_path=base_path)
        LOGGER.info(f"Updated README.md at {base_path}README.md")

    def commit_and_push(self, message: str) -> None:
        """Commits all the changes and pushes the commit to the repo

        Args:
            message: The commit message

        """
        if self.content.metadata.get_setting_by_name("update_root_readme"):
            # Generate root readme
            root_readme = self.generate_root_readme()
            self.update_readme(root_readme)

        self.content.metadata.system_version = self.api.get_system_version()
        self.content.push_metadata()
        self.git_client.commit_and_push(message)


class WorkflowInstaller:
    """Helper class for installing workflows"""

    def __init__(
        self,
        client: SecOpsClient,
        mod_time_cache: Cache[str, int],
    ) -> None:
        self.client = client
        self._mod_time_cache: Cache[str, int] = mod_time_cache
        self._cache: dict[str, Any] = {}

    def install_workflow(self, workflow: Workflow) -> None:
        """Save a playbook or block in the current platform

        Args:
            workflow: A Playbook object to install

        """
        if self._workflow_exists(workflow.name):
            self._update_workflow_if_needed(workflow)

        else:
            self.install_new_workflow(workflow)

    def _workflow_exists(self, __workflow_name: str, /) -> bool:
        """Check if a workflow exists (is installed) in the platform."""
        return __workflow_name in self._installed_playbooks

    def _update_workflow_if_needed(self, workflow: Workflow) -> None:
        if not self._workflow_was_modified(workflow):
            LOGGER.info(
                f"Skipped update for unchanged workflow '{workflow.name}'")
            self._filter_and_save_context()
            return

        self._log_merge_conflicts(workflow)
        self.update_local_workflow(workflow)

    def _log_merge_conflicts(self, workflow: Workflow) -> None:
        if self._has_merge_conflicts(workflow):
            LOGGER.warn(
                "Both the git playbook and local installed playbook were modified."
                "  Git version will override local changes!", )

    def _has_merge_conflicts(self, workflow: Workflow) -> bool:
        cached_time: int = self._mod_time_cache.get(workflow.name, -1)
        local_time: int = self._get_local_workflow_mod_time(workflow.name, -1)
        return min(local_time, workflow.modification_time) > cached_time

    def _workflow_was_modified(self, workflow: Workflow) -> bool:
        cached_time: int = self._mod_time_cache.get(workflow.name, -1)
        return workflow.modification_time > cached_time

    def update_local_workflow(self, workflow: Workflow) -> None:
        """Update an existing workflow in the platform."""
        LOGGER.info(f"Updating existing workflow '{workflow.name}'")
        self._adjust_workflow_ids(workflow)
        self.client.save_playbook(workflow)
        self._save_workflow_mod_time_to_context(workflow)
        LOGGER.info(f"Workflow '{workflow.name}' was updated successfully")

    def _adjust_workflow_ids(self, workflow: Workflow) -> None:
        """Adjust workflow identifiers to match the existing workflow's
        (with the same name) identifiers.
        """
        playbook_id: str = self._installed_playbooks[workflow.name].identifier
        local_playbook: dict[str, Any] = self.client.get_playbook(playbook_id)
        self._copy_ids_from_existing_workflow(workflow, local_playbook)
        self._process_steps(workflow, local_playbook)

    def install_new_workflow(self, workflow: Workflow) -> None:
        """Install a new workflow to the platform."""
        LOGGER.info(f"Installing new workflow '{workflow.name}'")
        self._define_workflow_as_new(workflow)
        self._process_steps(workflow)
        self.client.save_playbook(workflow)
        self._save_workflow_mod_time_to_context(workflow)
        LOGGER.info(
            f"New Playbook '{workflow.name}' was installed successfully")

    def _process_steps(
        self,
        workflow: Workflow,
        installed_workflow: dict = None,
    ) -> None:
        """Iterate the playbook steps and assign the correct integration instances and block
        identifiers

        Args:
            workflow: Workflow to iterate steps
            installed_workflow: Optional current installed playbooks to copy identifiers

        """
        # A dict where the keys are the old step identifiers and values are the new step identifiers
        # Used for patching step relations
        identifier_mappings = {}
        # Flatten steps to include action containers
        old_steps = (self._flatten_playbook_steps(
            installed_workflow.get("steps")) if installed_workflow else None)
        for step in self._flatten_playbook_steps(
                workflow.raw_data.get("steps")):
            provider = step.get("actionProvider")
            step_type = step.get("type")

            step["workflowIdentifier"] = workflow.raw_data.get("identifier")
            # Take the step identifier if the same step instance name already exists.
            existing_step = (next(
                (x for x in old_steps
                 if (x.get("instanceName") == step.get("instanceName") and
                     x.get("actionProvider") == step.get("actionProvider"))),
                None,
            ) if old_steps else None)
            if existing_step:
                old_step_identifier = step.get("identifier")
                identifier_mappings[old_step_identifier] = existing_step.get(
                    "identifier", )
                step["identifier"] = existing_step.get("identifier")
                step["originalStepIdentifier"] = existing_step.get(
                    "originalStepIdentifier", )

                step_debug_data = step.get("debugData")
                if step_debug_data and step_debug_data.get(
                        "originalStepIdentifier"):
                    step_debug_data[
                        "originalStepIdentifier"] = existing_step.get(
                            "originalStepIdentifier", )
                if step_debug_data and step_debug_data.get(
                        "originalWorkflowIdentifier", ):
                    step_debug_data["originalWorkflowIdentifier"] = (
                        installed_workflow.get("originalPlaybookIdentifier"))

            if step_type == 0 and provider == "Scripts":  # Regular Action
                self._assign_integration_instance_to_step(
                    step,
                    workflow.environments,
                    existing_step,
                )
            elif step_type == 5:  # Nested Workflow
                self._link_nested_block_step(step)

        for relation in workflow.raw_data.get("stepsRelations"):
            if relation.get("fromStep") in identifier_mappings:
                relation["fromStep"] = identifier_mappings.get(
                    relation.get("fromStep"))
            if relation.get("toStep") in identifier_mappings:
                relation["toStep"] = identifier_mappings.get(
                    relation.get("toStep"))

        self._adjust_loop_keys_and_parameters(identifier_mappings, workflow)

    def _adjust_loop_keys_and_parameters(self, identifier_mappings, workflow):
        for step in self._flatten_playbook_steps(
                workflow.raw_data.get("steps")):
            if step.get("startLoopStepIdentifier"):
                mapped_id = identifier_mappings.get(
                    step["startLoopStepIdentifier"])
                if mapped_id:
                    step["startLoopStepIdentifier"] = mapped_id

            if step.get("endLoopStepIdentifier"):
                mapped_id = identifier_mappings.get(
                    step["endLoopStepIdentifier"])
                if mapped_id:
                    step["endLoopStepIdentifier"] = mapped_id

            parameters = step.get("parameters", [])
            for param in parameters:
                param_name = param.get("name")
                param_value = param.get("value")

                # Handle Start/EndLoopStepIdentifier parameter
                if (param_name in {
                        "StartLoopStepIdentifier", "EndLoopStepIdentifier"
                } and param_value):
                    mapped_id = identifier_mappings.get(param_value)
                    if mapped_id:
                        param["value"] = mapped_id

    def _save_workflow_mod_time_to_context(self, workflow: Workflow) -> None:
        self.refresh_cache_item("playbooks")
        new_mod_time: int = self._get_local_workflow_mod_time(
            workflow.name, -1)
        self._mod_time_cache[workflow.name] = new_mod_time
        self._filter_and_save_context()

    def _filter_and_save_context(self) -> None:
        self._mod_time_cache.filter_items(set(self._installed_playbooks))
        self._mod_time_cache.push_local_to_external()

    def _get_local_workflow_mod_time(
        self,
        __workflow_name: str,
        default: int | None = None,
        /,
    ) -> int:
        playbook: dict[str, Any] = self._installed_playbooks[__workflow_name]
        return playbook.modification_time or default

    @property
    def _installed_playbooks(self) -> dict[str, dict[str, Any]]:
        """Currently installed playbooks and blocks"""
        if "playbooks" not in self._cache:
            self._cache["playbooks"] = {
                x.name: x
                for x in self.client.get_playbooks()
            }
        return self._cache.get("playbooks")

    @property
    def _playbook_categories(self) -> dict:
        """Currently configured playbook categories"""
        if "categories" not in self._cache:
            self._cache["categories"] = {
                x.name: x
                for x in self.client.get_playbook_categories()
            }
        return self._cache.get("categories")

    def refresh_cache_item(self, item_name) -> None:
        if item_name in self._cache:
            del self._cache[item_name]

    def _assign_integration_instance_to_step(
        self,
        step: dict,
        environments: list,
        existing_step: dict = None,
    ) -> None:
        """Reconfigure an integration instance of a workflow step.

        If old_steps is supplied, It will first try to match the same step in the old playbook and
        assign the step to the same integration instance.
        Otherwise, If the playbook is assigned to only one environment (and not all environments),
        it will assign the first integration instance it finds.
        If the playbook is assigned to All Environments or more than one environment, The step will
        be set to dynamic mode and assigned to the first shared instance, or None if it doesn't
        exist.

        Args:
            step: The step to reconfigure
            environments: Playbook assigned environments, for searching integration instances
            existing_step: Optional - if the step is already defined, take the integration instance
            from it instead

        """
        if existing_step:
            instance = self._get_step_parameter_by_name(
                existing_step,
                "IntegrationInstance",
            ).get("value")
            self._set_step_parameter_by_name(step, "IntegrationInstance",
                                             instance)
            fallback = self._get_step_parameter_by_name(
                existing_step,
                "FallbackIntegrationInstance",
            ).get("value")
            self._set_step_parameter_by_name(
                step,
                "FallbackIntegrationInstance",
                fallback,
            )
            return

        instance_display_name = self._get_instance_display_name(
            step,
            "IntegrationInstance",
            "InstanceDisplayName",
        )

        # If the playbook is for one specific environment, choose the first integration instance
        # from that environment. Otherwise, set the step to dynamic mode and set the first shared
        # integration instance as fallback
        if len(environments
               ) == 1 and environments[0] != ALL_ENVIRONMENTS_IDENTIFIER:
            integration_instances = self._find_integration_instances_for_step(
                step.get("integration"),
                environments[0],
            )
            if integration_instances:
                self._set_step_parameter_by_name(
                    step,
                    "IntegrationInstance",
                    integration_instances[0].get("identifier"),
                )
                self._set_step_parameter_by_name(
                    step,
                    "FallbackIntegrationInstance",
                    None,
                )
        else:
            integration_instances = self._find_integration_instances_for_step(
                step.get("integration"),
                ALL_ENVIRONMENTS_IDENTIFIER,
            )
            self._set_step_parameter_by_name(
                step,
                "IntegrationInstance",
                "AutomaticEnvironment",
            )
            if integration_instances:
                self._set_step_parameter_by_name(
                    step,
                    "FallbackIntegrationInstance",
                    None or integration_instances[0].get("identifier"),
                )
            else:
                self._set_step_parameter_by_name(
                    step,
                    "FallbackIntegrationInstance",
                    None,
                )

    def _get_instance_display_name(
        self,
        step: dict,
        parameter_name: str,
        display_name_key: str,
    ) -> str | None:
        """Helper to get the display name of an integration instance parameter."""
        param_json = self._get_step_parameter_by_name(step, parameter_name)

        if param_json is not None:
            return param_json.get(display_name_key)

        return None

    def _find_integration_instances_for_step(
        self,
        integration_name: str,
        environment: str,
    ) -> list[dict]:
        """Find integration instances available for integration per environment

        Args:
            integration_name: The integration name to look for
            environment: The environment to fetch the integration instances

        Returns:
            A list of configured integration instances

        """
        cache_key = f"integration_instances_{environment}"
        if cache_key not in self._cache:
            self._cache[cache_key] = self.api.get_integrations_instances(
                environment)

        instances = self._cache.get(cache_key)
        instances.sort(key=lambda x: x.get("instanceName"))

        return [
            x for x in instances
            if x.get("integrationIdentifier") == integration_name
            and x.get("isConfigured")
        ]

    @staticmethod
    def _flatten_playbook_steps(steps: list) -> list[dict]:
        """Flatten playbook steps with parallel actions to one list

        Args:
            steps: The playbook steps to flatten

        Returns:
            Flattened list of steps

        """
        flat_steps = []
        for step in steps:
            if step.get("actionProvider") == "ParallelActionsContainer":
                flat_steps.extend(step.get("parallelActions"))
            flat_steps.append(step)
        return flat_steps

    def _set_step_parameter_by_name(
        self,
        step: dict,
        parameter_name: str,
        parameter_value: str | None,
    ):
        """Set the value of a step parameter

        Args:
            step: The step to reconfigure
            parameter_name: Name of the parameter to reconfigure
            parameter_value: New value of the parameter

        """
        self._get_step_parameter_by_name(
            step, parameter_name)["value"] = (parameter_value)

    @staticmethod
    def _get_step_parameter_by_name(step: dict,
                                    parameter_name: str) -> dict | None:
        """Get a workflow step parameter by name

        Args:
            step: The step to get the parameter from
            parameter_name: Name of the parameter

        Returns:
            The parameter dict instance, or None if not found

        """
        return next(
            (x for x in step.get("parameters")
             if x.get("name") == parameter_name),
            None,
        )

    @staticmethod
    def _copy_ids_from_existing_workflow(workflow: Workflow,
                                         other: dict) -> None:
        """Reconfigure 'workflow' values according to 'other' workflow

        Args:
            workflow: The workflow to copy the ids to
            other: A dict of the other workflow to copy the ids from

        """
        workflow.raw_data["id"] = other.get("id")
        workflow.raw_data["identifier"] = other.get("identifier")
        workflow.raw_data["originalPlaybookIdentifier"] = other.get(
            "originalPlaybookIdentifier", )
        workflow.raw_data["trigger"]["id"] = other.get("trigger").get("id")
        workflow.raw_data["trigger"]["identifier"] = other.get("trigger").get(
            "identifier", )
        workflow.raw_data["categoryName"] = other.get("categoryName")
        workflow.raw_data["categoryId"] = other.get("categoryId")

    def _define_workflow_as_new(self, workflow: Workflow) -> None:
        """Generate a new identifier and create the playbook category if it doesn't exist

        Args:
            workflow: A new workflow to reconfigure

        """
        workflow.raw_data["identifier"] = workflow.raw_data[
            "originalPlaybookIdentifier"] = str(uuid.uuid4())
        workflow.raw_data["trigger"]["id"] = 0
        workflow.raw_data["trigger"]["identifier"] = str(uuid.uuid4())

        if workflow.category not in self._playbook_categories:
            category = self.api.create_playbook_category(workflow.category)
            self.refresh_cache_item("categories")
        else:
            category = self._playbook_categories.get(workflow.category)

        workflow.raw_data["categoryId"] = category.id

    def _link_nested_block_step(self, step: dict) -> None:
        """Links a nested block step to the correct block that is stored on the system

        Args:
            step: A nested workflow step to reconfigure

        """
        if (step.get("name") in self._installed_playbooks and
                self._installed_playbooks[step.get("name")].get("playbookType")
                == WorkflowTypes.BLOCK.value):
            nested_workflow_identifier = self._get_step_parameter_by_name(
                step,
                "NestedWorkflowIdentifier",
            )
            if nested_workflow_identifier:
                nested_workflow_identifier[
                    "value"] = self._installed_playbooks[step.get("name")].get(
                        "identifier")

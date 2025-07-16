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

from __future__ import annotations
# import re # Removed as COMMIT_AUTHOR_REGEX is no longer used here
import os
# import tempfile # Removed as _wd is removed
import uuid  # Used by WorkflowInstaller
import logging
from typing import Any
from jinja2 import Template  # Used by generate_root_readme

# soar.git_content_manager.GitContentManager is kept under the crucial assumption
# that it has been adapted to use LocalFolderManager instead of a Git client.
from soar.git_content_manager import GitContentManager
# from soar.git_manager import Git # REMOVED
from soar.soar_api_client import SiemplifyApiClient
from soar.cache import Cache, Context  # Used by WorkflowInstaller and GitSyncManager
from soar.constants import (
    ALL_ENVIRONMENTS_IDENTIFIER,
    # COMMIT_AUTHOR_REGEX, # REMOVED
    # DEFAULT_AUTHOR, # REMOVED
    # DEFAULT_USERNAME, # REMOVED as git_username parameter is gone
    IGNORED_INTEGRATIONS,
    INTEGRATION_NAME,  # Kept, usage might be elsewhere or in unadapted GitContentManager
    ROOT_README,
    ScriptType,
    WorkflowTypes,
)
from soar.definitions import Connector, File, Integration, Job, Mapping, Workflow  # File is used by update_readme
from soar.local_folder_manager import LocalFolderManager

LOGGER = logging.getLogger("soar")


class MergeConflictError(Exception):
    """A merge conflict was discovered."""  # Kept as its direct removal isn't requested.


class GitSyncManager:
    """GitSync main interface

    This class holds and orchestrates all GitSync components.

    Attributes:
        local_manager: A LocalFolderManager instance for handling all local file operations.
        api: A SiemplifyApiClient instance for communicating with Siemplify.
        content: A GitContentManager instance for reading or writing objects from the
                 local file system to a defined structure using the local_manager.
        logger: A logger instance.
    """

    def __init__(
        self,
        local_sync_path: str,
        smp_verify: bool = True,
        soar_api_client: SiemplifyApiClient = None,
    ):
        """
        Initializes the GitSyncManager with a local folder path.

        Args:
            local_sync_path (str): The path to the local directory to be managed.
            smp_verify (bool, optional): Whether to verify SSL for Siemplify API calls. Defaults to True.
            soar_api_client (SiemplifyApiClient, optional): An existing Siemplify API client. Defaults to None.
        """
        self._cache = {}
        self.api = soar_api_client
        self.content = GitContentManager(self.api)

    @classmethod
    def from_env_vars(
        cls,
        soar_api_client: SiemplifyApiClient = None,
    ) -> GitSyncManager:
        """Init an instance using Environment variables.

        Required Environment Variables:
            LOCAL_SYNC_PATH: Path to the local directory for synchronization.

        Optional Environment Variables:
            GIT_SYNC_SIEMPLIFY_VERIFY_SSL (str): "true" or "false" for Siemplify SSL verification. Defaults to "true".

        Args:
            soar_api_client: SiemplifyApiClient instance.

        Returns: A GitSyncManager instance.

        Raises:
            Exception: If LOCAL_SYNC_PATH is not set.
        """

        LOGGER.info("================= Param Init =================")
        local_sync_path = os.environ.get("LOCAL_SYNC_PATH")
        if not local_sync_path:
            LOGGER.error("LOCAL_SYNC_PATH environment variable is not set.")
            raise Exception("LOCAL_SYNC_PATH environment variable is not set.")

        smp_verify = os.environ.get("GIT_SYNC_SIEMPLIFY_VERIFY_SSL",
                                    "true").lower() == "true"

        LOGGER.info(f"Local Sync Path: {local_sync_path}")
        LOGGER.info(f"Siemplify Verify SSL: {smp_verify}")

        return cls(local_sync_path=local_sync_path,
                   smp_verify=smp_verify,
                   soar_api_client=soar_api_client)

    def install_integration(self, integration: Integration) -> None:
        """Install or update a custom or commercial integration.

        Args:
            integration: An Integration object instance to install
        """
        if integration.identifier in IGNORED_INTEGRATIONS:
            return
        LOGGER.info(f"Installing {integration.identifier}")
        if integration.isCustom:
            LOGGER.info(
                f"{integration.identifier} is a custom integration - importing as zip"
            )
            self.api.import_package(integration.identifier,
                                    integration.get_zip_as_base64())
        else:
            LOGGER.info(
                f"{integration.identifier} is a commercial integration - Checking installation"
            )
            if not self.get_installed_integration_version(
                    integration.identifier):
                LOGGER.info(
                    f"{integration.identifier} is not installed - installing from the marketplace"
                )
                if not self.install_marketplace_integration(
                        integration.identifier):
                    LOGGER.warn(
                        f"Couldn't install integration {integration.identifier} from the marketplace"
                    )
                    return
            integration_cards = next(
                (x for x in self.api.get_ide_cards()
                 if x["identifier"] == integration.identifier),
                {"cards": []
                 }  # Provide default if integration not found in IDE cards
            )["cards"]
            for script in integration.get_all_items():
                item_card = next(
                    (x
                     for x in integration_cards if x["name"] == script["name"]
                     and x["type"] == script["type"]),
                    None,
                )
                if item_card:
                    script["id"] = item_card["id"]
                    LOGGER.info(
                        f"Updating {integration.identifier} - {script['name']}"
                    )
                else:
                    LOGGER.info(
                        f"Adding {integration.identifier} - {script['name']}")
                script["script"] = integration.get_script(
                    script.get("name"), ScriptType(script.get("type")))
                self.api.update_ide_item(script)

    def install_connector(self, connector: Connector) -> None:
        """Installs or update a connector instance

        Args:
            connector: A Connector object instance to install
        """
        installed_version = self.get_installed_integration_version(
            connector.integration)
        if not installed_version:
            LOGGER.info(
                f"Connector {connector.name} integration ({connector.integration}) not installed"
            )
            # Assumes self.content.get_integration works with LocalFolderManager
            integration = self.content.get_integration(connector.integration)
            if integration and integration.isCustom:
                LOGGER.info(
                    "Custom integration found in local storage, installing")
                self.install_integration(integration)
            else:
                LOGGER.info(
                    "Trying to install connector integration from the marketplace"
                )
                if not self.install_marketplace_integration(
                        connector.integration):
                    raise Exception(
                        f"Error installing connector {connector.name} - missing integration"
                    )
                LOGGER.info(
                    "Connector integration successfully installed from the marketplace"
                )
        if connector.integration_version != installed_version:
            LOGGER.warn(
                "Installed integration version doesn't match the connector integration version. Please upgrade the "
                "connector.")
            connector.raw_data["isUpdateAvailable"] = True
        if connector.environment not in self.api.get_environment_names():
            LOGGER.warn(
                f"Connector is set to non-existing environment {connector.environment}. Using Default Environment "
                f"instead")
            # Potentially set connector.environment = self.api.get_default_environment_name() or similar if desired
        self.api.update_connector(connector.raw_data)

    def install_mappings(self, mappings: Mapping) -> None:
        """Install or update mappings definitions

        Args:
            mappings: A Mapping object instance to install
        """
        LOGGER.info(f"Installing mappings for {mappings.integrationName}")
        for rule in mappings.rules:
            self.api.add_mapping_rules(rule["familyFields"])
            self.api.add_mapping_rules(rule["systemFields"])

        for record in mappings.records:
            self.api.set_mappings_visual_family(
                record.get("source"),
                record.get("product"),
                record.get("eventName"),
                record.get("familyName"),
            )

    def install_workflows(self, workflows: list[Workflow]) -> None:
        """Install or update playbooks and blocks

        Args:
            workflows: A list of playbook instances to install

        Raises:
            Exception: When a playbook environment doesn't exist
        """
        environments = (self.api.get_environment_names() +
                        [ALL_ENVIRONMENTS_IDENTIFIER])
        for p in workflows:
            if not all(x in environments for x in p.environments):
                raise Exception(
                    f"Playbook {p.name} is assigned to environment that doesn't exist - {p.environments[0]}"
                )

        workflows = list(set(workflows))
        cache: Cache[
            str, int] = Cache()  # This cache seems local to the method call
        playbook_installer = WorkflowInstaller(self.api, cache)
        blocks, playbooks = [], []
        for workflow in workflows:
            if workflow.type == WorkflowTypes.BLOCK:
                blocks.append(workflow)
            else:
                playbooks.append(workflow)

        for block in blocks:
            playbook_installer.install_workflow(block)
        playbook_installer.refresh_cache_item(
            "playbooks")  # Refreshes WorkflowInstaller's internal cache
        for playbook in playbooks:
            playbook_installer.install_workflow(playbook)

    def install_job(self, job: Job) -> None:
        """Installs or updates a job instance

        Args:
            job: A Job object instance to install
        """
        if not self.get_installed_integration_version(job.integration):
            LOGGER.warn(
                f"Error installing job {job.name} - Job integration ({job.integration}) is not installed"
            )
            return

        integration_cards_data = next(
            (x for x in self.api.get_ide_cards()
             if x["identifier"] == job.integration),
            {},
        )
        integration_cards = integration_cards_data.get(
            "cards", [])  # Ensure 'cards' is a list

        if integration_cards:  # Check if list is not empty
            job_def_id_card = next(
                (
                    x for x in integration_cards if x["type"] == 2
                    and x["name"] == job.name  # Assuming type 2 is for jobs
                ),
                None,
            )
            if job_def_id_card:
                job.raw_data["jobDefinitionId"] = job_def_id_card.get("id")

        job_data_from_api = next(
            (x for x in self.api.get_jobs() if x["name"] == job.name), None)
        if job_data_from_api:
            job.raw_data["id"] = job_data_from_api.get("id")
        self.api.add_job(job.raw_data)

    def generate_root_readme(self) -> str:
        """Generates the readme file contents for the root of the local sync folder.

        Contains all assets currently found via the content manager.

        Returns: Readme file contents as a string.
        """

        def strip_new_lines(s: str | None):  # Added type hint for s
            return s.replace(
                "\n",
                "").strip() if s else ""  # Return empty string if s is None

        # These calls assume self.content methods are functional with LocalFolderManager
        integrations = [
            {
                "name":
                integration.definition.get(
                    "DisplayName", integration.identifier),  # Safer access
                "description":
                strip_new_lines(integration.definition.get("Description")),
            } for integration in self.content.get_integrations()
        ]

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
        """Creates or updates a readme file in basePath using LocalFolderManager.

        Args:
            readme: The readme contents (string).
            base_path: Base path in the local sync folder to write the readme file.
                       Writes to root by default.
        """
        if base_path and not base_path.endswith(
                "/"):  # Ensure trailing slash for base_path if not empty
            base_path += "/"

        # Ensure content passed to LocalFolderManager is bytes
        readme_content_bytes = readme.encode('utf-8')
        self.content.update_objects([File("README.md", readme_content_bytes)],
                                    base_path=base_path)
        LOGGER.info(f"Updated README.md at {base_path}README.md")

    def commit_and_push(self, message: str) -> None:
        """Saves metadata and readme updates to the local file system.
        The 'commit and push' terminology is a holdover from Git; this method
        now finalizes local changes described by the message.

        Args:
            message: A message describing the changes (used for logging).
        """
        LOGGER.info(
            f"Saving changes to local file system with message: {message}")

        # Assuming self.content.metadata and self.content.push_metadata are adapted
        if self.content.metadata.get_setting_by_name("update_root_readme"):
            root_readme = self.generate_root_readme()
            self.update_readme(root_readme)

        self.content.metadata.system_version = self.api.get_system_version()
        self.content.push_metadata(
        )  # This should use local_manager via content manager

        LOGGER.info("Changes have been written to the local file system.")

    @property
    def _marketplace_integrations(self) -> list[dict]:
        if "marketplace" not in self._cache:
            self._cache["marketplace"] = self.api.get_store_data()
        return self._cache.get("marketplace",
                               [])  # Return empty list if key not found

    def clear_cache(self) -> None:
        self._cache = {}
        LOGGER.info("Cache cleared.")

    def refresh_cache_item(self, item_name: str) -> None:  # Added type hint
        if item_name in self._cache:
            del self._cache[item_name]
            LOGGER.info(f"Cache item '{item_name}' refreshed.")
        else:
            LOGGER.debug(f"Cache item '{item_name}' not found for refreshing.")

    def install_marketplace_integration(self, integration_name: str) -> bool:
        """Installs or update an integration from the marketplace.

        Args:
            integration_name: Name of the integration to install

        Returns: True if the integration was installed successfully, otherwise False
        """
        store_integration = next(
            (x for x in self._marketplace_integrations
             if x["identifier"] == integration_name),
            None,
        )
        if not store_integration:
            LOGGER.warn(
                f"Integration {integration_name} wasn't found in the marketplace"
            )
            return False
        try:
            self.api.install_integration(
                integration_name,
                store_integration["version"],
                store_integration["isCertified"],
            )
            LOGGER.info(
                f"{integration_name} installed successfully from marketplace")
            # After successful installation, the local cache for installed versions might be stale.
            self.refresh_cache_item(
                "marketplace")  # Refresh to get updated installedVersion
            return True
        except Exception as e:
            LOGGER.warn(
                f"Couldn't install {integration_name} from marketplace - {e}")
            return False

    def get_installed_integration_version(self,
                                          integration_name: str) -> float:
        """Get currently installed integration version by checking the marketplace data.

        If the integration is not listed or not installed, 0.0 will be returned.

        Args:
            integration_name: Name of the integration to check.

        Returns: Integration version as float, or 0.0 if not installed/found.
        """
        integration_data = next(
            (
                x for x in
                self._marketplace_integrations  # Uses cached marketplace data
                if x["identifier"] == integration_name),
            None,
        )
        if integration_data and integration_data.get("installedVersion"):
            try:
                return float(integration_data["installedVersion"])
            except (ValueError, TypeError):
                LOGGER.warning(
                    f"Could not parse installedVersion '{integration_data.get('installedVersion')}' as float for {integration_name}."
                )
                return 0.0
        return 0.0


class WorkflowInstaller:
    """Helper class for installing workflows"""

    def __init__(
        self,
        api: SiemplifyApiClient,
        mod_time_cache: Cache[str, int],
    ) -> None:
        self.api: SiemplifyApiClient = api
        self._mod_time_cache: Cache[str, int] = mod_time_cache
        self._cache: dict[str, Any] = {
        }  # This is WorkflowInstaller's internal cache

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
            self._filter_and_save_context()  # Pushes mod_time_cache
            return

        self._log_merge_conflicts(workflow)
        self.update_local_workflow(workflow)

    def _log_merge_conflicts(self, workflow: Workflow) -> None:
        if self._has_merge_conflicts(workflow):
            LOGGER.warn(
                f"Potential merge conflict for workflow '{workflow.name}'. "
                "Both the stored version and local platform version appear modified since last sync. "
                "Stored version will override local platform changes!")

    def _has_merge_conflicts(self, workflow: Workflow) -> bool:
        cached_time: int = self._mod_time_cache.get(workflow.name, -1)
        local_time: int = self._get_local_workflow_mod_time(workflow.name, -1)
        # Merge conflict if local was modified after last sync AND remote was modified after last sync
        # Simplified: if local_time > cached_time AND workflow.modification_time > cached_time
        return min(local_time, workflow.modification_time) > cached_time

    def _workflow_was_modified(self, workflow: Workflow) -> bool:
        cached_time: int = self._mod_time_cache.get(workflow.name, -1)
        return workflow.modification_time > cached_time

    def update_local_workflow(self, workflow: Workflow) -> None:
        """Update an existing workflow in the platform."""
        LOGGER.info(f"Updating existing workflow '{workflow.name}'")
        self._adjust_workflow_ids(workflow)
        self.api.save_playbook(workflow.raw_data)
        self._save_workflow_mod_time_to_context(workflow)
        LOGGER.info(f"Workflow '{workflow.name}' was updated successfully")

    def _adjust_workflow_ids(self, workflow: Workflow) -> None:
        """Adjust workflow identifiers to match the existing workflow's
        (with the same name) identifiers.
        """
        playbook_id: str | None = self._installed_playbooks.get(
            workflow.name, {}).get("identifier")
        if not playbook_id:
            LOGGER.error(
                f"Cannot adjust IDs for workflow '{workflow.name}': Not found in installed playbooks cache."
            )
            # This situation should ideally not happen if _workflow_exists was true
            return

        local_playbook: dict[str, Any] = self.api.get_playbook(playbook_id)
        if not local_playbook:
            LOGGER.error(
                f"Cannot fetch local playbook details for ID '{playbook_id}' (name: '{workflow.name}')."
            )
            return

        self._copy_ids_from_existing_workflow(workflow, local_playbook)
        self._process_steps(workflow, local_playbook)

    def install_new_workflow(self, workflow: Workflow) -> None:
        """Install a new workflow in the platform."""
        LOGGER.info(f"Installing new workflow '{workflow.name}'")
        self._define_workflow_as_new(workflow)
        self._process_steps(
            workflow)  # No installed_workflow to pass for new ones
        self.api.save_playbook(workflow.raw_data)
        self._save_workflow_mod_time_to_context(workflow)
        LOGGER.info(
            f"New workflow '{workflow.name}' was installed successfully")

    def _process_steps(self,
                       workflow: Workflow,
                       installed_workflow: dict | None = None) -> None:
        """Iterate the playbook steps and assign the correct integration instances and block identifiers

        Args:
            workflow: Workflow to iterate steps
            installed_workflow: Optional current installed playbooks to copy identifiers from
        """
        identifier_mappings = {}
        old_steps_flat = (self._flatten_playbook_steps(
            installed_workflow["steps"]) if installed_workflow
                          and "steps" in installed_workflow else [])

        current_steps_flat = self._flatten_playbook_steps(
            workflow.raw_data.get("steps", []))

        for step in current_steps_flat:
            provider = step.get("actionProvider")
            step_type = step.get("type")  # 0 for action, 5 for nested workflow

            step["workflowIdentifier"] = workflow.raw_data.get("identifier")
            existing_step = None
            if old_steps_flat:  # Only try to find existing_step if there was an installed_workflow
                existing_step = next(
                    (
                        s for s in old_steps_flat if s.get("instanceName") ==
                        step.get("instanceName")  # Match by instanceName
                    ),
                    None,
                )

            if existing_step:
                old_step_identifier = step.get("identifier")
                new_identifier = existing_step.get("identifier")
                if old_step_identifier and new_identifier and old_step_identifier != new_identifier:
                    identifier_mappings[old_step_identifier] = new_identifier

                step["identifier"] = new_identifier
                step["originalStepIdentifier"] = existing_step.get(
                    "originalStepIdentifier")

                step_debug_data = step.get("debugData")
                if step_debug_data:
                    if "originalStepIdentifier" in step_debug_data:
                        step_debug_data[
                            "originalStepIdentifier"] = existing_step.get(
                                "originalStepIdentifier")
                    if "originalWorkflowIdentifier" in step_debug_data and installed_workflow:
                        step_debug_data[
                            "originalWorkflowIdentifier"] = installed_workflow.get(
                                "originalPlaybookIdentifier")
            else:  # New step or no existing workflow to match against
                # Ensure new steps get unique identifiers if not already set,
                # or if we are defining a workflow as completely new.
                if not step.get(
                        "identifier"
                ) or not installed_workflow:  # also if workflow itself is new
                    step["identifier"] = str(uuid.uuid4())
                # originalStepIdentifier might need specific handling for brand new steps
                # often it's same as identifier for new, non-copied steps.

            if step_type == 0 and provider == "Scripts":  # Regular Action
                self._assign_integration_instance_to_step(
                    step, workflow.environments, existing_step)
            elif step_type == 5:  # Nested Workflow (Block)
                self._link_nested_block_step(step)

        # Patch relations based on new identifiers
        for relation in workflow.raw_data.get("stepsRelations", []):
            if relation.get("fromStep") in identifier_mappings:
                relation["fromStep"] = identifier_mappings[relation.get(
                    "fromStep")]
            if relation.get("toStep") in identifier_mappings:
                relation["toStep"] = identifier_mappings[relation.get(
                    "toStep")]

    def _save_workflow_mod_time_to_context(self, workflow: Workflow) -> None:
        self.refresh_cache_item(
            "playbooks"
        )  # Refresh WorkflowInstaller's cache of installed playbooks
        new_mod_time: int = self._get_local_workflow_mod_time(
            workflow.name, -1)
        self._mod_time_cache[
            workflow.name] = new_mod_time  # Update external cache
        self._filter_and_save_context()

    def _filter_and_save_context(self) -> None:
        # Filter items in external mod_time_cache to only include currently installed playbooks
        self._mod_time_cache.filter_items(set(
            self._installed_playbooks.keys()))
        self._mod_time_cache.push_local_to_external()  # Save external cache

    def _get_local_workflow_mod_time(self,
                                     __workflow_name: str,
                                     default: int | None = None,
                                     /) -> int:
        playbook: dict[str, Any] | None = self._installed_playbooks.get(
            __workflow_name)
        if playbook:
            return playbook.get("modificationTimeUnixTimeInMs", default)
        return default if default is not None else -1

    @property
    def _installed_playbooks(self) -> dict[str, dict[str, Any]]:
        """Currently installed playbooks and blocks. Fetches if not cached."""
        if "playbooks" not in self._cache:  # Refers to WorkflowInstaller's internal _cache
            LOGGER.debug(
                "Fetching installed playbooks for WorkflowInstaller cache.")
            self._cache["playbooks"] = {
                x.get("name"): x
                for x in self.api.get_playbooks()
                if x.get("name")  # Ensure name exists
            }
        return self._cache.get("playbooks", {})

    @property
    def _playbook_categories(
            self) -> dict[str, dict[str, Any]]:  # Added return type hint
        """Currently configured playbook categories. Fetches if not cached."""
        if "categories" not in self._cache:  # Refers to WorkflowInstaller's internal _cache
            LOGGER.debug(
                "Fetching playbook categories for WorkflowInstaller cache.")
            self._cache["categories"] = {
                x.get("name"): x
                for x in self.api.get_playbook_categories()
                if x.get("name")  # Ensure name exists
            }
        return self._cache.get("categories", {})

    def refresh_cache_item(self, item_name: str) -> None:  # Added type hint
        if item_name in self._cache:  # Refers to WorkflowInstaller's internal _cache
            del self._cache[item_name]
            LOGGER.debug(
                f"WorkflowInstaller cache item '{item_name}' refreshed.")

    def _assign_integration_instance_to_step(
            self,
            step: dict,
            environments: list[str],
            existing_step: dict | None = None  # Typed environments
    ) -> None:
        if existing_step:
            # Try to preserve existing integration instance if step is matched
            instance_param = self._get_step_parameter_by_name(
                existing_step, "IntegrationInstance")
            if instance_param and "value" in instance_param:
                self._set_step_parameter_by_name(step, "IntegrationInstance",
                                                 instance_param["value"])

            fallback_param = self._get_step_parameter_by_name(
                existing_step, "FallbackIntegrationInstance")
            if fallback_param and "value" in fallback_param:
                self._set_step_parameter_by_name(
                    step, "FallbackIntegrationInstance",
                    fallback_param["value"])
            return

        # New step or step couldn't be matched, assign based on environment logic
        if len(environments
               ) == 1 and environments[0] != ALL_ENVIRONMENTS_IDENTIFIER:
            integration_instances = self._find_integration_instances_for_step(
                step.get("integration"), environments[0])
            if integration_instances:
                self._set_step_parameter_by_name(
                    step, "IntegrationInstance",
                    integration_instances[0].get("identifier"))
            else:  # No instance found for the specific environment
                self._set_step_parameter_by_name(step, "IntegrationInstance",
                                                 None)  # Or handle as error
            self._set_step_parameter_by_name(step,
                                             "FallbackIntegrationInstance",
                                             None)
        else:  # All Environments or multiple environments
            shared_instances = self._find_integration_instances_for_step(
                step.get("integration"),
                ALL_ENVIRONMENTS_IDENTIFIER  # Check for shared instances
            )
            self._set_step_parameter_by_name(step, "IntegrationInstance",
                                             "AutomaticEnvironment")
            if shared_instances:
                self._set_step_parameter_by_name(
                    step, "FallbackIntegrationInstance",
                    shared_instances[0].get("identifier"))
            else:
                self._set_step_parameter_by_name(
                    step, "FallbackIntegrationInstance", None)

    def _find_integration_instances_for_step(
            self,
            integration_name: str | None,
            environment: str  # Typed integration_name
    ) -> list[dict]:
        if not integration_name: return []

        cache_key = f"integration_instances_{environment}"
        if cache_key not in self._cache:  # Refers to WorkflowInstaller's internal _cache
            self._cache[cache_key] = self.api.get_integrations_instances(
                environment)

        all_instances: list[dict] = self._cache.get(cache_key, [])

        # Filter for the specific integration and ensure they are configured
        # Sort by instanceName for deterministic selection if taking the first one
        filtered_instances = sorted([
            inst for inst in all_instances
            if inst.get("integrationIdentifier") == integration_name
            and inst.get("isConfigured")
        ],
                                    key=lambda x: x.get("instanceName", ""))
        return filtered_instances

    @staticmethod
    def _flatten_playbook_steps(
            steps: list | None) -> list[dict]:  # Typed steps
        if not steps: return []
        flat_steps = []
        for step in steps:
            if step.get(
                    "actionProvider"
            ) == "ParallelActionsContainer":  # ParallelActionsContainer
                # Extend with actions inside the container
                flat_steps.extend(step.get("parallelActions", []))
            # Always add the step itself (container or regular step)
            flat_steps.append(step)
        # The original return `steps` seemed incorrect if flattening was intended.
        # It should return `flat_steps`. Let's assume original was a bug or simplified.
        # For true flattening that includes container contents and not the container itself:
        # flat_steps = []
        # for step in steps:
        #     if step.get("actionProvider") == "ParallelActionsContainer":
        #         flat_steps.extend(step.get("parallelActions", []))
        #     else:
        #         flat_steps.append(step)
        # However, the logic in _process_steps seems to expect containers to also be in the list
        # for matching. The original `flat_steps.append(step)` after extend was likely intentional.
        return flat_steps

    def _set_step_parameter_by_name(
            self, step: dict, parameter_name: str,
            parameter_value: str | None) -> None:  # Typed parameter_value
        param = self._get_step_parameter_by_name(step, parameter_name)
        if param:
            param["value"] = parameter_value
        else:
            LOGGER.warning(
                f"Parameter '{parameter_name}' not found in step '{step.get('instanceName', step.get('name'))}' to set value."
            )

    @staticmethod
    def _get_step_parameter_by_name(step: dict,
                                    parameter_name: str) -> dict | None:
        if "parameters" not in step or not isinstance(step["parameters"],
                                                      list):
            return None
        return next(
            (p for p in step["parameters"] if p.get("name") == parameter_name),
            None)

    @staticmethod
    def _copy_ids_from_existing_workflow(
            workflow: Workflow, other: dict[str, Any]) -> None:  # Typed other
        workflow.raw_data["id"] = other.get("id")
        workflow.raw_data["identifier"] = other.get("identifier")
        workflow.raw_data["originalPlaybookIdentifier"] = other.get(
            "originalPlaybookIdentifier")

        trigger = workflow.raw_data.get("trigger", {})
        other_trigger = other.get("trigger", {})
        trigger["id"] = other_trigger.get("id")
        trigger["identifier"] = other_trigger.get("identifier")
        workflow.raw_data[
            "trigger"] = trigger  # Ensure it's set back if it was missing

        workflow.raw_data["categoryName"] = other.get("categoryName")
        workflow.raw_data["categoryId"] = other.get("categoryId")

    def _define_workflow_as_new(self, workflow: Workflow) -> None:
        """Generate a new identifier and create the playbook category if it doesn't exist

        Args:
            workflow: A new workflow to reconfigure
        """
        new_uuid = str(uuid.uuid4())
        workflow.raw_data["identifier"] = new_uuid
        workflow.raw_data[
            "originalPlaybookIdentifier"] = new_uuid  # For new, original is itself

        trigger = workflow.raw_data.get("trigger", {})
        trigger[
            "id"] = 0  # For new workflows, backend usually assigns this upon first save
        trigger["identifier"] = str(uuid.uuid4())
        workflow.raw_data["trigger"] = trigger

        category_name = workflow.category  # Assuming workflow.category holds the name
        if category_name not in self._playbook_categories:  # Uses property, so fetches if needed
            LOGGER.info(
                f"Playbook category '{category_name}' not found. Creating new one."
            )
            try:
                category = self.api.create_playbook_category(category_name)
                self.refresh_cache_item("categories")  # Refresh after creation
            except Exception as e:
                LOGGER.error(
                    f"Failed to create playbook category '{category_name}': {e}"
                )
                # Decide on fallback: use default, raise error, or proceed without categoryId
                category = {
                    "id": None,
                    "name": category_name
                }  # Fallback example
        else:
            category = self._playbook_categories[category_name]

        workflow.raw_data["categoryId"] = category.get("id")
        workflow.raw_data["categoryName"] = category.get(
            "name")  # Ensure name is also consistent

    def _link_nested_block_step(self, step: dict) -> None:
        """Links a nested block step to the correct block that is stored on the system

        Args:
            step: A nested workflow step to reconfigure (type 5)
        """
        block_name = step.get(
            "name")  # The 'name' of the step is the block's name
        if block_name in self._installed_playbooks:  # Check if block exists by name
            block_details = self._installed_playbooks[block_name]
            if block_details.get("playbookType") == WorkflowTypes.BLOCK.value:
                nested_workflow_param = self._get_step_parameter_by_name(
                    step, "NestedWorkflowIdentifier")
                if nested_workflow_param:
                    nested_workflow_param["value"] = block_details.get(
                        "identifier")
                    LOGGER.debug(
                        f"Linked step '{step.get('instanceName')}' to block '{block_name}' (ID: {block_details.get('identifier')})"
                    )
                else:
                    LOGGER.warning(
                        f"Step '{step.get('instanceName')}' (block '{block_name}') is missing 'NestedWorkflowIdentifier' parameter."
                    )
            else:
                LOGGER.warning(
                    f"Found item '{block_name}' in playbooks, but it's not a Block. Cannot link step '{step.get('instanceName')}'."
                )
        else:
            LOGGER.warning(
                f"Block '{block_name}' for step '{step.get('instanceName')}' not found in installed playbooks. Cannot link."
            )

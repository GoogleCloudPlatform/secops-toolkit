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

from jinja2 import Template
from soar.git_sync_manager import GitSyncManager
from soar.constants import PLAYBOOKS_ROOT_README
import click
from soar.definitions import Workflow
from soar.soar_api_client import SiemplifyApiClient
import os
import logging
import sys

LOGGER = logging.getLogger("soar")

# Environment Variables
INCLUDE_BLOCKS = os.environ.get("INCLUDE_PLAYBOOK_BLOCKS",
                                "false").lower() == "true"
EXCLUDE_FOLDER = os.environ.get("EXCLUDE_FOLDER", "Development")


# --- CLI Commands ---
@click.group()
def cli():
    """Manages Response As Code."""
    pass


def create_root_readme(gitsync: GitSyncManager):
    """
    Creates the content for the root README file based on the playbooks in the Git repository.
    :param gitsync: The GitSyncManager instance.
    :return: The rendered README content as a string.
    """
    playbooks = []
    for pb in gitsync.content.get_playbooks():
        playbooks.append(pb.raw_data)
    readme = Template(PLAYBOOKS_ROOT_README)
    return readme.render(playbooks=playbooks)


@cli.command(name="sync-playbooks")
def sync_playbooks():

    api = SiemplifyApiClient(os.environ.get("TARGET_SOAR_API_URL"),
                             os.environ.get("TARGET_SOAR_API_KEY"), True)
    soc_roles = api.get_soc_roles()

    try:
        gitsync = GitSyncManager.from_env_vars(soar_api_client=api)

        playbooks = {}
        git_playbooks = list(gitsync.content.get_playbooks())
        LOGGER.info(f"Git Playbooks len {len(git_playbooks)}")

        for playbook in git_playbooks:
            LOGGER.info(f"Playbook {playbook.name}")

            overview_templates = playbook.raw_data["overviewTemplates"]
            new_templates = []
            for overview_template in overview_templates:
                LOGGER.info(f"Roles: {overview_template['roles']}")
                new_roles = []
                for role in overview_template['roles']:
                    for soc_role in soc_roles:
                        if soc_role["name"] == role:
                            new_roles.append(soc_role["id"])
                overview_template["roles"] = new_roles
                new_templates.append(overview_template)
            playbook.raw_data["overviewTemplates"] = new_templates
            LOGGER.info(
                f"Playbook Updated Overview templates: {playbook.raw_data['overviewTemplates']}"
            )

            playbooks[playbook.name] = playbook

            if INCLUDE_BLOCKS:
                for block in playbook.get_involved_blocks():
                    if block.get("name") not in playbooks:
                        block = gitsync.content.get_playbook(block.get("name"))
                        if block:
                            playbooks[block.name] = block

        gitsync.install_workflows(list(playbooks.values()))

    except Exception as e:
        LOGGER.error(f"General error performing Sync Playbooks")
        LOGGER.exception(e)
        raise


@cli.command(name="pull-playbooks")
def pull_playbooks():
    """
    Synchronize SOAR playbooks from the SOAR platform to a Git repository.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    commit_msg = os.environ.get("COMMIT_MESSAGE", "Automated playbook sync")
    readme_addon = os.environ.get("README_ADDON")
    include_blocks = os.environ.get("INCLUDE_PLAYBOOK_BLOCKS",
                                    "false").lower() == "true"

    api = SiemplifyApiClient(os.environ.get("SOURCE_SOAR_API_URL"),
                             os.environ.get("SOURCE_SOAR_API_KEY"), True)
    soc_roles = api.get_soc_roles()

    try:
        gitsync = GitSyncManager.from_env_vars(soar_api_client=api)
        installed_playbooks = gitsync.api.get_playbooks()

        for playbook in installed_playbooks:
            if EXCLUDE_FOLDER in playbook.get("categoryName"):
                LOGGER.info(
                    "Skip playbook since belongs to the excluded folder")
                continue

            LOGGER.info(f"Pushing Playbook {playbook['name']}")

            if readme_addon:
                LOGGER.info(
                    "Readme addon found - adding to GitSync metadata file (GitSync.json)"
                )
                gitsync.content.metadata.set_readme_addon(
                    "Playbook", playbook.get("name"), readme_addon)

            playbook = Workflow(
                gitsync.api.get_playbook(playbook.get("identifier")))
            overview_templates = playbook.raw_data["overviewTemplates"]
            new_templates = []
            for overview_template in overview_templates:
                LOGGER.info(f"Roles: {overview_template['roles']}")
                new_roles = []
                for role in overview_template['roles']:
                    for soc_role in soc_roles:
                        if soc_role["id"] == role:
                            new_roles.append(soc_role["name"])
                overview_template["roles"] = new_roles
                new_templates.append(overview_template)
            playbook.overview_templates = new_templates

            gitsync.content.push_playbook(playbook)
            if include_blocks:
                for block in playbook.get_involved_blocks():
                    installed_block = next(
                        (x for x in installed_playbooks
                         if x.get("name") == block.get("name")), None)
                    if not installed_block:
                        LOGGER.warning(
                            f"Block {block.get('name')} wasn't found in the repo, ignoring"
                        )
                        continue
                    block = Workflow(
                        gitsync.api.get_playbook(
                            installed_block.get("identifier")))
                    gitsync.content.push_playbook(block)

        gitsync.update_readme(create_root_readme(gitsync), "Playbooks")

    except Exception as e:
        LOGGER.error(f"General error performing Pull Playbooks")
        LOGGER.exception(e)
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.
        stdout,  # Explicitly print to stdout for GitHub Actions visibility
        force=True)

    # Ensure our specific logger is also set to INFO
    LOGGER.setLevel(logging.INFO)
    cli()

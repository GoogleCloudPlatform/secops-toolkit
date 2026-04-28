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
import os
import sys
import time
import click
from secops.exceptions import APIError
from dotenv import load_dotenv
from models import SocRole, WorkflowMenuCard, Workflow, Template
from manager import ResponseManager
from utils import get_local_playbooks, get_local_playbook
from constants import PLAYBOOKS_ROOT_README
from config import INCLUDE_BLOCKS, EXCLUDE_FOLDER

LOGGER = logging.getLogger("rac")


def create_root_readme() -> str:
    """
    Creates the content for the root README file based on the playbooks in the Git repository.
    :return: The rendered README content as a string.
    """
    playbooks = []
    for pb in get_local_playbooks():
        playbooks.append(pb.raw_data)
    readme = Template(PLAYBOOKS_ROOT_README)
    return readme.render(playbooks=playbooks)


@click.group()
def cli():
    """Manages Response As Code."""
    pass


@cli.command(name="sync-playbooks")
def sync_playbooks():

    response_manager = ResponseManager()
    soc_roles: List[SocRole] = response_manager.get_soc_roles()

    try:
        playbooks = {}
        git_playbooks = list(get_local_playbooks())
        LOGGER.info(f"Git Playbooks len {len(git_playbooks)}")

        for playbook in git_playbooks:
            LOGGER.info(f"Playbook {playbook.name}")

            overview_templates = playbook.overview_templates
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
            playbook.overview_templates = new_templates
            LOGGER.info(
                f"Playbook Updated Overview templates: {playbook.overview_templates}"
            )

            playbooks[playbook.name] = playbook

            if INCLUDE_BLOCKS:
                for block in playbook.get_involved_blocks():
                    if block.get("name") not in playbooks:
                        block = response_manager.get_playbook(
                            block.get("name"))
                        if block:
                            playbooks[block.name] = block

        response_manager.install_playbooks(list(playbooks.values()))

    except Exception as e:
        LOGGER.error(f"General error performing Sync Playbooks")
        LOGGER.exception(e)
        raise


@cli.command(name="pull-playbooks")
@click.pass_obj
def pull_playbooks(
    manager_obj: SOARManager
):  # Renamed manager to manager_obj to avoid conflict with manager instance
    """
    Synchronize SOAR playbooks from the SOAR platform to a Git repository.
    """
    commit_msg = os.environ.get("COMMIT_MESSAGE", "Automated playbook sync")
    readme_addon = os.environ.get("README_ADDON")
    include_blocks = os.environ.get("INCLUDE_PLAYBOOK_BLOCKS",
                                    "false").lower() == "true"

    response_manager = ResponseManager()

    soc_roles: List[SocRole] = response_manager.get_soc_roles()
    print(soc_roles)

    try:
        installed_playbooks: List[
            WorkflowMenuCard] = response_manager.get_playbooks()

        for playbook in installed_playbooks:
            if EXCLUDE_FOLDER and EXCLUDE_FOLDER in playbook.categoryName:
                LOGGER.info(
                    f"Skip playbook since belongs to the excluded folder: {playbook.displayName}"
                )
                continue

            LOGGER.info(f"Processing Playbook {playbook.displayName}")

            if readme_addon:
                LOGGER.info(
                    "Readme addon found - adding to GitSync metadata file (GitSync.json)"
                )
                gitsync.content.metadata.set_readme_addon(
                    "Playbook", playbook.displayName, readme_addon)

            playbook_details = Workflow(
                response_manager.get_playbook(playbook.identifier))
            LOGGER.info(f"Playbook details: {playbook_details}")
            overview_templates = playbook_details.overview_templates
            new_templates = []
            for overview_template in overview_templates:
                LOGGER.info(f"Roles: {overview_template.get('roles')}")
                new_roles = []
                for role in overview_template.get('roles', []):
                    for soc_role in soc_roles:
                        if soc_role.displayName == role:
                            new_roles.append(soc_role.name)
                overview_template["roles"] = new_roles
                new_templates.append(overview_template)
            playbook_details.overview_templates = new_templates

            response_manager.store_playbook(playbook_details)

            if include_blocks:
                for block in playbook_details.get_involved_blocks():
                    installed_block = next(
                        (x for x in installed_playbooks
                         if x.displayName == block.displayName), None)
                    if not installed_block:
                        LOGGER.warning(
                            f"Block {block.displayName} wasn't found in the repo, ignoring"
                        )
                        continue
                    block_details = Workflow(
                        response_manager.get_playbook(
                            installed_block.identifier))
                    response_manager.store_playbook(block_details)

        response_manager.update_readme(create_root_readme(), "Playbooks")

    except Exception as e:
        LOGGER.error(f"General error performing Pull Playbooks")
        LOGGER.exception(e)
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout,
        force=True)

    LOGGER.setLevel(logging.INFO)
    cli()

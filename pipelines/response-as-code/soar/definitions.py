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

import base64
import json
from collections.abc import Iterator
from typing import Any
from zipfile import ZipFile

from jinja2 import Environment as JinjaEnvironment, Template

from soar.soar_api_client import SiemplifyApiClient
from soar.constants import (
    ACTION_PARAMETER_TYPES,
    BASE_PARAMETER_TYPES,
    CONDITION_MATCH_TYPES,
    CONDITION_OPERATORS,
    CONNECTOR_README,
    INTEGRATION_README_TEMPLATE,
    JOB_README,
    MAPPING_README,
    PLAYBOOK_README_TEMPLATE,
    ScriptType,
    TRIGGER_TYPES,
    VISUAL_FAMILY_README,
    WorkflowTypes,
)


class File:
    """Represents a common file object used by the GitManager"""

    def __init__(self, path: str, contents: str | bytes):
        self.path = path
        if isinstance(contents, str):
            contents = contents.encode("utf-8")
        self.content = contents

    def __repr__(self):
        return f"{{Path: {self.path} Contents head: {self.content[:15]}...}}"


class Content:

    def __init__(self):
        self.readme: str | None = None


class Metadata:

    def __init__(self, **kwargs):

        def _get_arg_with_multiple_names(args: dict[str, Any],
                                         arg_name_options: list[str],
                                         default_value: Any):
            for name in arg_name_options:
                value = args.get(name, None)
                if value:
                    return value
            return default_value

        self.system_version = _get_arg_with_multiple_names(
            kwargs, ["system_version", "systemVersion"], "")
        self.readme_addons = _get_arg_with_multiple_names(
            kwargs,
            ["readme_addons", "readmeAddons"],
            {
                "Integration": {},
                "Mappings": {},
                "Visual Family": {},
                "Playbook": {},
                "Connector": {},
                "Job": {},
            },
        )
        self.settings = kwargs.get("settings", {"update_root_readme": True})

    def get_readme_addon(self, content_type: str,
                         content_name: str) -> str | None:
        if content_type not in self.readme_addons:
            raise KeyError(f"Content Type {content_type} doesn't exist")
        elif content_name not in self.readme_addons[content_type]:
            return None
        return self.readme_addons[content_type][content_name]

    def set_readme_addon(self, content_type: str, content_name: str,
                         readme: str) -> None:
        if content_type not in self.readme_addons:
            raise KeyError(f"Content Type {content_type} doesn't exist")
        self.readme_addons[content_type][content_name] = "\n".join(
            readme.split("\\n"))

    def get_setting_by_name(self, name: str) -> Any:
        if name not in self.settings:
            raise KeyError(f"Setting {name} not found")
        return self.settings[name]


class Connector(Content):

    def __init__(self, connector: dict):
        super().__init__()
        self.raw_data = connector
        for param in self.raw_data["params"]:
            param["creationTimeUnixTimeInMs"] = 0
            param["modificationTimeUnixTimeInMs"] = 0
        self.name = self.raw_data.get("displayName")
        self.description = self.raw_data.get("description")
        self.integration = self.raw_data.get("integration")
        self.integration_version = self.raw_data.get("integrationVersion")
        self.connector_definition_name = self.raw_data.get(
            "connectorDefinitionName")
        self.environment = self.raw_data.get("environment")

    def generate_readme(self, additional_info: str = None) -> None:
        template = CONNECTOR_README
        if additional_info:
            template += additional_info
        readme = Template(template)
        self.readme = readme.render(connector=self.raw_data)

    def iter_files(self) -> Iterator[File]:
        yield File("README.md", self.readme)
        yield File(f"{self.name}.json", json.dumps(self.raw_data, indent=4))


class VisualFamily(Content):

    def __init__(self, visual_family: dict):
        super().__init__()
        if "visualFamilyDataModel" in visual_family:
            visual_family = visual_family["visualFamilyDataModel"]
        self.raw_data = visual_family
        self.name = self.raw_data.get("family")
        self.description = self.raw_data.get("description")
        self.imageBase64 = self.raw_data.get("imageBase64")
        self.rules = self.raw_data.get("rules")
        self.raw_data["id"] = 0
        for rule in self.raw_data["rules"]:
            rule["id"] = 0

    def get_importable_format(self) -> dict:
        return {"visualFamilyDataModel": self.raw_data}

    def iter_files(self) -> Iterator[File]:
        yield File("README.md", self.readme)
        yield File(f"{self.name}.json",
                   json.dumps(self.get_importable_format(), indent=4))
        yield File(f"{self.name}.png", base64.b64decode(self.imageBase64))

    def generate_readme(self, additional_info: str = None) -> None:
        template = VISUAL_FAMILY_README
        if additional_info:
            template += additional_info
        readme = Template(template)
        self.readme = readme.render(visual_family=self.__dict__)


class Mapping(Content):

    def __init__(self, integration_name: str, records: list[dict],
                 rules: list[dict]):
        super().__init__()
        self.integrationName = integration_name
        self.records = records
        self.rules = rules
        for rec in self.records:
            rec["id"] = 0
            rec["familyId"] = 0
        for rule in self.rules:
            for fam_fields in rule["familyFields"] + rule["systemFields"]:
                fam_fields["mappingRule"]["id"] = 0
                fam_fields["mappingRule"]["creationTimeUnixTimeInMs"] = 0
                fam_fields["mappingRule"]["modificationTimeUnixTimeInMs"] = 0
                fam_fields["creationTimeUnixTimeInMs"] = 0
                fam_fields["modificationTimeUnixTimeInMs"] = 0

    def iter_files(self) -> Iterator[File]:
        yield File(f"README.md", self.readme)
        yield File(f"{self.integrationName}_Records.json",
                   json.dumps(self.records, indent=4))
        yield File(f"{self.integrationName}_Rules.json",
                   json.dumps(self.rules, indent=4))

    def generate_readme(self, additional_info: str = None) -> None:
        template = MAPPING_README
        if additional_info:
            template += additional_info
        readme = Template(template)
        self.readme = readme.render(mappings=self.__dict__)


class Integration(Content):

    def __init__(self, integration_card: dict, zip_buffer):
        super().__init__()
        self.zip_buffer = zip_buffer
        self.integration_card = integration_card

        self.zipfile = ZipFile(zip_buffer)
        self.identifier = self.integration_card.get("identifier")
        self.isCustom = self.integration_card.get("isCustomIntegration")
        self.definition = json.loads(
            self.zipfile.read(f"Integration-{self.identifier}.def"))
        self.version = self.definition.get("Version")
        if not self.isCustom:
            self.definition["IsCustom"] = False

        self.actions = []
        self.jobs = []
        self.connectors = []
        self.managers = []
        self.dependencies = []
        self.has_resources = False
        for file in [
                x for x in self.zipfile.namelist() if not x.endswith("/")
        ]:
            if file.startswith("ActionsDefinitions"):
                self.actions.append(json.loads(self.zipfile.read(file)))
            elif file.startswith("Jobs") and not file.startswith("JobsScrips"):
                self.jobs.append(json.loads(self.zipfile.read(file)))
            elif file.startswith(
                    "Connectors") and not file.startswith("ConnectorsScripts"):
                self.connectors.append(json.loads(self.zipfile.read(file)))
            elif (not self.isCustom and file.startswith("Managers")
                  and file.endswith(".managerdef")):
                self.managers.append(json.loads(self.zipfile.read(file)))
            elif self.isCustom and file.startswith("Managers"):
                self.managers.append(file)
            elif file.startswith("Dependencies"):
                self.dependencies.append(file)
            elif file.startswith("Resources/" + self.identifier + ".svg"):
                self.has_resources = True

    def get_all_items(self):
        return self.actions + self.jobs + self.connectors + self.managers

    def get_script(self, name: str, script_type: ScriptType) -> str:
        path = ""
        if script_type == ScriptType.JOB:
            path += "JobsScrips/"
        elif script_type == ScriptType.ACTION:
            path += "ActionsScripts/"
        elif script_type == ScriptType.CONNECTOR:
            path += "ConnectorsScripts/"
        elif script_type == ScriptType.MANAGER:
            path += "Managers/"
        path += f"{name}.py"
        return self.zipfile.read(path).decode("utf-8")

    def get_zip_as_base64(self):
        return base64.b64encode(self.zip_buffer.getvalue()).decode("utf-8")

    def generate_readme(self, additional_info: str = None):
        env = JinjaEnvironment()
        env.filters.update({
            "action_param_type":
            lambda x: ACTION_PARAMETER_TYPES.get(x),
            "base_param_type":
            lambda x: BASE_PARAMETER_TYPES.get(x),
        })
        template = INTEGRATION_README_TEMPLATE
        if additional_info:
            template += additional_info
        readme = env.from_string(template)
        if not self.isCustom:
            integration = {
                "dependencies": self.dependencies,
                "definition": self.definition,
                "actions": [x for x in self.actions if x["IsCustom"]],
                "jobs": [x for x in self.jobs if x["IsCustom"]],
                "connectors": [x for x in self.connectors if x["IsCustom"]],
                "has_resources": self.has_resources,
            }
            self.readme = readme.render(integration=integration)
        else:
            self.readme = readme.render(integration=self.__dict__)

    def __repr__(self):
        return self.identifier

    def iter_files(self, api: SiemplifyApiClient) -> Iterator[File]:
        """Iterates all files in integration.

        If the integration is custom, it will only return custom and mandatory files.
        if not, it will iterate all the files in the exported zip. It yields tuples of (relative_path, data)

        Args:
            api: SiemplifyApiClient object - to diff between custom and commercial scripts

        Returns: A generator of File object instances representing the integration
        """
        yield File("README.md", self.readme)
        if not self.isCustom:
            yield File(
                f"Integration-{self.identifier}.def",
                json.dumps(self.definition, indent=4),
            )

            if self.has_resources:
                for file in self.zipfile.namelist():
                    if file.startswith(
                            "Resources/") and not file.endswith("/"):
                        yield File(file, self.zipfile.read(file))

            for card in self.integration_card["cards"]:
                if card["isCustom"]:
                    definition = api.get_ide_item(card["id"], card["type"])
                    definition["id"] = 0

                    if card["type"] == ScriptType.ACTION.value:
                        yield File(
                            f"ActionsDefinitions/{card['name']}.actiondef",
                            json.dumps(definition, indent=4),
                        )
                        yield File(
                            f"ActionsScripts/{card['name']}.py",
                            self.zipfile.read(
                                f"ActionsScripts/{card['name']}.py").decode(
                                    "utf-8"),
                        )

                    elif card["type"] == ScriptType.JOB.value:
                        try:
                            script_path = f"JobsScripts/{card['name']}.py"
                            script = self.zipfile.read(script_path).decode(
                                "utf-8")
                        except KeyError:
                            script_path = f"JobsScrips/{card['name']}.py"
                            script = self.zipfile.read(script_path).decode(
                                "utf-8")
                        yield File(script_path, script)
                        yield File(
                            f"Jobs/{card['name']}.jobdef",
                            json.dumps(definition, indent=4),
                        )

                    elif card["type"] == ScriptType.CONNECTOR.value:
                        yield File(
                            f"Connectors/{card['name']}.connectordef",
                            json.dumps(definition, indent=4),
                        )
                        yield File(
                            f"ConnectorsScripts/{card['name']}.py",
                            self.zipfile.read(
                                f"ConnectorsScripts/{card['name']}.py").decode(
                                    "utf-8"),
                        )

                    elif card["type"] == ScriptType.MANAGER.value:
                        yield File(
                            f"Managers/{card['name']}.managerdef",
                            json.dumps(definition, indent=4),
                        )
                        yield File(
                            f"Managers/{card['name']}.py",
                            self.zipfile.read(
                                f"Managers/{card['name']}.py").decode("utf-8"),
                        )
        else:
            for file in self.zipfile.namelist():
                content = self.zipfile.read(file)
                if content:  # filters folders
                    yield File(file, content)


class Workflow(Content):

    def __init__(self, raw_data: dict):
        super().__init__()
        self.raw_data = raw_data
        self.raw_data["id"] = 0
        self.raw_data["trigger"]["id"] = 0
        self.name = self.raw_data.get("name")
        self.description = self.raw_data.get("description")
        self.type = WorkflowTypes(self.raw_data.get("playbookType"))
        self.priority = self.raw_data.get("priority")
        self.isDebugMode = self.raw_data.get("isDebugMode", None)
        self.version = self.raw_data.get("version")
        self.trigger = self.raw_data.get("trigger")
        self.steps = self.raw_data.get("steps")
        self.isEnabled = self.raw_data.get("isEnabled")
        self.category = self.raw_data.get("categoryName", "Default")
        self.environments = self.raw_data.get("environments")
        self.modification_time = self.raw_data["modificationTimeUnixTimeInMs"]
        self.overviewTemplates = self.raw_data.get("overviewTemplates", [])

    def __hash__(self):
        """Used to remove duplicates in workflow lists"""
        return hash(self.name)

    def __eq__(self, other):
        """Used to remove duplicates in workflow lists"""
        return self.name == getattr(other, "name", None)

    def generate_readme(self, additional_info: str = None):
        env = JinjaEnvironment()
        env.globals["WorkflowTypes"] = WorkflowTypes
        env.filters.update({
            "trigger_type":
            lambda x: TRIGGER_TYPES.get(x),
            "condition_operator":
            lambda x: CONDITION_OPERATORS.get(x),
            "condition_match_type":
            lambda x: CONDITION_MATCH_TYPES.get(x),
            "split_action_name":
            lambda x: x.split("_", 1)[1] if "_" in x else x,
        })
        template = PLAYBOOK_README_TEMPLATE
        if additional_info:
            template += additional_info
        readme = env.from_string(template)
        self.readme = readme.render(playbook=self.__dict__,
                                    involved_blocks=self.get_involved_blocks())

    def iter_files(self) -> Iterator[File]:
        yield File(self.name + ".json", json.dumps(self.raw_data, indent=4))
        yield File("README.md", self.readme)

    def get_involved_blocks(self):
        return [x for x in self.steps if x.get("type") == 5]


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

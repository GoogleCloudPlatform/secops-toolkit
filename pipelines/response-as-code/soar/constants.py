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

from enum import Enum

#############
# GitSync
#############

INTEGRATION_NAME = "GitSync"
DEFAULT_USERNAME = "None"
DEFAULT_AUTHOR = "GitSync <gitsync@siemplify.co>"
COMMIT_AUTHOR_REGEX = (
    r"[A-Za-z ,.'-]+ <[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}>")

IGNORED_INTEGRATIONS = ["GitSync", "Siemplify", "SiemplifyUtilities"]
IGNORED_JOBS = [
    "Actions Monitor",
    "Connectors Monitor",
    "ETL Monitor",
    "Jobs Monitor",
    "Machine Resource Utilization",
]

AVAILABLE_CONTENT = [
    "Integrations",
    "Playbooks",
    "Jobs",
    "Connectors",
    "Simulated Cases",
    "Integration Instances",
    "Visual Families",
    "Mappings",
    "Environments",
    "Dynamic Parameters",
    "Logo",
    "Case Tags",
    "Case Stages",
    "Case Title Settings",
    "Case Close Reasons",
    "Networks",
    "Domains",
    "Custom Lists",
    "Email Templates",
    "Blacklists",
    "SLA Records",
]

ALL_ENVIRONMENTS_IDENTIFIER = "*"

#############
# Playbooks
#############


class WorkflowTypes(Enum):
    PLAYBOOK = 0
    BLOCK = 1


TRIGGER_TYPES = {
    0: "Vendor Name",
    1: "Tag Name",
    2: "Alert Type",
    3: "Product Name",
    4: "Network Name",
    5: "Entity Details",
    6: "Relation Details",
    7: "Tracking List",
    8: "All",
    9: "Alert Trigger Value",
    10: "Custom Trigger",
    11: "Get Inputs",
}

CONDITION_OPERATORS = {0: "And", 1: "Or"}

CONDITION_MATCH_TYPES = {
    0: "Equals",
    1: "Contains",
    2: "Starts With",
    3: "Greater Than",
    4: "Less Than",
    5: "Not Equals",
    6: "Not Contains",
    7: "Is Empty",
    8: "Is Not Empty",
}

#############
# Integrations
#############


class ScriptType(Enum):
    CONNECTOR = 0
    ACTION = 1
    JOB = 2
    MANAGER = 4


ACTION_PARAMETER_TYPES = {
    0: "String",
    1: "Boolean",
    2: "Playbook Name",
    3: "Users",
    4: "Stages",
    5: "Case Close Reason",
    6: "Close Case Root Cause",
    7: "Priorities",
    10: "Email Content",
    11: "Content",
    12: "Password",
    13: "Entity Type",
    15: "List",
    16: "Code",
}

BASE_PARAMETER_TYPES = {
    0: "Boolean",
    1: "Integer",
    2: "String",
    3: "Password",
    4: "IP",
    8: "Email",
}

#############
# Templates
#############

PLAYBOOKS_ROOT_README = """# Playbooks
|Name|Folder|Description|
|----|------|-----------|
{% for playbook in playbooks -%}
|{{ playbook.name }}|{{ playbook.categoryName }}|{{ (playbook.description or '')|replace('\n', ' ') }}|
{% endfor -%}

"""

PLAYBOOK_README_TEMPLATE = """# {{ playbook.name }}
{{ playbook.description }}\n
\n
**Enabled:** {{ playbook.isEnabled }}\n
**Version:** {{ playbook.version }}\n
**Type:** {{ "Playbook" if playbook.type == WorkflowTypes.PLAYBOOK else "Block" }}\n
**Priority:** {{ playbook.priority }}\n
**Playbook Simulator:** {{ playbook.isDebugMode }}

{% if playbook.trigger.type != 11 %}
### Playbook Trigger
**Trigger Type:** {{ playbook.trigger.type|trigger_type }}\n
**Conditions Operator:** {{ playbook.trigger.logicalOperator|condition_operator }}\n
##### Conditions
|Key|Operator|Value|
|---|--------|-----|
{% for condition in playbook.trigger.conditions -%}
|{{ condition.fieldName }}|{{ condition.matchType|condition_match_type }}|{{ condition.value }}|
{% endfor %}
{% else %}
##### Input Parameters
|Name|Default Value|
|----|-------------|
{% for input in playbook.trigger.conditions -%}
|{{ input.fieldName }}|{{ input.value }}|
{% endfor %}
{% endif %}
### Involved Steps (Unordered)
|Step Name|Description|Integration|Original Action|
|---------|-----------|-----------|---------------|
{% macro describeSteps(steps) -%}
{% for step in steps -%}
{% if step.actionProvider not in ["Flow", "ParallelActionsContainer"] -%}
|{{ step.instanceName }}|{{ step.description|replace('\n', '') }}|{{ step.integration }}|{{ step.actionName|split_action_name }}|
{% elif step.actionProvider == "ParallelActionsContainer" -%}
{{ describeSteps(step.parallelActions) -}}
{% endif -%}
{% endfor -%}
{%- endmacro -%}
{{ describeSteps(playbook.steps) }}
{% if involved_blocks|length > 0 -%}
### Involved Blocks
|Name|Description|
|----|-----------|
{% for block in involved_blocks -%}
|{{ block.name }}|{{ block.description|replace('\n', '') }}|
{% endfor -%}
{% endif -%}

"""

INTEGRATION_README_TEMPLATE = """{% if integration.has_resources -%}
<p align="center"><img src="./Resources/{{ integration.definition.Identifier }}.svg" 
     alt="{{ integration.definition.Identifier }}" width="200"/></p>
{% endif %}
# {{ integration.definition.Identifier }}

{{ integration.definition.Description }}

Python Version - {{ integration.definition.PythonVersion }}
{% if integration.definition.IntegrationProperties -%}
#### Parameters
|Name|Description|IsMandatory|Type|DefaultValue|
|----|-----------|-----------|----|------------|
{% for param in integration.definition.IntegrationProperties -%}
|{{ param.PropertyDisplayName }}|{{ param.PropertyDescription|replace('\n', '') }}|{{ param.IsMandatory }}|{{ param.PropertyType|base_param_type }}|{% if param.PropertyType != 3 %}{{ param.Value }}{% else %}*****{% endif %}|
{% endfor -%}
{% endif %}
{% if integration.dependencies %}
#### Dependencies
| |
|-|
{% for depend in integration.dependencies -%}
|{{ depend | replace("Dependencies/", "") }}|
{% endfor -%}
{% endif %}
{% if integration.actions %}
## Actions
{% for action in integration.actions -%}
#### {{ action.Name }}
{{ action.Description }}
Timeout - {{ action.TimeoutSeconds }} Seconds\n
{% if action.Parameters|length > 0 %}
|Name|Description|IsMandatory|Type|DefaultValue|
|----|-----------|-----------|----|------------|
{% for param in action.Parameters -%}
|{{ param.Name }}|{{ param.Description|replace('\n', '') }}|{{ param.IsMandatory }}|{{ param.Type|action_param_type }}|{% if param.Type != 12 %}{{ param.Value }}{% else %}*****{% endif %}|
{% endfor %}
{% endif %}
{% if action.DynamicResultsMetadata %}
{% for metadata in action.DynamicResultsMetadata -%}
{% if metadata.ResultName == "JsonResult" -%}
##### JSON Results
```json
{{ metadata.ResultExample | replace("\n", "  \n") }}
```
{% endif %}
{% endfor %}
{% endif %}
{% endfor %}
{% endif %}

{% if integration.jobs -%}
## Jobs
{% for job in integration.jobs %}
#### {{ job.Name }}
{{ job.Description }}
{% if job.Parameters|length > 0 %}
|Name|IsMandatory|Type|DefaultValue|
|----|-----------|----|------------|
{% for param in job.Parameters -%}
|{{ param.Name }}|{{ param.IsMandatory }}|{{ param.Type|base_param_type }}|{% if param.Type != 3 %}{{ param.DefaultValue }}{% else %}*****{% endif %}|
{% endfor -%}
{% endif -%}
{% endfor -%}
{% endif %}

{% if integration.connectors %}
## Connectors
{% for connector in integration.connectors -%}
#### {{ connector.Name }}
{{ connector.Description }}
{% if connector.Parameters|length > 0 %}
|Name|Description|IsMandatory|Type|DefaultValue|
|----|-----------|-----------|----|------------|
{% for param in connector.Parameters -%}
|{{ param.Name }}|{{ param.Description|replace('\n', '') }}|{{ param.IsMandatory }}|{{ param.Type|base_param_type }}|{% if param.Type != 3 %}{{ param.DefaultValue }}{% else %}*****{% endif %}|
{% endfor -%}
{% endif %}
{% if connector.Rules %}
##### Allowlist
| |
|-|
{% for rule in connector.Rules -%}
|{{ rule.RuleName }}|
{% endfor %}
{% endif %}
{% endfor %}
{% endif %}

"""

VISUAL_FAMILY_README = """<p align="center">
<img src="./{{ visual_family.name }}.png" 
     alt="{{ visual_family.name }}" width="200"/></p>
     
# {{ visual_family.name }}

### Description
{{ visual_family.description }}

### Rules
|Primary Source|Secondary Source|Third Source|Forth Source|Type|Primary Destination|Secondary Destination|Third Destination|Forth Destination|
|--------------|----------------|------------|------------|----|-------------------|---------------------|-----------------|-----------------|
{% for rule in visual_family.rules -%}
|{{ rule.primarySource }}|{{ rule.secondarySource }}|{{ rule.thirdSource }}|{{ rule.forthSource }}|{{ rule.relationType }}|{{ rule.primaryDestination }}|{{ rule.secondaryDestination }}|{{ rule.thirdDestination }}|{{ rule.forthDestination }}|
{% endfor -%}

"""

MAPPING_README = """# {{ mappings.integrationName }} Mappings
|Product|Event Name|Visual Family|
|-------|----------|-------------|
{% for record in mappings.records -%}
|{{ record.product }}|{{ record.eventName }}|{{ record.familyName }}|
{% endfor -%}

"""

CONNECTOR_README = """# {{ connector.displayName }}
{{ connector.description }}\n

Integration: {{ connector.integration }}\n
Integration Version: {{ connector.integrationVersion }}\n
Device Product Field: {{ connector.deviceProductField }}\n
Event Name Field: {{ connector.eventNameField }}
### Parameters
|Name|Description|Is Mandatory|Value|
|----|-----------|------------|-----|
{% for param in connector.params -%}
{% if param.isDisplayed == True -%}
|{{ param.paramName }}|{{ param.description }}|{{ param.isMandatory }}|{% if param.Type != 3 %}{{ param.paramValue }}{% else %}*****{% endif %}|
{% endif -%}
{% endfor -%}

{% if connector.whiteList %}
### Whitelist
| |
|-|
{% for value in connector.whiteList -%}
|{{ value }}|
{% endfor -%}
{% endif %}

"""

JOB_README = """## {{ job.name }}
{{ job.description }}\n

**Run Interval In Seconds:** {{ job.runIntervalInSeconds }}

{% if job.parameters -%}
#### Parameters
|Name|Type|Is Mandatory|Value|
|----|----|------------|-----|
{% for param in job.parameters -%}
|{{ param.name }}|{{ param.type|base_param_type }}|{{ param.isMandatory }}|{% if param.type != 3 %}{{ param.value }}{% else %}*****{% endif %}|
{% endfor -%}
{% endif %}

"""

ROOT_README = """# GitSync
{% if integrations %}
## Integrations
|Name|Description|
|----|-----------|
{% for integration in integrations -%}
|{{ integration.name }}|{{ integration.description }}|
{% endfor %}
{% endif -%}

{% if connectors %}
## Connectors
|Name|Description|Has Mappings|
|----|-----------|------------|
{% for connector in connectors -%}
|{{ connector.name }}|{{ connector.description }}|{{ connector.hasMappings }}|
{% endfor %}
{% endif -%}

{% if playbooks %}
## Playbooks
|Name|Description|
|----|-----------|
{% for playbook in playbooks -%}
|{{ playbook.name }}|{{ playbook.description }}|
{% endfor %}
{% endif -%}

{% if visualFamilies %}
## Visual Families
|Name|Description|
|----|-----------|
{% for vf in visualFamilies -%}
|{{ vf.name }}|{{ vf.description }}|
{% endfor %}
{% endif -%}

{% if jobs %}
## Jobs
|Name|Description|
|----|-----------|
{% for job in jobs -%}
|{{ job.name }}|{{ job.description }}|
{% endfor %}
{% endif -%}

"""

STEP_TYPE: int = 0

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

#
#   Generate answer to question using mutimodel LLM
#
from google.auth import default
from google import genai
from google.genai import types

# Generation Config with low temperature for reproducible results

safety_settings = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
]


# Generate Answer
def generate_answer(input: str,
                    instructions: str,
                    response_schema,
                    files: list | None = None,
                    markdown: bool = True) -> str:
    """Generate a response to the given input using the LLM."""
    contents = [input]
    if files:
        for f in files:
            contents.append(f)

    config = types.GenerateContentConfig(
        temperature=0.1,
        #max_output_tokens=2048,
        top_k=1,
        #top_p=0.1,
        candidate_count=1,
        response_mime_type="application/json",
        response_schema=response_schema,
        system_instruction=instructions,
        safety_settings=safety_settings)

    # Use Vertex AI backend with default credentials
    # Requires google-auth default credentials and a project defined in the environment,
    # or passing project and location explicitly if needed.
    # In recommender_curated_community.py there are contenthub_project_id and contenthub_location
    import recommender_curated_community
    import os

    # Initialize Google GenAI client for Vertex AI usage
    client = genai.Client(vertexai=True)

    # using the model defined in recommender_curated_community
    model_name = recommender_curated_community.ai_model
    print("Generating response...")
    response = client.models.generate_content(model=model_name,
                                              contents=contents,
                                              config=config)
    print("Response generated")
    return response.text


def generate_curated_rules_recommendation(input_rule, curated_rules):
    """
    Generates GenAI suggestion based on input rule and curated rules

  """
    prompt = f"""
             # Provide Google SecOps curated that cover the security objective of the input rule.

             Expected output:
                 - 'ucid' : provided do not change. identifier of the usecase from the input
                 - 'title': provided do not change. title of rules we want to cover used to determine the security objective
                 - 'description': provided do not change. Description of rules you want to cover used to determine the security objective
                 - 'rule' : content of rules you want to cover used to determine the security objective
                 - 'curated rules': curated rules that potential cover this objective (comma separated),  Extract from contentMetadata value displayName, categories, and from ruleSet value displayName.Notation: ["ruleSet"]["categories"]/["ruleSet"]["displayName"]/["contentMetadata"]["displayName"]
                 - 'curated rules coverage': provide curated rule coverage as: no (missing equivalent), partially (meaning some coverage, like matches tactic and objecitive, but  missing log sources, vendor,  or rule logic), or very good (meaning coverage of security objective)
                 - 'curated rationale': crisp description of why suggested curated rules may cover this objective. Indicate the log data sources needed curated rules

              Using attached documents and the following input:
                 - 'ucid'
                 - 'title'
                 - 'description'
                 - 'rule'

          ## Example 1:
            Input:
              - 'ucid': '5582'
              - 'title': 'SOC - Exchange UM Spawning Unexpected Processes (HAFNIUM)'
              - 'description': 'Identifies abnormal child processes originating from the Exchange Unified Messaging service that deviate from known baselines.'
              -  'rule': '//ucid: 5582\\n//author: Alice Smith\\n//title: SOC - Suspicious Volume Shadow Copy Modification\\n//severity: High\\n//description: Ransomware precursor behavior\\n//technique: T1490\\n//date created: 15/05/2022\\n//date reviewed: 20/11/2023\\n//contributor: \\n\\nSecurityEvent\\n| where TimeGenerated > ago(24h)\\n| where EventID == 4688\\n| where NewProcessName !has \\\"outlook.exe\\\" and NewProcessName !has \\\"msedge.exe\\\"'
            Answer:
              - 'ucid': '5582'
              - 'title': 'SOC - Exchange UM Spawning Unexpected Processes (HAFNIUM)'
              - 'description': 'Identifies abnormal child processes originating from the Exchange Unified Messaging service that deviate from known baselines.'
              - 'curated rules': 'Windows Threats/Initial Access/Hafnium Exchange Web Shell'
              - 'curated rules coverage': 'very good'
              - 'curated rationale': 'Exchange web shell behavior is covered accurately by the SecOps curated rule. Log Data Sources: Carbon Black (CB_EDR), Microsoft Sysmon (WINDOWS_SYSMON), SentinelOne (SENTINEL_EDR), Crowdstrike Falcon (CS_EDR)'


            ## Example 2:
              Input:
              - 'ucid': '7741',
              - 'title' : 'SOC - CLI Directory Traversal - HighValueTargets\"",
              - 'description': "Identifies directory traversal patterns within cmd.exe, which often signals attempts to bypass execution controls, hijack arguments, or access restricted file paths.",
              - 'rule': '//ucid: 7741\\n//author: Bob Johnson\\n//title: SOC - CLI Directory Traversal\\n//severity: Medium\\n//description: Identifies directory traversal patterns within cmd.exe, which often signals attempts to bypass execution controls, hijack arguments, or access restricted file paths.\\n//technique: T1059.003\\n//date created: 10/02/2023\\n//date reviewed: 05/01/2024\\n//contributor: Carol Williams\\n\\nlet AllowedPaths = datatable(AllowedStr: string) [\\n    \\\"Microsoft Visual Studio\\\", \\\"Windows Defender\\\", \\\"\\\\\\\\LoadRunner\\\", \\\"\\\\\\\\LoadGenerator\\\\\\\\\\\",\\n    \\\"\\\\\\\\wwwroot\\\\\\\\AppFlow\\\\\\\\\\\", \\\"DELL\\\\\\\\WMS\\\", \\\"Admin Software\\\", \\\"WebProxyService.exe\\\",\\n    \\\"python\\\", \\\"sdb.exe\\\", \\\"....\\\\\\\\\\\", \\\"app.locale\\\",\\n    \\\"Macro Focus\\\", \\\"Anaconda3\\\", \\\"D2FRQExImportSetup.msi\\\", \\\"DIR /-C /TW /4\\\"\\n];\\nSecurityEvent\\n| where TimeGenerated > ago(24h)\\n| where EventID == 4688\\n| where ParentProcessName has_any (\\\"cmd.exe\\\", \\\"powershell.exe\\\")\\n//eg: ../../../../WINNT/win.ini\\n// /scripts/..%5c../winnt/system32/ cmd.exe?/c+dir+c:\\\\\\n//hxxps://[www.imperva.com/learn/application-security/directory-traversal/](https://www.imperva.com/learn/application-security/directory-traversal/)\\n//\\n// the following regex is specifically for exclusion of dot dot slash notation where there are less than 4 occurrences as they can be considered common place\\n// this is achieved by firstly identifying dot dot slash notations that occur less than 4 times and excluding them\\n//[a-z0-9 =:;@\\\\\\\"*\\\\\\\\.](\\\\\\\\\\\\\\\\|\\\\\\\\/){0,2} --> prefixing the dotdotslash can be a variety of symbols e.g. dirabc\\\\..\\\\..\\\\ or myfolder\\\\+..\\\\..\\\\  etc\\n//(\\\\\\\\.\\\\\\\\.(\\\\\\\\\\\\\\\\|\\\\\\\\/)){1,3} --> matches that actual dotdotslash notation of either ../ or ..\\\\  repeating up to 3 times e.g. will match on ../..\\\\../\\n//(\\\\\\\\\\\\\\\\)?((\\\\\\\\.){0,2})?([a-z0-9 @*]|$ --> after 1-3 dotdotslash notations the string should either terminate or have characters that don\u00e2\u0080\u0099t match ..\\\\ to allow the next regex to pick up 4 iterations of greater\\n| extend ExcludeTraversal = iif(CommandLine matches regex \\\"(?i)[+a-z0-9 =:;@\\\\\\\"*\\\\\\\\.](\\\\\\\\\\\\\\\\|\\\\\\\\/){0,2}(\\\\\\\\.\\\\\\\\.(\\\\\\\\\\\\\\\\|\\\\\\\\/)){1,3}(\\\\\\\\\\\\\\\\)?((\\\\\\\\.){0,2})?([a-z0-9 @*+]|$)\\\", \\\"Matche'

              Answer:
              - 'ucid': '7741',
              - 'title' : 'SOC - CLI Directory Traversal - HighValueTargets\"",
              - 'description': "Identifies directory traversal patterns within cmd.exe, which often signals attempts to bypass execution controls, hijack arguments, or access restricted file paths.",
              - 'curated rules': 'Windows Threats/Mandiant Frontline Threats/Cmd.exe or Powershell.exe Payload Creating Windows Service',
              - 'curated rules coverage': 'partially'
              - 'curated rationale': 'The curated rule detects service creation via command line or PowerShell, tracking how an attacker might deploy a service pointing to a remote payload. It covers the creation mechanism but does not specifically parse the binPath for traversal variables. Log Data Sources: Carbon Black (CB_EDR), Microsoft Sysmon (WINDOWS_SYSMON), SentinelOne (SENTINEL_EDR), Crowdstrike Falcon (CS_EDR).'


                ##Google SecOps curated rules as JSON follow:
                {curated_rules}


                ## Input rule:
                {input_rule}



                """

    instructions = """
                  Analyze the provided input rule title, description and rule definition in oder to find curated detection rules the cover the same security objective.
                  Answer only with curated detection rules the you are provided.
                  Ensure think logically and consider all provided curated detection rules. Ensure not missing rules that may have the similar security objective 
                  Consider that a curated detection rules with indicators of compromise (IOC) based on Applied Threat Intelligence could cover many malware, unusual binaries or hacker tools.
                  Consider that a curated detection rules with a user and entity behavior analytics (UEBA) can cover suspicious, unusual, not normal: actions, scripts executions, connections and other behaviors.
                  Do not change 'ucid', 'title','description'.
                  If you see multiple potential candidates, list them with a comma separated. List maximal 5 curated or 5 community rules per input rule
                  Indicate the log sources needed for curated or community rules in rational as Log Data Sources
                  If you can not find an answer use 'N/A'. 
  
      """

    response_schema = {
        "type": "object",
        "properties": {
            "ucid": {
                "type": "string"
            },
            "title": {
                "type": "string"
            },
            "description": {
                "type": "string"
            },
            "curated rules": {
                "type": "string"
            },
            "curated rules coverage": {
                "type": "string"
            },
            "curated rationale": {
                "type": "string"
            },
        }
    }

    # for debug
    #  with open('prompt.txt', 'w') as f:
    #          f.write(prompt)
    #  print("Prompt written to prompt.txt")

    p = generate_answer(prompt, instructions, response_schema)
    return (p)


# WIP (not used) for spitting curated and community in separate calls
def generate_community_rules_recommendation(input_rule, all_community_rules):
    """
    Generates GenAI suggestion based on input rule
    all community rules are attached to the prompt, since not very large
  """
    prompt = f"""
             # Provide Google SecOps community rules that cover the security objective of the input rule.

             Expected output:
                 - 'ucid' : provided do not change. identifier of the usecase from the input
                 - 'title': provided do not change. title of rules we want to cover used to determine the security objective
                 - 'description': provided do not change. Description of rules you want to cover used to determine the security objective
                 - 'rule' : content of rules you want to cover used to determine the security objective
                 - 'community rules': community rules name that cover the objective and functionality (comma separated). Extract the rule name from the definiton. Notation: def [community_rule_name] {{
                 - 'community rules coverage': provide community rule coverage as: no (missing equivalent), partially (meaning some coverage, like matches tactic and objecitive, but  missing log sources, vendor,  or rule logic), or very good (meaning coverage of security objective)
                 - 'community rationale': crisp description of why suggested community rules may cover this objective. Indicate the log data sources needed for community rules

              Using attached documents and the following input:
                 - 'ucid'
                 - 'title'
                 - 'description'
                 - 'rule'

          ## Example 1:
            Input:
              - 'ucid': '5582'
              - 'title': 'SOC - Exchange UM Spawning Unexpected Processes (HAFNIUM)'
              - 'description': 'Identifies abnormal child processes originating from the Exchange Unified Messaging service that deviate from known baselines.'
              -  'rule': '//ucid: 5582\\n//author: Alice Smith\\n//title: SOC - Suspicious Volume Shadow Copy Modification\\n//severity: High\\n//description: Ransomware precursor behavior\\n//technique: T1490\\n//date created: 15/05/2022\\n//date reviewed: 20/11/2023\\n//contributor: \\n\\nSecurityEvent\\n| where TimeGenerated > ago(24h)\\n| where EventID == 4688\\n| where NewProcessName !has \\\"outlook.exe\\\" and NewProcessName !has \\\"msedge.exe\\\"'
            Answer:
              - 'ucid': '5582'
              - 'title': 'SOC - Exchange UM Spawning Unexpected Processes (HAFNIUM)'
              - 'description': 'Identifies abnormal child processes originating from the Exchange Unified Messaging service that deviate from known baselines.'
              - 'community rules': 'N/A'
              - 'community rules coverage': 'no'
              - 'community rationale': 'N/A'
              
            ## Example 2:
              Input:
              - 'ucid': '7741',
              - 'title' : 'SOC - CLI Directory Traversal - HighValueTargets\"",
              - 'description': "Identifies directory traversal patterns within cmd.exe, which often signals attempts to bypass execution controls, hijack arguments, or access restricted file paths.",
              - 'rule': '//ucid: 7741\\n//author: Bob Johnson\\n//title: SOC - CLI Directory Traversal\\n//severity: Medium\\n//description: Identifies directory traversal patterns within cmd.exe, which often signals attempts to bypass execution controls, hijack arguments, or access restricted file paths.\\n//technique: T1059.003\\n//date created: 10/02/2023\\n//date reviewed: 05/01/2024\\n//contributor: Carol Williams\\n\\nlet AllowedPaths = datatable(AllowedStr: string) [\\n    \\\"Microsoft Visual Studio\\\", \\\"Windows Defender\\\", \\\"\\\\\\\\LoadRunner\\\", \\\"\\\\\\\\LoadGenerator\\\\\\\\\\\",\\n    \\\"\\\\\\\\wwwroot\\\\\\\\AppFlow\\\\\\\\\\\", \\\"DELL\\\\\\\\WMS\\\", \\\"Admin Software\\\", \\\"WebProxyService.exe\\\",\\n    \\\"python\\\", \\\"sdb.exe\\\", \\\"....\\\\\\\\\\\", \\\"app.locale\\\",\\n    \\\"Macro Focus\\\", \\\"Anaconda3\\\", \\\"D2FRQExImportSetup.msi\\\", \\\"DIR /-C /TW /4\\\"\\n];\\nSecurityEvent\\n| where TimeGenerated > ago(24h)\\n| where EventID == 4688\\n| where ParentProcessName has_any (\\\"cmd.exe\\\", \\\"powershell.exe\\\")\\n//eg: ../../../../WINNT/win.ini\\n// /scripts/..%5c../winnt/system32/ cmd.exe?/c+dir+c:\\\\\\n//hxxps://[www.imperva.com/learn/application-security/directory-traversal/](https://www.imperva.com/learn/application-security/directory-traversal/)\\n//\\n// the following regex is specifically for exclusion of dot dot slash notation where there are less than 4 occurrences as they can be considered common place\\n// this is achieved by firstly identifying dot dot slash notations that occur less than 4 times and excluding them\\n//[a-z0-9 =:;@\\\\\\\"*\\\\\\\\.](\\\\\\\\\\\\\\\\|\\\\\\\\/){0,2} --> prefixing the dotdotslash can be a variety of symbols e.g. dirabc\\\\..\\\\..\\\\ or myfolder\\\\+..\\\\..\\\\  etc\\n//(\\\\\\\\.\\\\\\\\.(\\\\\\\\\\\\\\\\|\\\\\\\\/)){1,3} --> matches that actual dotdotslash notation of either ../ or ..\\\\  repeating up to 3 times e.g. will match on ../..\\\\../\\n//(\\\\\\\\\\\\\\\\)?((\\\\\\\\.){0,2})?([a-z0-9 @*]|$ --> after 1-3 dotdotslash notations the string should either terminate or have characters that don\u00e2\u0080\u0099t match ..\\\\ to allow the next regex to pick up 4 iterations of greater\\n| extend ExcludeTraversal = iif(CommandLine matches regex \\\"(?i)[+a-z0-9 =:;@\\\\\\\"*\\\\\\\\.](\\\\\\\\\\\\\\\\|\\\\\\\\/){0,2}(\\\\\\\\.\\\\\\\\.(\\\\\\\\\\\\\\\\|\\\\\\\\/)){1,3}(\\\\\\\\\\\\\\\\)?((\\\\\\\\.){0,2})?([a-z0-9 @*+]|$)\\\", \\\"Matche'

              Answer:
              - 'ucid': '7741',
              - 'title' : 'SOC - CLI Directory Traversal - HighValueTargets\"",
              - 'description': "Identifies directory traversal patterns within cmd.exe, which often signals attempts to bypass execution controls, hijack arguments, or access restricted file paths.",
              - 'community rules': 'mitre_attack_T1570_suspicious_command_psexec,mitre_attack_T1140_encoded_powershell_command'
              - 'community rules coverage': 'partially',
              - 'community rationale': 'The community rule detects the creation of services with suspicious names. While it does not check the binary path for external addresses, it provides coverage for a related persistence technique involving malicious services. Log Data Sources: Microsoft Windows Event Logs.',

                ## Google SecOps Community rules as text follow:
                {all_community_rules}

                ## Input rule:
                {input_rule}



                """

    instructions = """Analyze the provided input rule title, description and rule definition in oder to find  community rules the cover the same security objective.
                    Answer only with community rules the you are provided.
                    Think logicaly and check your answer for all communioty same input objective and follow the format for the output in the notation.
                    Consider that community rules with indicators of compromise (IOC) based on Applied Threat Intelligence could cover many malware or hacker tools.
                    Consider that community rules with a user and entity behavior analytics (UEBA) can cover suspicious actions, executions, connections and other behaviors.
                    Do not change 'ucid', 'title','description'.
                    If you see multiple potential candidates, list them with a comma separated. List maximal 5 community rules per input rule
                    Indicate the log sources needed for  community rules in rational as Log Data Sources
                    If you can not find an answer use 'N/A'. """

    response_schema = {
        "type": "object",
        "properties": {
            "ucid": {
                "type": "string"
            },
            "title": {
                "type": "string"
            },
            "description": {
                "type": "string"
            },
            "community rules": {
                "type": "string"
            },
            "community rules coverage": {
                "type": "string"
            },
            "community rationale": {
                "type": "string"
            }
        }
    }

    # for debug
    #  with open('prompt.txt', 'w') as f:
    #          f.write(prompt)
    #  print("Prompt written to prompt.txt")

    p = generate_answer(prompt, instructions, response_schema)
    return (p)


# helper funation to determine the log source needed for certain customer rule
def find_log_sources_needed(rule, unique_log_types):
    """
    Uses GenAI to determine log type needed for input rule
  """
    prompt = f"""Determine which are the necessary log sources for the following rules.

                The only avalable log sources are: {unique_log_types}

                Example:
                Input:
                  - 'ucid': '1234'
                  - 'title': 'Service Creation referencing External IP Address or URL
                  - 'description': 'Looking for the creation of service that point to external addresses either IP or URL, as this would be very unusual and could be a form of persistence for an attacker to re-establish control or deploy new payloads."
                  -  'rule': // Data Source: Security Events\nEvent\n// Timeframe: Look back over the last 24 hours\n| where TimeGenerated > ago(1d)\n// Filter for relevant PowerShell logging Event IDs (Script Block Logging, Module Logging)\n| where EventID in (4104, 4103, 800)

                 Output:
                  - 'ucid': '1234'
                  - 'title': 'Service Creation referencing External IP Address or URL
                  - 'description': 'Looking for the creation of service that point to external addresses either IP or URL, as this would be very unusual and could be a form of persistence for an attacker to re-establish control or deploy new payloads."
                  -  'rule': // Data Source: Security Events\nEvent\n// Timeframe: Look back over the last 24 hours\n| where TimeGenerated > ago(1d)\n// Filter for relevant PowerShell logging Event IDs (Script Block Logging, Module Logging)\n| where EventID in (4104, 4103, 800)
                  -  log_sources: ['EDR', 'CS-EDR', 'Endpoint']


                Input rules:

                {rule}"""

    instructions = "Analyze the provided rule title, descitpiton and rule definition, used sources, tables to determine the needed log sources. Do not change 'ucid', 'title','description' and 'rule'. Consider overlaps, like for example EDR collects the all log on servers and hosts. Endpoint log type is the same as EDR and CS-EDR and EDR like logs."

    response_schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "ucid": {
                    "type": "string"
                },
                "title": {
                    "type": "string"
                },
                "description": {
                    "type": "string"
                },
                "rule": {
                    "type": "string"
                },
                "log_sources": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                }
            }
        }
    }

    p = generate_answer(prompt, instructions, response_schema)
    return (p)

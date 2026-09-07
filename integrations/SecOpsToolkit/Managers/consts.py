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

import re
from datetime import timedelta

from SiemplifyDataModel import EntityTypes
from TIPCommon.base.action.data_models import EntityTypesEnum
from TIPCommon.types import SingleJson

API_URL = "https://backstory.googleapis.com"
SCOPES = ("https://www.googleapis.com/auth/chronicle-backstory",)
API_LIMIT_ERROR = 429
MAX_RETRIES = 40
LIMIT = 50
DEFAULT_LIMIT = 100
TIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
MAX_LIMIT = 1000
MAX_EVENT_LIMIT = 10000
UDM_QUERY_EVENTS_DEFAULT_LIMIT = 50
UDM_QUERY_EVENTS_MAX_LIMIT = 10000
MAX_HOURS_BACKWARDS = 1
NOW = "now"
INTEGRATION_NAME = "SecOpsToolkit"
INTEGRATION_DISPLAY_NAME = "SecOps Toolkit"
EXECUTE_UDM_QUERY_SCRIPT_NAME = f"{INTEGRATION_DISPLAY_NAME} - Execute UDM Query"
GET_RULE_DETAILS_SCRIPT_NAME = f"{INTEGRATION_NAME} - Get Rule Details"
GET_DETECTION_DETAILS_SCRIPT_NAME = f"{INTEGRATION_NAME} - Get Detection Details"
EXECUTE_RETROHUNT_SCRIPT_NAME = f"{INTEGRATION_NAME} - Execute Retrohunt"
GET_REFERENCE_LISTS_SCRIPT_NAME = f"{INTEGRATION_NAME} - Get Reference Lists"
GET_DATA_TABLES_SCRIPT_NAME: str = f"{INTEGRATION_NAME} - Get Data Tables"
ADD_VALUES_TO_REFERENCE_LIST_SCRIPT_NAME = (
    f"{INTEGRATION_NAME} - Add Values To Reference List"
)
IS_VALUE_IN_REFERENCE_IN_LIST_SCRIPT_NAME = (
    f"{INTEGRATION_NAME} - Is Value In Reference List"
)
REMOVES_VALUES_FROM_REFERENCE_LIST_SCRIPT_NAME = (
    f"{INTEGRATION_NAME} - Remove Values From Reference List"
)
REMOVE_ROWS_FROM_DATA_TABLE_SCRIPT_NAME: str = (
    f"{INTEGRATION_NAME} - Remove Rows From Data Table"
)
ADD_ROWS_TO_DATA_TABLE_SCRIPT_NAME: str = f"{INTEGRATION_NAME} - Add Rows To Data Table"
IS_VALUE_IN_DATA_TABLE_SCRIPT_NAME: str = f"{INTEGRATION_NAME} - Is Value In Data Table"
IS_CIDR_IN_DATA_TABLE_SCRIPT_NAME: str = f"{INTEGRATION_NAME} - Is CIDR In Data Table"
ASK_GEMINI_SCRIPT_NAME: str = f"{INTEGRATION_NAME} - Ask Gemini"
ENRICH_ENTITIES_SCRIPT_NAME: str = f"{INTEGRATION_NAME} - Enrich Entities"
GENERATE_UDM_QUERY_SCRIPT_NAME: str = f"{INTEGRATION_NAME} - Generate UDM Query"
ADD_ENTRY_TO_WATCHLIST_SCRIPT_NAME: str = f"{INTEGRATION_NAME} - Add Entry To Watchlist"

PARAM_ROWS: str = "Rows"
MINIMUM_DATA_TABLE_ROWS_TO_RETURN: int = 1
MAX_DATA_TABLE_ROWS_TO_RETURN: int = 1000
BACKSTORY_API_ROOT_IDENTIFIER: str = "backstory"
ENRICHMENT_PREFIX: str = "SecOpsToolkit_"

# Query Templates
USER_EMAIL_QUERY_KEY: str = "user_email_query"
USER_GENERIC_QUERY_KEY: str = "user_generic_query"

RELATED_ENTITIES_KEY: str = "relatedEntities"
FIRST_SEEN_KEY: str = "firstSeen"
LAST_SEEN_KEY: str = "lastSeen"
ENRICHMENT_FIRST_SEEN_KEY: str = "first_seen"
ENRICHMENT_LAST_SEEN_KEY: str = "last_seen"

IOC_SEVERITIES = {"n/a": 0, "info": 1, "low": 2, "medium": 3, "high": 4}
WHITELIST_FILTER = "whitelist"
BLACKLIST_FILTER = "blacklist"
VENDOR = "Google"
PRODUCT = "Google Chronicle"
GETLIST = "Available Reference Lists"
RA_PRODUCT_NAME = "RISK_SCORE_RULE"

# Sync Data job
SYNC_DATA_SCRIPT_NAME = "Google Chronicle - Sync Data"
DEFAULT_HOURS_BACKWARDS = 24
DEFAULT_FETCH_INTERVAL = 12
MAX_FETCH_LIMIT_FOR_JOB = 1000
TYPE_DELIMITER = "__"
CHRONICLE_USER = "Chronicle SOAR"
JSON_REGEX_PATTERN = "{(?:[^{}]|(?R))*}"
HTTP_STATUS_CODE_REGEX_PATTERN = r"HTTP/\d\.\d\s(\d+)"
HTTP_HEADERS_REGEX_PATTERN = r".+:\s[\w\- //]+"


# Alerts Creator Job
ALERTS_CREATOR_SCRIPT_NAME = "Google Chronicle - Alerts Creator"
ALERTS_CREATOR_BATCH_SIZE = 1000
ALERTS_CREATOR_MAX_ITERATIONS = 1
ALERTS_CREATOR_MINIMUM_SUPPORTED_VERSION = "6.2.30"
ALERTS_CREATOR_MAX_API_RETRIES = 4
ALERTS_CREATOR_RETRY_TIME_DELTA_MS = 500

PRIORITY_SIEMPLIFY_TO_CHRONICLE = {0: 100, 2: 200, 3: 300, 4: 400, 5: 500}

STATUS_SIEMPLIFY_TO_CHRONICLE = {0: 4, 1: 3}  # open  # closed

REASON_SIEMPLIFY_TO_CHRONICLE = {
    0: 2,  # malicious
    1: 1,  # not malicious
    2: 3,  # maintenance
    4: 0,  # unknown
}

SIEMPLIFY_REASON_TO_CHRONICLE_VERDICT = {
    0: 1,  # malicious -> True Positive
    1: 2,  # not malicious -> False Positive
    3: 0,  # maintenance -> Unspecified
    4: 0,  # unknown -> Unspecified
}

SIEMPLIFY_USEFULNESS_TO_CHRONICLE_REPUTATION = {
    0: 0,  # None ->
    1: 2,  # Not Useful
    2: 1,  # Useful
}


ENDPOINTS = {
    "batch_operation": "/batch",
    "udm_search": "v1/events:udmSearch",
    "find_raw_logs": "legacy:legacyFindRawLogs",
    "get_rule_details": "v2/detect/rules/{ruleId}",
    "get_curated_rule_details": "v2/detect/contentHub/featuredContentRules",
    "get_detection_details": "v2/detect/rules/{ruleId}/detections/{detection_id}",
    "list_curated_rule_detections": "v2/detect/curatedRules/{ruleId}/detections",
    "execute_retrohunt": "v2/detect/rules/{ruleId}:runRetrohunt",
    "get_reference_list": "v2/lists/{reference_list_name}?view={view}",
    "get_reference_list_detail": "v2/lists/{reference_list_name}",
    "get_reference_list_all_view": "v2/lists?view={view}",
    "update_reference_list": "v2/lists?update_mask=list.lines",
    "list_alerts": "v1/alert/listalerts",
    "rule_detections": "v2/detect/rules/{ruleId}/detections",
    "stream_detection_alerts": "v2/detect/rules:streamDetectionAlerts",
}

ENDPOINTS_1PLATFORM = {
    "batch_operation": "/batch",
    "udm_search": ":udmSearch",
    "get_rule_details": "rules/{ruleId}",
    "get_curated_rule_details": "contentHub/featuredContentRules",
    "get_detection_details": (
        "legacy:legacyGetDetection?ruleId={ruleId}&detectionId={detection_id}"
    ),
    "list_curated_rule_detections": (
        "legacy:legacySearchCuratedDetections?ruleId={ruleId}"
    ),
    "execute_retrohunt": "rules/{ruleId}/retrohunts",
    "get_reference_list": "referenceLists/{reference_list_name}?view={view}",
    "get_reference_list_all_view": "referenceLists?view={view}",
    "update_reference_list": (
        "referenceLists/{reference_list_name}?update_mask=entries"
    ),
    # not supported -> https://buganizer.corp.google.com/issues/407712702
    "list_alerts": "legacy:legacySearchAlerts",
    "rule_detections": "legacy:legacySearchDetections?ruleId={ruleId}",
    "stream_detection_alerts": "legacy:legacyStreamDetectionAlerts",
    "list_iocs": "legacy:legacySearchEnterpriseWideIoCs",
    "list_events": "legacy:legacySearchAssetEvents",
    "artifact_ioc_details": "legacy:legacySearchArtifactIoCDetails",
    "list_assets": "legacy:legacySearchEnterpriseWideIoCs",
    "create_alert": "legacy:legacyCreateSoarAlert",
    "update_alert": "legacy:legacyUpdateAlert",
    "create_case": "legacy:legacyCreateOrUpdateCase",
    "get_data_table": "dataTables/{data_table}",
    "list_rows": "dataTables/{data_table}/dataTableRows",
    "delete_rows": "dataTables/{data_table}/dataTableRows/{data_table_row}",
    "create_data_table": "dataTables",
    "list_data_tables": "dataTables",
    "add_row": "dataTables/{data_table}/dataTableRows:bulkCreate",
    "replace_rows": "dataTables/{data_table}/dataTableRows:bulkReplace",
    "opt_in": "users/me/preferenceSet?updateMask=ui_preferences.enable_duet_ai_chat",
    "create_conversation": "users/me/conversations",
    "execute_prompt": "users/me/conversations/{conversation_id}/messages",
    "delete_conversation": "users/me/conversations/{conversation_id}",
    "summarize_entities_from_query": ":summarizeEntitiesFromQuery",
    "summarize_entity": ":summarizeEntity",
    "find_related_entities": ":findRelatedEntities",
    "generate_udm_query": ":translateUdmQuery",
    "watchlists": "watchlists",
    "add_entry_to_watchlist": "watchlists/{watchlist_id}/entities:batchAdd",
    "find_raw_logs": "legacy:legacyFindRawLogs",
}

MAX_DATA_TABLE_PAGE_SIZE: int = 1000

SIMILARITY_BY_NAME_AND_PRODUCT = "Alert Name, Alert Type and Product"
SIMILARITY_BY_NAME = "Alert Name and Alert Type"
SIMILARITY_BY_PRODUCT = "Product"
SIMILARITY_BY_ASSETS = "Only IOCs/Assets"

SEVERITY_REGEX: str = r'severity\s*=\s*"(.*?)"'
RESULT_REGEX: str = r'\$result\s*=\s*"(.*?)"'

ONLY_EVENTS = "Only Events"
ONLY_STATISTICS = "Only Statistics"
EVENTS_AND_STATISTICS = "Events + Statistics"

EVENT_TYPES = [
    "EVENTTYPE_UNSPECIFIED",
    "PROCESS_UNCATEGORIZED",
    "PROCESS_LAUNCH",
    "PROCESS_INJECTION",
    "PROCESS_PRIVILEGE_ESCALATION",
    "PROCESS_TERMINATION",
    "PROCESS_OPEN",
    "PROCESS_MODULE_LOAD",
    "REGISTRY_UNCATEGORIZED",
    "REGISTRY_CREATION",
    "REGISTRY_MODIFICATION",
    "REGISTRY_DELETION",
    "SETTING_UNCATEGORIZED",
    "SETTING_CREATION",
    "SETTING_MODIFICATION",
    "SETTING_DELETION",
    "MUTEX_UNCATEGORIZED",
    "MUTEX_CREATION",
    "FILE_UNCATEGORIZED",
    "FILE_CREATION",
    "FILE_DELETION",
    "FILE_MODIFICATION",
    "FILE_READ",
    "FILE_COPY",
    "FILE_OPEN",
    "FILE_MOVE",
    "FILE_SYNC",
    "USER_UNCATEGORIZED",
    "USER_LOGIN",
    "USER_LOGOUT",
    "USER_CREATION",
    "USER_CHANGE_PASSWORD",
    "USER_CHANGE_PERMISSIONS",
    "USER_STATS",
    "USER_BADGE_IN",
    "USER_DELETION",
    "USER_RESOURCE_CREATION",
    "USER_RESOURCE_UPDATE_CONTENT",
    "USER_RESOURCE_UPDATE_PERMISSIONS",
    "USER_COMMUNICATION",
    "USER_RESOURCE_ACCESS",
    "USER_RESOURCE_DELETION",
    "GROUP_UNCATEGORIZED",
    "GROUP_CREATION",
    "GROUP_DELETION",
    "GROUP_MODIFICATION",
    "EMAIL_UNCATEGORIZED",
    "EMAIL_TRANSACTION",
    "EMAIL_URL_CLICK",
    "NETWORK_UNCATEGORIZED",
    "NETWORK_FLOW",
    "NETWORK_CONNECTION",
    "NETWORK_FTP",
    "NETWORK_DHCP",
    "NETWORK_DNS",
    "NETWORK_HTTP",
    "NETWORK_SMTP",
    "STATUS_UNCATEGORIZED",
    "STATUS_HEARTBEAT",
    "STATUS_STARTUP",
    "STATUS_SHUTDOWN",
    "STATUS_UPDATE",
    "SCAN_UNCATEGORIZED",
    "SCAN_FILE",
    "SCAN_PROCESS_BEHAVIORS",
    "SCAN_PROCESS",
    "SCAN_HOST",
    "SCAN_VULN_HOST",
    "SCAN_VULN_NETWORK",
    "SCAN_NETWORK",
    "SCHEDULED_TASK_UNCATEGORIZED",
    "SCHEDULED_TASK_CREATION",
    "SCHEDULED_TASK_DELETION",
    "SCHEDULED_TASK_ENABLE",
    "SCHEDULED_TASK_DISABLE",
    "SCHEDULED_TASK_MODIFICATION",
    "SYSTEM_AUDIT_LOG_UNCATEGORIZED",
    "SYSTEM_AUDIT_LOG_WIPE",
    "SERVICE_UNSPECIFIED",
    "SERVICE_CREATION",
    "SERVICE_DELETION",
    "SERVICE_START",
    "SERVICE_STOP",
    "SERVICE_MODIFICATION",
    "GENERIC_EVENT",
    "RESOURCE_CREATION",
    "RESOURCE_DELETION",
    "RESOURCE_PERMISSIONS_CHANGE",
    "RESOURCE_READ",
    "RESOURCE_WRITTEN",
    "ANALYST_UPDATE_VERDICT",
    "ANALYST_UPDATE_REPUTATION",
    "ANALYST_UPDATE_SEVERITY_SCORE",
    "ANALYST_UPDATE_STATUS",
    "ANALYST_ADD_COMMENT",
]

TIMEFRAME_MAPPING = {
    "Last Hour": {"hours": 1},
    "Last 6 Hours": {"hours": 6},
    "Last 24 Hours": {"hours": 24},
    "Last Week": "last_week",
    "Last Month": "last_month",
    "Custom": "custom",
    "Alert Time Till Now": "Alert Time Till Now",
    "5 Minutes Around Alert Time": "5 Minutes Around Alert Time",
    "30 Minutes Around Alert Time": "30 Minutes Around Alert Time",
    "1 Hour Around Alert Time": "1 Hour Around Alert Time",
}

CONFIDENCE_TO_INT_MAPPING = {"high": 90, "medium": 60, "low": 30}

INT_TO_SEVERITY_MAPPING = {0: "N/A", 1: "Info", 2: "Low", 3: "Medium", 4: "High"}

RULE_ALERT_TYPE = "RULE"
EXTERNAL_ALERT_TYPE = "EXTERNAL"
IOC_ALERT_TYPE = "IOC"

HOURS_BACKWARDS_STRING = "Max Hours Backwards"
SHA256_LENGTH = 64
MD5_LENGTH = 32
SHA1_LENGTH = 40

EXECUTE_RETROHUNT_TIME_FRAME_DDL_VALUES = [
    "Last Hour",
    "Last 6 Hours",
    "Last 24 Hours",
    "Last Week",
    "Last Month",
    "Alert Time Till Now",
    "5 Minutes Around Alert Time",
    "30 Minutes Around Alert Time",
    "1 Hour Around Alert Time",
    "Custom",
]

EXECUTE_RETROHUNT_TIME_FRAME_DEFAULT_VALUE = "Last Hour"

GET_REFERENCE_LIST_FILTER_KEY_DDL_VALUES = [
    "Select One",
    "Name",
    "Content Type",
    "Description",
]

GET_REFERENCE_LIST_FILTER_LOGIC_DDL_VALUES = ["Equal", "Contains"]

GET_REFERENCE_FILTER_KEY_CONTENT_TYPE = "contentType"
GET_REFERENCE_FILTER_KEY_SYNTAX_TYPE = "syntaxType"
GET_REFERENCE_FILTER_KEY_DISPLAY_NAME = "displayName"
GET_REFERENCE_LIST_FILTER_KEY_DEFAULT_VALUE = "Select One"
GET_REFERENCE_LIST_FILTER_LOGIC_EQUAL = "Equal"
GET_REFERENCE_LIST_CONTENT_TYPE = "CONTENT_TYPE_DEFAULT_STRING"
GET_REFERENCE_LIST_FILTER_LOGIC_CONTAINS = "Contains"
GET_REFERENCE_LIST_FILTER_KEY_NAME = "name"

GET_DATA_TABLES_FILTER_KEY_DDL_VALUES: list[str] = [
    "Select One",
    "Name",
    "Description",
]
GET_DATA_TABLES_FILTER_KEY_DEFAULT_VALUE: str = "Select One"
GET_DATA_TABLES_FILTER_KEY_NAME: str = "Name"
GET_DATA_TABLES_FILTER_KEY_DESCRIPTION: str = "Description"
GET_DATA_TABLES_FILTER_LOGIC_DDL_VALUES: list[str] = ["Equal", "Contains"]
GET_DATA_TABLES_FILTER_LOGIC_EQUAL: str = "Equal"
GET_DATA_TABLES_FILTER_LOGIC_CONTAINS: str = "Contains"
DEFAULT_MAX_DATA_TABLES_TO_RETURN: int = 100
DEFAULT_MAX_DATA_TABLE_ROWS_TO_RETURN: int = 1000
MAX_DATA_TABLES: int = 1000
MAX_DATA_TABLE_ROWS: int = 1000
MIN_DATA_TABLES: int = 1
MIN_DATA_TABLE_ROWS: int = 1


class HashArtifactTypes:
    MD5 = "artifact.hash_md5"
    SHA1 = "artifact.hash_sha1"
    SHA256 = "artifact.hash_sha256"


HASH_VALUE_TYPE_MAPPING = {
    HashArtifactTypes.MD5: "HASH_MD5",
    HashArtifactTypes.SHA1: "HASH_SHA1",
    HashArtifactTypes.SHA256: "HASH_SHA256",
}

NOT_ASSIGNED = "n/a"

# Unified Alerts Connector
UNIFIED_CONNECTOR_DEVICE_VENDOR = "Google Chronicle"
UNIFIED_CONNECTOR_DEVICE_PRODUCT = "Google Chronicle"
UNIFIED_CONNECTOR_CONNECTOR_NAME = "Google Chronicle - Chronicle Alerts Connector"
UNIFIED_CONNECTOR_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
UNIFIED_CONNECTOR_DEFAULT_LIMIT = 100
UNIFIED_CONNECTOR_DEFAULT_MAX_LIMIT = 50
UNIFIED_CONNECTOR_DEFAULT_TIME_FRAME = 1
UNIFIED_CONNECTOR_MAX_TIME_FRAME = 167
UNIFIED_CONNECTOR_MAX_SAFE_FETCH_LIMIT = 1000
UNIFIED_CONNECTOR_IS_TIMEOUT_DB_KEY = "is_timeout"
UNIFIED_CONNECTOR_DYNAMIC_FETCH_LIMIT_DB_KEY = "dynamic_fetch_limit"
UNIFIED_CONNECTOR_MIN_DYNAMIC_FETCH_LIMIT = 10
UNIFIED_CONNECTOR_DUPLICATE_MIN_SCANNED = 100
UNIFIED_CONNECTOR_DUPLICATE_RATIO_THRESHOLD = 0.9
MAX_ALLOWED_INGESTION_DELAY_MINUTES = 7
EXTERNAL_ALERT_ASSET_TYPE = "asset"
EXTERNAL_ALERT_USER_TYPE = "user"
DEFAULT_PADDING_PERIOD = 1
MAX_PADDING_PERIOD = 12
MAX_DETECTION_STREAM_BATCH_SIZE = 50
MIN_DETECTION_STREAM_TIMEOUT = 10
STRING_PREFIX_SEPARATOR = "_"
SCC_ENTERPRISE_PRODUCT_NAME = "SCCE"

ALERT_TYPES = {"rule": "rule", "external": "external", "ioc": "ioc"}

ALERT_TYPE_NAMES = {
    ALERT_TYPES.get("rule"): "RULE",
    ALERT_TYPES.get("external"): "EXTERNAL",
    ALERT_TYPES.get("ioc"): "IOC",
}

NESTED_KEYS_DELIMITER = ">"
EXTERNAL_MULTIPLE_VALUES_NESTED_KEYS = [
    "event>principal>ip",
    "event>principal>nat_ip",
    "event>principal>mac",
    "event>principal>asset>ip",
    "event>principal>asset>nat_ip",
    "event>principal>asset>mac",
    "event>src>ip",
    "event>src>nat_ip",
    "event>src>mac",
    "event>src>asset>ip",
    "event>src>asset>nat_ip",
    "event>src>asset>mac",
    "event>target>ip",
    "event>target>nat_ip",
    "event>target>mac",
    "event>target>asset>ip",
    "event>target>asset>nat_ip",
    "event>target>asset>mac",
    "event>observer>ip",
    "event>observer>nat_ip",
    "event>observer>mac",
    "event>observer>asset>ip",
    "event>observer>asset>nat_ip",
    "event>observer>asset>mac",
    "event>about>ip",
    "event>about>nat_ip",
    "event>about>mac",
    "event>about>asset>ip",
    "event>about>asset>nat_ip",
    "event>about>asset>mac",
    "event>network>email>to",
    "event>principal>user>emailAddresses",
    "event>src>user>emailAddresses",
    "event>target>user>emailAddresses",
    "event>observer>user>emailAddresses",
    "event>about>user>emailAddresses",
]

RULE_MULTIPLE_VALUES_NESTED_KEYS = [
    "event>principal>ip",
    "event>principal>nat_ip",
    "event>principal>mac",
    "event>principal>asset>ip",
    "event>principal>asset>nat_ip",
    "event>principal>asset>mac",
    "event>principal>user>emailAddresses",
    "event>src>ip",
    "event>src>nat_ip",
    "event>src>mac",
    "event>src>asset>ip",
    "event>src>asset>nat_ip",
    "event>src>asset>mac",
    "event>src>user>emailAddresses",
    "event>target>ip",
    "event>target>nat_ip",
    "event>target>mac",
    "event>target>asset>ip",
    "event>target>asset>nat_ip",
    "event>target>asset>mac",
    "event>target>user>emailAddresses",
    "event>observer>ip",
    "event>observer>nat_ip",
    "event>observer>mac",
    "event>observer>asset>ip",
    "event>observer>asset>nat_ip",
    "event>observer>asset>mac",
    "event>observer>user>emailAddresses",
    "event>about>ip",
    "event>about>nat_ip",
    "event>about>mac",
    "event>about>asset>ip",
    "event>about>asset>nat_ip",
    "event>about>asset>mac",
    "event>about>user>emailAddresses",
    "event>network>email>to",
]

SIEMPLIFY_SEVERITIES = {
    "info": -1,
    "low": 40,
    "medium": 60,
    "high": 80,
    "critical": 100,
    "informational": -1,
    "error": 40,
}

GCTI_ALERT_SEVERITY_MAPPING = {
    "UNKNOWN_SEVERITY": -1,
    "INFORMATIONAL": -1,
    "ERROR": 40,
    "LOW": 40,
    "MEDIUM": 60,
    "HIGH": 80,
    "CRITICAL": 100,
}

FALLBACK_SEVERITY_VALUES = ["info", "low", "medium", "high", "critical"]

FILTER_TYPE_DELIMITER = "."
FILTER_VALUES_DELIMITER = ","
FILTER_LOGIC = {"and": "and", "or": "or"}
SUPPORTED_OPERATORS = [">=", "<=", "!=", "=", ">", "<"]
MULTIPLE_VALUES_SUPPORTED_OPERATORS = {
    "=": FILTER_LOGIC.get("or"),
    "!=": FILTER_LOGIC.get("and"),
}

ALERT_TYPES_SUPPORTED_FILTERS = {
    ALERT_TYPES.get("rule"): {
        "severity": {
            "response_key": "siemplify_severity",
            "operators": ["=", "!=", ">", "<", ">=", "<="],
            "possible_values": [
                "low",
                "medium",
                "high",
                "critical",
                "informational",
                "info",
                "error",
            ],
            "values_mapping": SIEMPLIFY_SEVERITIES,
        },
        "ruleName": {
            "response_key": "name",
            "operators": ["=", "!="],
            "possible_values": None,
        },
        "ruleID": {
            "response_key": "rule_id",
            "operators": ["=", "!="],
            "possible_values": None,
        },
        "alertState": {
            "response_key": "alert_state",
            "operators": ["=", "!="],
            "possible_values": ["alerting", "not alerting"],
        },
        "ruleType": {
            "response_key": "rule_class",
            "operators": ["=", "!="],
            "possible_values": ["curated", "custom"],
        },
        "ruleLabels": {
            "response_key": "rule_labels",
            "operators": ["=", "!="],
            "possible_values": None,
        },
    },
    ALERT_TYPES.get("external"): {
        "productName": {
            "response_key": "product_name",
            "operators": ["=", "!="],
            "possible_values": None,
        },
        "productEventType": {
            "response_key": "product_event_type",
            "operators": ["=", "!="],
            "possible_values": None,
        },
        "threatName": {
            "response_key": "name",
            "operators": ["=", "!="],
            "possible_values": None,
        },
        "severity": {
            "response_key": "unified_siemplify_severity",
            "operators": ["=", "!=", ">", "<", ">=", "<="],
            "possible_values": [
                "low",
                "medium",
                "high",
                "critical",
                "informational",
                "error",
            ],
            "values_mapping": SIEMPLIFY_SEVERITIES,
        },
        "type": {
            "response_key": "alert_type",
            "operators": ["=", "!="],
            "possible_values": ["asset", "user"],
        },
    },
    ALERT_TYPES.get("ioc"): {
        "rawSeverity": {
            "response_key": "highest_siemplify_severity",
            "operators": ["=", "!=", ">", "<", ">=", "<="],
            "possible_values": ["low", "medium", "high", "critical", "info"],
            "values_mapping": SIEMPLIFY_SEVERITIES,
        },
        "intRawConfidenceScore": {
            "response_key": "average_confidence_score",
            "operators": ["=", "!=", ">", "<", ">=", "<="],
            "possible_values": [str(item) for item in range(101)],
            "transformer": int,
        },
        "normalizedConfidenceScore": {
            "response_key": "average_normalized_confidence_score",
            "operators": ["=", "!=", ">", "<", ">=", "<="],
            "possible_values": ["low", "medium", "high", "critical"],
            "values_mapping": SIEMPLIFY_SEVERITIES,
        },
    },
}

ENTITY_TYPES_MAPPING = {
    "DestinationURL": ["target.url"],
    "FILEHASH": {
        "MD5": ["target.file.md5"],
        "SHA1": ["target.file.sha1"],
        "SHA256": ["target.file.sha256"],
    },
    "ADDRESS": [
        "principal.ip",
        "principal.asset.ip",
        "src.ip",
        "src.asset.ip",
        "target.ip",
        "target.asset.ip",
    ],
    "HOSTNAME": [
        "principal.hostname",
        "src.hostname",
        "target.hostname",
        "target.asset.hostname",
    ],
    "PROCESS": {
        "INT": [
            "target.process.pid",
            "target.process.parent_pid",
            "target.process.parent_process.pid",
        ],
        "STR": [
            "target.process.file.full_path",
            "target.process.parent_process.file.full_path",
        ],
    },
    "EMAILSUBJECT": ["network.email.subject"],
    "USERUNIQNAME": {
        "EMAIL": [
            "network.email.from",
            "network.email.to",
            "network.email.cc",
            "network.email.bcc",
        ],
        "USERNAME": [
            "principal.user.user_display_name",
            "src.user.user_display_name",
            "target.user.user_display_name",
        ],
    },
    "MAC_ADDRESS": [
        "src.mac",
        "about.mac",
        "target.mac",
        "observer.mac",
        "principal.mac",
        "src.asset.mac",
        "about.asset.mac",
        "intermediary.mac",
        "target.asset.mac",
        "observer.asset.mac",
        "principal.asset.mac",
    ],
}

ACTIVITY_TYPES_MAPPING = {
    "NETWORK": [
        "NETWORK_UNCATEGORIZED",
        "NETWORK_FLOW",
        "NETWORK_CONNECTION",
        "NETWORK_FTP",
        "NETWORK_DHCP",
        "NETWORK_DNS",
        "NETWORK_HTTP",
        "NETWORK_SMTP",
    ],
    "USER": [
        "USER_UNCATEGORIZED",
        "USER_LOGIN",
        "USER_LOGOUT",
        "USER_CREATION",
        "USER_CHANGE_PASSWORD",
        "USER_CHANGE_PERMISSIONS",
        "USER_STATS",
        "USER_BADGE_IN",
        "USER_DELETION",
        "USER_RESOURCE_CREATION",
        "USER_RESOURCE_UPDATE_CONTENT",
        "USER_RESOURCE_UPDATE_PERMISSIONS",
        "USER_COMMUNICATION",
        "USER_RESOURCE_ACCESS",
        "USER_RESOURCE_DELETION",
    ],
    "PROCESS": [
        "PROCESS_UNCATEGORIZED",
        "PROCESS_LAUNCH",
        "PROCESS_INJECTION",
        "PROCESS_PRIVILEGE_ESCALATION",
        "PROCESS_TERMINATION",
        "PROCESS_OPEN",
        "PROCESS_MODULE_LOAD",
    ],
    "FILE": [
        "FILE_UNCATEGORIZED",
        "FILE_CREATION",
        "FILE_DELETION",
        "FILE_MODIFICATION",
        "FILE_READ",
        "FILE_COPY",
        "FILE_OPEN",
        "FILE_MOVE",
        "FILE_SYNC",
    ],
    "REGISTRY": [
        "REGISTRY_UNCATEGORIZED",
        "REGISTRY_CREATION",
        "REGISTRY_MODIFICATION",
        "REGISTRY_DELETION",
    ],
    "EMAIL": ["EMAIL_UNCATEGORIZED", "EMAIL_TRANSACTION", "EMAIL_URL_CLICK"],
    "GROUP": [
        "GROUP_UNCATEGORIZED",
        "GROUP_CREATION",
        "GROUP_DELETION",
        "GROUP_MODIFICATION",
    ],
    "SETTING": [
        "SETTING_UNCATEGORIZED",
        "SETTING_CREATION",
        "SETTING_MODIFICATION",
        "SETTING_DELETION",
    ],
    "MUTEX": ["MUTEX_UNCATEGORIZED", "MUTEX_CREATION"],
    "STATUS": [
        "STATUS_UNCATEGORIZED",
        "STATUS_HEARTBEAT",
        "STATUS_STARTUP",
        "STATUS_SHUTDOWN",
        "STATUS_UPDATE",
    ],
    "SCAN": [
        "SCAN_UNCATEGORIZED",
        "SCAN_FILE",
        "SCAN_PROCESS_BEHAVIORS",
        "SCAN_PROCESS",
        "SCAN_HOST",
        "SCAN_VULN_HOST",
        "SCAN_VULN_NETWORK",
        "SCAN_NETWORK",
    ],
    "SCHEDULED TASK": [
        "SCHEDULED_TASK_UNCATEGORIZED",
        "SCHEDULED_TASK_CREATION",
        "SCHEDULED_TASK_DELETION",
        "SCHEDULED_TASK_ENABLE",
        "SCHEDULED_TASK_DISABLE",
        "SCHEDULED_TASK_MODIFICATION",
    ],
    "SYSTEM AUDIT": ["SYSTEM_AUDIT_LOG_UNCATEGORIZED", "SYSTEM_AUDIT_LOG_WIPE"],
    "SERVICE": [
        "SERVICE_UNSPECIFIED",
        "SERVICE_CREATION",
        "SERVICE_DELETION",
        "SERVICE_START",
        "SERVICE_STOP",
        "SERVICE_MODIFICATION",
    ],
    "RESOURCE": [
        "RESOURCE_CREATION",
        "RESOURCE_DELETION",
        "RESOURCE_PERMISSIONS_CHANGE",
        "RESOURCE_READ",
        "RESOURCE_WRITTEN",
    ],
    "ANALYST": [
        "ANALYST_UPDATE_VERDICT",
        "ANALYST_UPDATE_REPUTATION",
        "ANALYST_UPDATE_SEVERITY_SCORE",
        "ANALYST_UPDATE_STATUS",
        "ANALYST_ADD_COMMENT",
    ],
    "ALL": [],
}

RULE_ALERT_PREFIX = "GChronicle"
SCRIPT_EXECUTION_MARGIN = 10
ZERO = 0

CURATED_RULE_ID_PREFIX = "ur_"
OUTCOME_UPDATED_DETECTION_KEY = "update_detection"
OAUTH_SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)
REFERENCE_LIST_VIEW_FULL = "REFERENCE_LIST_VIEW_FULL"
REFERENCE_LIST_VIEW_BASIC = "REFERENCE_LIST_VIEW_BASIC"
FILTER_KEY_MAPPING = {
    "Content Type": GET_REFERENCE_FILTER_KEY_SYNTAX_TYPE,
    "Name": GET_REFERENCE_FILTER_KEY_DISPLAY_NAME,
}
RESOURCE_REGEX_PATTERN = r"([^/]+)/([^/]+)"
LIST_ALERTS_LIMIT = 10000

LIST_EVENTS_URI: str = (
    "assetResults?assetIdentifier={entity_identifier}&assetType="
    "{entity_type}&selectedList=AssetViewTimeline"
)

LIST_ASSETS_IP_URI: str = (
    "destinationIpResults?{entity_type}={entity_identifier}&"
    "selectedList=IpViewDistinctAssets"
)
LIST_ASSETS_HASH_URI: str = (
    "hashResults?{entity_type}={entity_identifier}&selectedList=HashViewDistinctAssets"
)
LIST_ASSETS_DOMAIN_URI: str = (
    "domainResults?{entity_type}={entity_identifier}&"
    "selectedList=DomainViewDistinctAssets"
)

ENTITY_TYPE_TO_ASSET_TYPE_MAPPING = {
    "ADDRESS": "ip",
    "DestinationURL": "domain",
    "artifact.hash_md5": "md5",
    "artifact.hash_sha1": "sha1",
    "artifact.hash_sha256": "sha256",
}

LIST_EVENTS_ENTITY_TYPE_TO_ASSET_TYPE_MAPPING = {
    "ADDRESS": "ipAddress",
    "HOSTNAME": "hostname",
    "MACADDRESS": "mac",
}

LOOKUP_SIMILAR_ALERTS_URI = "enterpriseInsights"
MB_IN_BYTES = 1_048_576
FIVE_MINUTES_IN_SECONDS = 300

EMAIL_REGEX: re.Pattern = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)
INVALID_KEY_CHARACTERS_REGEX: re.Pattern = re.compile(r"[^a-zA-Z0-9_]")

ENTITY_QUERY_TEMPLATES: SingleJson = {
    str(EntityTypes.FILEHASH).lower(): (
        'principal.file.sha256 = "{value}" OR '
        'principal.process.file.sha256 = "{value}" OR '
        'target.file.sha256 = "{value}" OR '
        'target.process.file.sha256 = "{value}" OR '
        'security_result.about.file.sha256 = "{value}" OR '
        'src.file.sha256 = "{value}" OR '
        'src.process.file.sha256 = "{value}" nocase'
    ),
    str(EntityTypes.ADDRESS).lower(): 'ip = "{value}" nocase',
    str(EntityTypes.HOSTNAME).lower(): 'hostname = "{value}" nocase',
    str(EntityTypes.MACADDRESS).lower(): 'principal.mac = "{value}" nocase',
    str(EntityTypes.DOMAIN).lower(): (
        'target.hostname = "{value}" OR '
        "target.hostname = /.*{value}/ OR "
        "network.dns.questions.name = /.*{value}/ nocase"
    ),
    str(EntityTypes.URL).lower(): (
        'target.hostname = "{value}" OR '
        "target.hostname = /.*{value}/ OR "
        "network.dns.questions.name = /.*{value}/ nocase"
    ),
    "user_generic_query": 'user = "{value}" nocase',
    "user_email_query": (
        'principal.user.email_addresses = "{value}" OR '
        'target.user.email_addresses = "{value}" OR '
        'network.email.from = "{value}" OR '
        'network.email.to = "{value}" nocase'
    ),
}

NAMESPACE_FILTER_ENTITY_TYPES: SingleJson = {
    EntityTypes.ADDRESS,
    EntityTypes.HOSTNAME,
    EntityTypes.USER,
}

ENRICHED_ORDERED_KEYS: list[str] = [
    "name",
    "metadata",
    "entity",
    "metric",
    "alertCounts",
    "timeline",
    "prevalenceResult",
    "fileMetadataAndProperties",
    "relatedEntities",
]

ENRICHMENT_KEYS: list[str] = [
    "entity",
    "metric",
    "alertCounts",
    "prevalenceResult",
    "relatedEntities",
]

SUPPORTED_TYPE_VALUES: list[str] = [
    EntityTypesEnum.USER,
    EntityTypesEnum.FILE_HASH,
    EntityTypesEnum.ADDRESS,
    EntityTypesEnum.HOST_NAME,
    EntityTypesEnum.MAC_ADDRESS,
    EntityTypesEnum.DOMAIN,
    EntityTypesEnum.URL,
]

TIME_DELTAS: SingleJson = {
    "Last Hour": timedelta(hours=1),
    "Last 6 Hours": timedelta(hours=6),
    "Last 24 Hours": timedelta(hours=24),
    "Last Week": timedelta(weeks=1),
}

KEYS_TO_PRESERVE: list[str] = ["alertCounts", "timeline", "prevalenceResult"]
SERVICE_ACCOUNT_EMAIL_KEY: str = "service_account_email"
PERMISSION_ERROR_MESSAGE: str = "the caller does not have permission"
IMPERSONATION_ERROR_MESSAGE: str = "unable to acquire impersonated credentials"
ENTITY_TYPE_MAPPING: dict[str, callable] = {
    "ASSET_IP_ADDRESS": lambda v: {"asset": {"ip": v}},
    "MAC": lambda v: {"asset": {"mac": v}},
    "HOSTNAME": lambda v: {"asset": {"hostname": v}},
    "PRODUCT_SPECIFIC_ID": lambda v: {"asset": {"productObjectId": v}},
    "USERNAME": lambda v: {"user": {"userid": v}},
    "EMAIL": lambda v: {"user": {"emailAddresses": v}},
    "EMPLOYEE_ID": lambda v: {"user": {"employeeId": v}},
    "WINDOWS_SID": lambda v: {"user": {"windowsSid": v}},
    "PRODUCT_OBJECT_ID": lambda v: {"user": {"productObjectId": v}},
}

INCLUDE_RAW_LOG_DATA_PARAM: str = "Include Raw Log Data"
TIME_FRAME_PARAM: str = "Time Frame"
CUSTOM: str = "Custom"
LAST_HOUR = "Last Hour"
MAX_RESPONSE_BYTE_SIZE: int = 300000000

RAW_LOG_SPEC_KEYS: list[str] = [
    "agent_id",
    "aggregate_id",
    "data_domains",
    "description",
    "device",
    "template_instance_id",
    "timestamp",
    "user_name",
]

EVENT_ID_PATTERN = re.compile(r"events/([^/]+)$")

MIN_RESULTS_TO_RETURN: int = 1
MAX_RESULTS_TO_RETURN: int = 10000

TIME_RANGE_MINUTES: int = 1
DETECTION_TIME_FORMAT: str = "%Y-%m-%dT%H:%M:%SZ"
NS_DATETIME_PATTERN: re.Pattern = re.compile(r"\.\d{9}Z")

REFERENCE_LIST_FOUND_STRING: str = "found"
REFERENCE_LIST_NOT_FOUND_STRING: str = "not found"

CIDR_COLUMN_TYPE: str = "CIDR"

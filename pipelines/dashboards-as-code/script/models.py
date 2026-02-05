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

from enum import Enum
from typing import List, Optional, Any


class DashboardOperation(Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"


class DashboardAccess(Enum):
    DASHBOARD_ACCESS_UNSPECIFIED = "DASHBOARD_ACCESS_UNSPECIFIED"
    DASHBOARD_PRIVATE = "DASHBOARD_PRIVATE"
    DASHBOARD_PUBLIC = "DASHBOARD_PUBLIC"


class DashboardType(Enum):
    DASHBOARD_TYPE_UNSPECIFIED = "DASHBOARD_TYPE_UNSPECIFIED"
    CURATED = "CURATED"
    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"
    CUSTOM = "CUSTOM"
    MARKETPLACE = "MARKETPLACE"


class DataSource(Enum):
    DATA_SOURCE_UNSPECIFIED = "DATA_SOURCE_UNSPECIFIED"
    UDM = "UDM"
    RULE_DETECTIONS = "RULE_DETECTIONS"
    GLOBAL = "GLOBAL"
    INGESTION_METRICS = "INGESTION_METRICS"


class FilterOperatorAndValues:

    def __init__(self, operator: str, values: List[Any]):
        self.operator = operator
        self.values = values

    @staticmethod
    def from_dict(data: dict):
        return FilterOperatorAndValues(operator=data.get("operator"),
                                       values=data.get("values", []))

    def to_dict(self):
        return {"operator": self.operator, "values": self.values}


class ChartLayout:

    def __init__(self, span_x: int, span_y: int, start_x: int, start_y: int):
        self.span_x = span_x
        self.span_y = span_y
        self.start_x = start_x
        self.start_y = start_y

    @staticmethod
    def from_dict(data: dict):
        return ChartLayout(span_x=data.get("spanX"),
                           span_y=data.get("spanY"),
                           start_x=data.get("startX"),
                           start_y=data.get("startY"))

    def to_dict(self):
        return {
            "spanX": self.span_x,
            "spanY": self.span_y,
            "startX": self.start_x,
            "startY": self.start_y
        }


class ChartConfig:

    def __init__(self, dashboard_chart: str, chart_layout: ChartLayout,
                 filters_ids: List[str]):
        self.dashboard_chart = dashboard_chart
        self.chart_layout = chart_layout
        self.filters_ids = filters_ids

    @staticmethod
    def from_dict(data: dict):
        return ChartConfig(dashboard_chart=data.get("dashboardChart"),
                           chart_layout=ChartLayout.from_dict(
                               data.get("chartLayout", {})),
                           filters_ids=data.get("filtersIds", []))

    def to_dict(self):
        return {
            "dashboardChart": self.dashboard_chart,
            "chartLayout": self.chart_layout.to_dict(),
            "filtersIds": self.filters_ids
        }


class DashboardFilter:

    def __init__(
            self, id: str, data_source: DataSource, field_path: str,
            filter_operator_and_field_values: List[FilterOperatorAndValues],
            display_name: str, chart_ids: List[str],
            is_standard_time_range_filter: bool, is_mandatory: bool,
            is_standard_time_range_filter_enabled: bool):
        self.id = id
        self.data_source = data_source
        self.field_path = field_path
        self.filter_operator_and_field_values = filter_operator_and_field_values
        self.display_name = display_name
        self.chart_ids = chart_ids
        self.is_standard_time_range_filter = is_standard_time_range_filter
        self.is_mandatory = is_mandatory
        self.is_standard_time_range_filter_enabled = is_standard_time_range_filter_enabled

    @staticmethod
    def from_dict(data: dict):
        return DashboardFilter(
            id=data.get("id"),
            data_source=DataSource(data.get("dataSource"))
            if data.get("dataSource") else None,
            field_path=data.get("fieldPath"),
            filter_operator_and_field_values=[
                FilterOperatorAndValues.from_dict(item)
                for item in data.get("filterOperatorAndFieldValues", [])
            ],
            display_name=data.get("displayName"),
            chart_ids=data.get("chartIds", []),
            is_standard_time_range_filter=data.get(
                "isStandardTimeRangeFilter"),
            is_mandatory=data.get("isMandatory"),
            is_standard_time_range_filter_enabled=data.get(
                "isStandardTimeRangeFilterEnabled"))

    def to_dict(self):
        return {
            "id":
            self.id,
            "dataSource":
            self.data_source.value if self.data_source else None,
            "fieldPath":
            self.field_path,
            "filterOperatorAndFieldValues":
            [item.to_dict() for item in self.filter_operator_and_field_values],
            "displayName":
            self.display_name,
            "chartIds":
            self.chart_ids,
            "isStandardTimeRangeFilter":
            self.is_standard_time_range_filter,
            "isMandatory":
            self.is_mandatory,
            "isStandardTimeRangeFilterEnabled":
            self.is_standard_time_range_filter_enabled
        }


class DashboardDefinition:

    def __init__(self, filters: List[DashboardFilter], fingerprint: str,
                 charts: List[ChartConfig]):
        self.filters = filters
        self.fingerprint = fingerprint
        self.charts = charts

    @staticmethod
    def from_dict(data: dict):
        return DashboardDefinition(filters=[
            DashboardFilter.from_dict(item)
            for item in data.get("filters", [])
        ],
                                   fingerprint=data.get("fingerprint"),
                                   charts=[
                                       ChartConfig.from_dict(item)
                                       for item in data.get("charts", [])
                                   ])

    def to_dict(self):
        return {
            "filters": [item.to_dict() for item in self.filters],
            "fingerprint": self.fingerprint,
            "charts": [item.to_dict() for item in self.charts]
        }


class DashboardUserData:

    def __init__(self, last_viewed_time: str, is_pinned: bool):
        self.last_viewed_time = last_viewed_time
        self.is_pinned = is_pinned

    @staticmethod
    def from_dict(data: dict):
        return DashboardUserData(last_viewed_time=data.get("lastViewedTime"),
                                 is_pinned=data.get("isPinned"))

    def to_dict(self):
        return {
            "lastViewedTime": self.last_viewed_time,
            "isPinned": self.is_pinned
        }


class NativeDashboard:

    def __init__(self, name: str, display_name: str, description: str,
                 definition: DashboardDefinition, type: DashboardType,
                 create_time: str, update_time: str, create_user_id: str,
                 update_user_id: str, dashboard_user_data: DashboardUserData,
                 etag: str, access: DashboardAccess):
        self.name = name
        self.display_name = display_name
        self.description = description
        self.definition = definition
        self.type = type
        self.create_time = create_time
        self.update_time = update_time
        self.create_user_id = create_user_id
        self.update_user_id = update_user_id
        self.dashboard_user_data = dashboard_user_data
        self.etag = etag
        self.access = access

    @staticmethod
    def from_dict(data: dict):
        return NativeDashboard(
            name=data.get("name"),
            display_name=data.get("displayName"),
            description=data.get("description"),
            definition=DashboardDefinition.from_dict(data.get(
                "definition", {})),
            type=DashboardType(data.get("type")) if data.get("type") else None,
            create_time=data.get("createTime"),
            update_time=data.get("updateTime"),
            create_user_id=data.get("createUserId"),
            update_user_id=data.get("updateUserId"),
            dashboard_user_data=DashboardUserData.from_dict(
                data.get("dashboardUserData", {})),
            etag=data.get("etag"),
            access=DashboardAccess(data.get("access"))
            if data.get("access") else None)

    def to_dict(self):
        return {
            "name": self.name,
            "displayName": self.display_name,
            "description": self.description,
            "definition": self.definition.to_dict(),
            "type": self.type.value if self.type else None,
            "createTime": self.create_time,
            "updateTime": self.update_time,
            "createUserId": self.create_user_id,
            "updateUserId": self.update_user_id,
            "dashboardUserData": self.dashboard_user_data.to_dict(),
            "etag": self.etag,
            "access": self.access.value if self.access else None
        }

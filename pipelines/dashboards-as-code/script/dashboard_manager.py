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

import json
import logging
from pathlib import Path
from typing import List, Dict
from secops import SecOpsClient
from secops.exceptions import APIError
from config import SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION
from models import NativeDashboard, DashboardType, DashboardOperation

LOGGER = logging.getLogger(__name__)


class DashboardManager:
    """Manages the lifecycle of SecOps parsers and extensions."""

    def __init__(self):
        if not all([SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION]):
            raise APIError(
                "Missing SecOps env vars: SECOPS_CUSTOMER_ID, SECOPS_PROJECT_ID, SECOPS_REGION."
            )
        try:
            self.client = SecOpsClient().chronicle(
                customer_id=SECOPS_CUSTOMER_ID,
                project_id=SECOPS_PROJECT_ID,
                region=SECOPS_REGION)
            LOGGER.info("SecOps client initialized successfully.")
        except Exception as e:
            raise APIError(f"Failed to initialize SecOps client: {e}") from e

    def export_dashboard(self, dashboard_names: List[str]):
        return self.client.export_dashboard(dashboard_names=dashboard_names)

    def list_remote_dashboards(self, include_charts: bool = True) -> Dict:
        """
        Fetches all dashboards and their charts from the Google SecOps API.
    
        Returns:
            dict: A dictionary where keys are dashboard names and values are dicts
                  containing the dashboard details and a list of its charts.
        """
        try:
            all_dashboards_raw = self.client.list_dashboards(page_size=1000)
            dashboards = {}

            if "nativeDashboards" not in all_dashboards_raw:
                LOGGER.info("No remote dashboards found.")
                return dashboards

            all_dashboards = [
                NativeDashboard.from_dict(d)
                for d in all_dashboards_raw["nativeDashboards"]
            ]

            for dashboard in all_dashboards:
                if not dashboard.display_name:
                    LOGGER.warning(
                        f"Skipping a dashboard with no displayName: {dashboard.name}"
                    )
                    continue

                if dashboard.type == DashboardType.CURATED:
                    LOGGER.debug(
                        f"Skipping a curated dashboard: {dashboard.name}")
                    continue

                LOGGER.info(
                    f"Fetching details for dashboard: {dashboard.display_name}"
                )
                full_dashboard_dict = self.client.get_dashboard(
                    dashboard.name.split("/")[-1], "FULL")
                full_dashboard = NativeDashboard.from_dict(full_dashboard_dict)

                if include_charts:
                    charts_list = []
                    if full_dashboard.definition and full_dashboard.definition.charts:
                        for chart_ref in full_dashboard.definition.charts:
                            if chart_ref.dashboard_chart:
                                chart_id = chart_ref.dashboard_chart.split(
                                    "/")[-1]
                                try:
                                    chart_details = self.client.get_chart(
                                        chart_id)
                                    charts_list.append(chart_details)
                                    LOGGER.debug(
                                        f"Successfully fetched chart {chart_id} for dashboard {dashboard.display_name}"
                                    )
                                except Exception as e:
                                    LOGGER.error(
                                        f"Failed to fetch chart {chart_id} for dashboard {dashboard.display_name}: {e}"
                                    )

                    dashboards[dashboard.display_name] = {
                        "dashboard": full_dashboard,
                        "dashboardCharts": charts_list
                    }
                else:
                    dashboards[dashboard.display_name] = full_dashboard
            return dashboards

        except Exception as e:
            LOGGER.error(
                f"Error: Could not connect to Google SecOps API or list dashboards."
            )
            LOGGER.error(f"Details: {e}")
            return {}

    def get_local_dashboards_with_charts(self,
                                         path: str = "./dashboards") -> Dict:
        dashboard_dir = Path(path)
        if not dashboard_dir.is_dir():
            LOGGER.error(f"Error: Directory '{path}' not found.")
            return {}

        local_dashboards = {}
        for json_file in dashboard_dir.glob("*.json"):
            try:
                with open(json_file, "r") as f:
                    config = json.load(f)
                    dashboard_def = config["dashboards"][0]
                    dashboard_name = dashboard_def["dashboard"]["displayName"]
                    charts = dashboard_def.get("dashboardCharts", [])
                    queries = dashboard_def.get("dashboardQueries", [])

                    chart_layouts = {}
                    if "definition" in dashboard_def.get(
                            "dashboard",
                        {}) and "charts" in dashboard_def["dashboard"].get(
                            "definition", {}):
                        for layout_info in dashboard_def["dashboard"][
                                "definition"]["charts"]:
                            if "dashboardChart" in layout_info and "chartLayout" in layout_info:
                                chart_layouts[layout_info[
                                    "dashboardChart"]] = layout_info[
                                        "chartLayout"]

                    local_dashboards[dashboard_name] = {
                        "dashboard": dashboard_def["dashboard"],
                        "dashboardCharts": charts,
                        "dashboardQueries": queries
                    }
            except (json.JSONDecodeError, KeyError) as e:
                LOGGER.error(f"Error parsing {json_file.name}: {e}")
            except Exception as e:
                LOGGER.error(
                    f"An unexpected error occurred with file {json_file.name}: {e}"
                )

        return local_dashboards

    def are_charts_different(self, local_chart: Dict,
                             remote_chart: Dict) -> bool:
        local_copy = local_chart.copy()
        remote_copy = remote_chart.copy()

        ignore_fields = [
            "name", "etag", "chartDatasource", "nativeDashboard", "createTime",
            "updateTime", "createUserId", "updateUserId"
        ]

        for field in ignore_fields:
            local_copy.pop(field, None)
            remote_copy.pop(field, None)

        return local_copy != remote_copy

    def compute_dashboard_operations(self):
        local_dashboards = self.get_local_dashboards_with_charts()
        if not local_dashboards:
            LOGGER.info("No local dashboards found. Exiting.")
            return
        LOGGER.info(f"\nFound {len(local_dashboards)} local dashboard(s):")
        for name in sorted(local_dashboards.keys()):
            LOGGER.info(f"  - {name}")

        # 2. Get remote dashboards with their chart definitions
        LOGGER.info("\nFetching remote dashboards from Google SecOps...")
        remote_dashboards = self.list_remote_dashboards()
        if not remote_dashboards:
            LOGGER.info("Could not retrieve any remote dashboards.")
        else:
            LOGGER.info(f"Found {len(remote_dashboards)} remote dashboard(s).")

        # 3. Compare and plan
        dashboards_ops = {}

        for name, local_data in local_dashboards.items():
            if name not in remote_dashboards:
                dashboards_ops[name] = {
                    "operation": DashboardOperation.CREATE,
                    "dashboard": local_dashboards[name]
                }
            else:
                # Dashboard exists, compare charts
                remote_data = remote_dashboards[name]
                local_charts_map = {
                    c['displayName']: c
                    for c in local_data.get("dashboardCharts", [])
                }
                remote_charts_map = {
                    c['displayName']: c
                    for c in remote_data.get("dashboardCharts", [])
                }

                charts_to_add = [
                    c for name, c in local_charts_map.items()
                    if name not in remote_charts_map
                ]
                charts_to_delete = [
                    c for name, c in remote_charts_map.items()
                    if name not in local_charts_map
                ]
                charts_to_update = []

                for chart_name, local_chart in local_charts_map.items():
                    if chart_name in remote_charts_map:
                        remote_chart = remote_charts_map[chart_name]
                        if self.are_charts_different(local_chart,
                                                     remote_chart):
                            # We need the remote chart's ID to update it.
                            update_payload = local_chart.copy()
                            update_payload['name'] = remote_chart['name']
                            charts_to_update.append(update_payload)

                if charts_to_add or charts_to_delete or charts_to_update:
                    dashboards_ops[name] = {
                        "operation":
                        DashboardOperation.UPDATE,
                        "dashboard_id":
                        remote_data['dashboard'].name.split('/')[-1],
                        "dashboard":
                        local_dashboards[name]
                    }

        return dashboards_ops

    def plan(self):
        dashboards_ops = self.compute_dashboard_operations()

        LOGGER.info("\n" + "=" * 40)
        LOGGER.info("📊 Comparison Result")
        LOGGER.info("=" * 40)

        if not dashboards_ops:
            LOGGER.info("No dashboard need to be created or updated.")
            return {}

        else:
            LOGGER.info(
                f"Following dashboards requires updates/creation: {dashboards_ops.keys()}."
            )
            return dashboards_ops

    def apply(self):
        dashboards_ops = self.compute_dashboard_operations()

        LOGGER.info("\n" + "=" * 40)
        LOGGER.info("📊 Apply Operations")
        LOGGER.info("=" * 40)

        if not dashboards_ops:
            LOGGER.info("No dashboard need to be created or updated.")
            return {}

        else:
            for name, config in dashboards_ops.items():
                if config["operation"] == DashboardOperation.CREATE:
                    LOGGER.info(f"Creating dashboard '{name}'...")
                    response = self.client.import_dashboard(
                        dashboard=config["dashboard"])
                    LOGGER.info(f"Response '{response}'")
                    LOGGER.info(f"'{name}' created successfully.")

                elif config["operation"] == DashboardOperation.UPDATE:
                    LOGGER.info(f"  -> Updating dashboard '{name}':")
                    dashboard_id = config["dashboard_id"]

                    self.client.delete_dashboard(dashboard_id=dashboard_id)

                    self.client.import_dashboard(dashboard=config["dashboard"])
                else:
                    raise Exception(
                        "Dashboard operations it not CREATE or UPDATE, this is inconsistent."
                    )

            return dashboards_ops

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

import os
import sys
import json
import click
import logging
from pathlib import Path
from dotenv import load_dotenv
from dashboard_manager import DashboardManager
from utils import generate_pr_comment_output, setup_logging

load_dotenv()

setup_logging()
LOGGER = logging.getLogger(__name__)


@click.group()
@click.pass_context
def cli(ctx):
    try:
        # Store the manager instance in the Click context object
        ctx.obj = DashboardManager()
    except Exception as e:
        LOGGER.critical(f"Fatal Initialization Error: {e}", exc_info=True)
        sys.exit(1)


@cli.command(name="plan")
@click.pass_obj
def plan(manager: DashboardManager):
    LOGGER.info("🚀 Starting Dashboard as Code deployment plan...")
    plan = {}
    has_errors = False
    try:
        LOGGER.info("--- Planning Dashboards deployment ---")
        plan = manager.plan()
    except Exception as e:
        LOGGER.error(f"A pipeline error occurred: {e}", exc_info=True)
        has_errors = True
    finally:
        generate_pr_comment_output(plan, has_errors)
        if has_errors:
            sys.exit(1)

    LOGGER.info("\n" + "=" * 40)


@cli.command(name="apply")
@click.pass_obj
def apply(manager: DashboardManager):
    LOGGER.info("🚀 Starting Dashboard as Code deployment ...")
    result = {}
    submitted = []
    has_errors = False
    try:
        LOGGER.info("Deploy Dashboards")
        result = manager.apply()
    except Exception as e:
        LOGGER.error(f"A pipeline error occurred: {e}", exc_info=True)
        has_errors = True
    finally:
        generate_pr_comment_output(result, has_errors)
        if has_errors:
            sys.exit(1)

    LOGGER.info("\n" + "=" * 40)


@cli.command(name="download")
@click.option('--dashboard',
              type=str,
              help="Name of Custom Dashboard to download.")
@click.pass_obj
def download(manager: DashboardManager, dashboard: str):
    print("🚀 Starting dashboard download...")
    remote_dashboards = manager.list_remote_dashboards(include_charts=False)
    if not remote_dashboards:
        print("No remote dashboards found. Exiting.")
        return

    dashboard_dir = Path("./dashboards")
    dashboard_dir.mkdir(exist_ok=True)

    for name, data in remote_dashboards.items():
        if name == dashboard:
            file_path = dashboard_dir / f"{dashboard.replace(' ','_').lower()}.json"
            print(f"  -> Saving dashboard '{name}' to {file_path}...")
            with open(file_path, "w") as f:
                dashboard_export = manager.export_dashboard(
                    dashboard_names=[data.name])
                json.dump(dashboard_export["inlineDestination"], f, indent=2)
    print("\n✅ Download complete.")


if __name__ == "__main__":
    cli()

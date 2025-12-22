# coding=utf-8
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

import binascii
import json
import os
import click
import logging
import google.cloud.logging
from datetime import date, timedelta, datetime
from secops import SecOpsClient
from dotenv import load_dotenv
from dateutil.relativedelta import relativedelta

load_dotenv()

client = google.cloud.logging.Client()
client.setup_logging()

LOGGER = logging.getLogger('secops')
logging.basicConfig(
    level=logging.DEBUG if os.environ.get('DEBUG') else logging.INFO,
    format='[%(levelname)-8s] - %(asctime)s - %(message)s')
logging.root.setLevel(logging.DEBUG)

SECOPS_REGION = os.environ.get("SECOPS_REGION")
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT")
GCS_BUCKET = os.environ.get("GCS_BUCKET")
SECOPS_CUSTOMER_ID = os.environ.get("SECOPS_CUSTOMER_ID")
SECOPS_PROJECT_ID = os.environ.get("SECOPS_PROJECT_ID")
MONTHS_TO_LOOK_BACK = os.environ.get("MONTHS_TO_LOOK_BACK", 11)

HUNDRED_TERABYTES = 99000000000000


def trigger_export(export_start_datetime: str, export_end_datetime: str,
                   log_types: str):
    """
    Trigger secops export using Data Export API for a specific date
    :param secops_source_sa_key_secret_path:
    :param secops_export_bucket:
    :param secops_target_project_id:
    :param log_types:
    :param export_end_datetime:
    :param export_start_datetime:
    :param date: datetime (as string) with DD-MM-YYYY format
    :return:
  """

    client = SecOpsClient()
    chronicle = client.chronicle(customer_id=SECOPS_CUSTOMER_ID,
                                 project_id=SECOPS_PROJECT_ID,
                                 region=SECOPS_REGION)

    export_ids = []

    start_time, end_time = (datetime.strptime(export_start_datetime,
                                              "%Y-%m-%dT%H:%M:%SZ"),
                            datetime.strptime(export_end_datetime,
                                              "%Y-%m-%dT%H:%M:%SZ"))

    gcs_bucket = f"projects/{GCP_PROJECT_ID}/buckets/{GCS_BUCKET}"

    try:
        if log_types is None or log_types == "":
            export_response = chronicle.create_data_export(
                start_time=start_time,
                end_time=end_time,
                gcs_bucket=gcs_bucket,
                export_all_logs=True)
            LOGGER.info(export_response)
            export_id = export_response["name"].split("/")[-1]
            LOGGER.info(f"Export request response: {export_response}")
            if "estimatedVolume" in export_response and int(
                    export_response["estimatedVolume"]) > HUNDRED_TERABYTES:
                raise SystemExit(
                    f'Export with ID: {export_id} might result in more than 100TB of data. This might result in data loss, please check this.'
                )
            export_ids.append(export_id)
            LOGGER.info(f"Triggered export with ID: {export_id}")
        else:
            export_response = chronicle.create_data_export(
                start_time=start_time,
                end_time=end_time,
                gcs_bucket=gcs_bucket,
                log_types=log_types.split(","))
            export_id = export_response["name"].split("/")[-1]
            LOGGER.info(f"Export request response: {export_response}")
            if "estimatedVolume" in export_response and int(
                    export_response["estimatedVolume"]) > HUNDRED_TERABYTES:
                raise SystemExit(
                    f'Export with ID: {export_id} might result in more than 100TB of data. This might result in data loss, please check this.'
                )
            LOGGER.info(f"Triggered export with ID: {export_id}")
    except Exception as e:
        LOGGER.error(f"Error during export': {e}")
        raise SystemExit(f'Error during secops export: {e}')

    return export_ids


def check_monthly_export(export_month: str, log_types: str):
    """
  Trigger DLP Job and setup secops feeds to ingest data from output bucket.
  :param month: month for which data exports should be checked
  :return:
  """
    try:
        export_month_date = datetime.strptime(export_month, "%Y-%m")
    except ValueError:
        raise SystemExit(
            f'Invalid export month format: {export_month}. Please use YYYY-MM.'
        )

    client = SecOpsClient()
    chronicle = client.chronicle(customer_id=SECOPS_CUSTOMER_ID,
                                 project_id=SECOPS_PROJECT_ID,
                                 region=SECOPS_REGION)
    create_time = datetime(export_month_date.year, export_month_date.month, 1,
                           0, 0, 0)
    create_time_str = create_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    data_export_response = chronicle.list_data_export(
        filters=f"(createTime >= \"{create_time_str}\")", page_size=1000)

    failed_jobs = False
    in_progress_jobs = False
    expected_log_types = set(log_types.split(","))

    for export in data_export_response["dataExports"]:
        data_export = chronicle.get_data_export(
            data_export_id=export["name"].split("/")[-1])
        LOGGER.info(f"Export response: {data_export}.")
        if "dataExportStatus" in data_export and export["dataExportStatus"][
                "stage"] == "FINISHED_SUCCESS":
            if "exportedVolume" in export and int(
                    export["exportedVolume"]) > HUNDRED_TERABYTES:
                raise SystemExit(
                    f'Export with ID: {export["name"].split("/")[-1]} exported more than 100TB of data. This might result in data loss, please check this.'
                )
            exported_log_types = []
            for log_type in data_export["includeLogTypes"]:
                exported_log_types.append(log_type.split("/")[-1])
            expected_log_types = expected_log_types - set(exported_log_types)
        elif "dataExportStatus" in data_export and (
                export["dataExportStatus"]["stage"] == "IN_QUEUE"
                or export["dataExportStatus"]["stage"] == "PROCESSING"):
            in_progress_jobs = True
        elif "dataExportStatus" in data_export and export["dataExportStatus"][
                "stage"] == "FINISHED_FAILURE":
            failed_jobs = True
        else:
            raise SystemExit(
                f'Inconsistent state for export with ID: {export["name"].split("/")[-1]}'
            )

    if len(expected_log_types) == 0:
        LOGGER.info(
            "Exports finished successfully for all log types in request.")
    else:
        if in_progress_jobs:
            raise SystemExit(f'Data Export still in progress')
        elif failed_jobs:
            raise SystemExit(f'Data Export still in progress')
        else:
            raise SystemExit(
                f'Error with checking data export status, no jobs in progress or failures and still {expected_log_types} log types left.'
            )


def trigger_export_action(export_month: str, log_types: str):
    """
    Trigger secops export for a specific month
    :param export_month: month for which data should be exported
    :param log_types: comma separated list of log types to export
    :return:
    """
    if export_month:
        try:
            export_month_date = datetime.strptime(export_month, "%Y-%m")
        except ValueError:
            raise SystemExit(
                f'Invalid export month format: {export_month}. Please use YYYY-MM.'
            )
    else:
        today = date.today()
        export_month_date = today - relativedelta(months=MONTHS_TO_LOOK_BACK)

    start_date = export_month_date.replace(day=1)
    end_date = start_date + relativedelta(months=1) - timedelta(days=1)

    start_datetime_str = start_date.strftime("%Y-%m-%dT00:00:00Z")
    end_datetime_str = end_date.strftime("%Y-%m-%dT23:59:59Z")

    return trigger_export(export_start_datetime=start_datetime_str,
                          export_end_datetime=end_datetime_str,
                          log_types=log_types)


def main(request):
    """
    Entry point for Cloud Function triggered by HTTP request.
    :param request: payload of HTTP request triggering cloud function
    :return:
    """
    debug = os.environ.get('DEBUG')
    logging.basicConfig(level=logging.INFO)
    LOGGER.info('processing http payload')
    try:
        payload = json.loads(request.data)
    except (binascii.Error, json.JSONDecodeError) as e:
        raise SystemExit(f'Invalid payload: {e.args[0]}.')
    action = payload.get('ACTION')
    log_types = payload.get('LOG_TYPES', None)

    match action:
        case "TRIGGER-EXPORT":
            export_month = payload.get('EXPORT_MONTH', None)
            trigger_export_action(export_month=export_month,
                                  log_types=log_types)
        case "CHECK-MONTHLY-EXPORT":
            export_month = payload.get('EXPORT_MONTH',
                                       date.today().strftime("%Y-%m"))
            check_monthly_export(export_month=export_month,
                                 log_types=log_types)
        case _:
            return "Action must be either 'TRIGGER-EXPORT', 'CHECK-MONTHLY-EXPORT'"

    return "Success."


@click.command()
@click.option(
    '--export-month',
    '-m',
    required=False,
    type=str,
    help=
    'Month for secops export in YYYY-MM format. If not provided, the previous month will be used.'
)
@click.option('--log-type', type=str, multiple=True)
@click.option('--action',
              type=click.Choice(['TRIGGER-EXPORT', 'CHECK-MONTHLY-EXPORT']),
              required=True)
@click.option('--debug',
              is_flag=True,
              default=False,
              help='Turn on debug logging.')
def main_cli(export_month, log_type: list, action: str, debug=False):
    """
    CLI entry point.
    :param export_month: month for secops export
    :param debug: whether to enable debug logs
    :return:
    """
    logging.basicConfig(level=logging.INFO if not debug else logging.DEBUG)
    match action:
        case "TRIGGER-EXPORT":
            trigger_export_action(export_month=export_month,
                                  log_types=','.join(log_type))
        case "CHECK-MONTHLY-EXPORT":
            if not export_month:
                export_month = datetime.now().strftime("%Y-%m")
            check_monthly_export(export_month=export_month,
                                 log_types=','.join(log_type))
        case _:
            return "Action must be either 'TRIGGER-EXPORT', 'ANONYMIZE-DATA' or 'IMPORT-DATA'"

    return "Success."


if __name__ == '__main__':
    main_cli()

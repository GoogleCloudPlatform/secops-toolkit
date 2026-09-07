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

from SiemplifyJob import SiemplifyJob
from SiemplifyUtils import output_handler
from TIPCommon.extraction import extract_action_param, extract_configuration_param
from SecOpsToolkitManager import SecOpsToolkitManager
from consts import INTEGRATION_NAME
from datetime import datetime, timedelta, timezone


class JobParametersParser:
    """This class parses the input parameters of the job."""

    def __init__(self, siemplify_):
        self.api_root = extract_configuration_param(
            siemplify_,
            provider_name=INTEGRATION_NAME,
            param_name="API Root",
            is_mandatory=True,
            print_value=True,
        )
        self.creds = extract_configuration_param(
            siemplify_,
            provider_name=INTEGRATION_NAME,
            param_name="User's Service Account",
            is_mandatory=False,
            print_value=False,
        )
        self.verify_ssl = extract_configuration_param(
            siemplify_,
            provider_name=INTEGRATION_NAME,
            param_name="Verify SSL",
            default_value=True,
            input_type=bool,
            print_value=True,
        )
        self.workload_identity_email = extract_configuration_param(
            siemplify_,
            provider_name=INTEGRATION_NAME,
            param_name="Workload Identity Email",
            print_value=False,
        )

        self.search_id = JobParametersParser.parse_search_id(siemplify_)
        self.window_size = JobParametersParser.parse_window_size(siemplify_)

    @staticmethod
    def parse_search_id(siemplify):
        return extract_action_param(
            siemplify=siemplify,
            param_name="Search ID",
            is_mandatory=True,
            print_value=True,
        )

    @staticmethod
    def parse_window_size(siemplify):
        return extract_action_param(
            siemplify=siemplify,
            param_name="Window Size",
            input_type=int,
            is_mandatory=False,
            default_value=720,
            print_value=False,
        )


@output_handler
def main():
    siemplify = SiemplifyJob()
    siemplify.script_name = "ScheduledQueryJob"
    siemplify.LOGGER.info("--------------- JOB STARTED ---------------")

    try:
        job_parameters_parser = JobParametersParser(siemplify)

        manager = SecOpsToolkitManager.create_manager_instance(
            user_service_account=job_parameters_parser.creds,
            workload_identity_email=job_parameters_parser.workload_identity_email,
            chronicle_soar=siemplify,
            api_root=job_parameters_parser.api_root,
            verify_ssl=job_parameters_parser.verify_ssl,
        )
        manager.test_connectivity()

        search_id = job_parameters_parser.search_id
        window_size = int(job_parameters_parser.window_size or 720)

        siemplify.LOGGER.info(f"Fetching search query details for {search_id}")
        search_query_obj = manager.get_search_query(search_id)

        query_text = search_query_obj.get("query")

        if not query_text:
            siemplify.LOGGER.error(
                "Could not extract queryText from the retrieved search query. Aborting."
            )
            return

        now = datetime.now(timezone.utc)
        end_time = now
        start_time = end_time - timedelta(hours=window_size)

        siemplify.LOGGER.info(
            f"Triggering legacy fetch UDM search view from {start_time} to {end_time}"
        )

        operation = manager.search(
            query=query_text,
            start_time=start_time,
            end_time=end_time,
            max_events=100000,
        )

        operation_name = operation.get("name")
        if not operation_name:
            error_msg = (
                f"Search did not return an operation name. Response: {operation}"
            )
            siemplify.LOGGER.error(error_msg)
            siemplify.end(error_msg, "false")
            return

        siemplify.LOGGER.info(
            f"Search operation started: '{operation_name}'. Waiting for completion..."
        )

        # 4. Monitor operation until done
        completed_op = manager.wait_for_operation(
            operation_name=operation_name,
            poll_interval_seconds=5,
            timeout_seconds=600,
            logger=siemplify.LOGGER,
        )

        error = completed_op.get("error")
        metadata = completed_op.get("metadata", {})
        state = metadata.get("state", "UNKNOWN")

        if error:
            error_msg = error.get("message", str(error))
            error_code = error.get("code", "UNKNOWN")
            msg = f"Search operation failed with error (code {error_code}): {error_msg}"
            siemplify.LOGGER.error(msg)
            siemplify.end(msg, "false")
            return

        if state in ["FAILED", "CANCELLED"]:
            msg = f"Search operation ended with state: {state}"
            siemplify.LOGGER.error(msg)
            siemplify.end(msg, "false")
            return

        result_row_count = (
            completed_op.get("response", {}).get("metadata", {}).get("resultRowCount")
        )
        success_msg = f"Search operation completed successfully with state: '{state}'."
        if result_row_count is not None:
            success_msg += f" Materialized {result_row_count} rows."

        siemplify.LOGGER.info(
            "Successfully triggered the data table population search."
        )
        siemplify.LOGGER.info("--------------- JOB FINISHED ---------------")

    except Exception as error:
        siemplify.LOGGER.error(f"Got exception on main handler. Error: {error}")
        siemplify.LOGGER.exception(error)
        raise


if __name__ == "__main__":
    main()

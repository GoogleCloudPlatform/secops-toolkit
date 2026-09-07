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

from consts import INTEGRATION_NAME
from SecOpsToolkitManager import SecOpsToolkitManager
from SiemplifyJob import SiemplifyJob
from SiemplifyUtils import output_handler
from TIPCommon.extraction import extract_action_param, extract_configuration_param


class JobParametersParser:
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

        # Email settings - split comma separated string into Python list
        recipient_emails_param = extract_action_param(
            siemplify_, "Recipient Emails", is_mandatory=True, print_value=True
        )
        self.recipient_emails = [
            email.strip()
            for email in recipient_emails_param.split(",")
            if email.strip()
        ]

        # Tenant URL
        tenant_url_param = extract_action_param(
            siemplify_, "Tenant URL", is_mandatory=True, print_value=True
        )
        self.tenant_url = tenant_url_param.strip() if tenant_url_param else ""


def send_notification_email(
    parser: JobParametersParser, rules_to_notify: list, siemplify, logger
):
    try:
        subject = "Google SecOps - Rules Monitoring Notification"
        to_recipients = parser.recipient_emails
        tenant_url = parser.tenant_url
        tenant_link_html = (
            f'<a href="{tenant_url}" target="_blank" style="color: #1a73e8; text-decoration: underline;">{tenant_url}</a>'
            if tenant_url
            else "Google SecOps Console"
        )

        body = f"""
        <div style="font-family: Arial, sans-serif; font-size: 14px; color: #333; line-height: 1.6;">
            <p>Dear Security Detection Team,</p>
            <p>The following rule(s) in tenant <b>{tenant_link_html}</b> are currently in a <b>LIMITED</b> or <b>PAUSED</b> state and require attention:</p>
            <ul style="list-style-type: disc; margin-left: 20px;">
        """
        for r in rules_to_notify:
            rule_name = r.get("displayName", "Unknown")
            state = r.get("executionState", "UNSPECIFIED")
            body += f"""
                <li style="margin-bottom: 6px;">
                    <b>{rule_name}</b>: <span style="color: #d93025; font-weight: bold;">{state}</span>
                </li>
            """
        body += f"""
            </ul>
            <p style="margin-top: 16px;">
                Please review and re-enable the rules directly in the tenant console:<br>
                🔗 <b>Tenant Link:</b> <a href="{tenant_url}" target="_blank" style="color: #1a73e8; text-decoration: underline;">{tenant_url}</a>
            </p>
            <br>
            <p>Best Regards,<br><b>SecOps Team</b></p>
        </div>
        """

        siemplify.send_mail(subject, body, to_recipients, None, None)
        logger.info(f"Successfully sent notification email to TO: {to_recipients}")

    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        logger.exception("Failed to send email notification")


@output_handler
def main():
    siemplify = SiemplifyJob()
    siemplify.script_name = "RulesMonitoring"
    siemplify.LOGGER.info("--------------- JOB STARTED ---------------")

    try:
        parser = JobParametersParser(siemplify)
        siemplify.LOGGER.info("Successfully parsed parameters")

        manager = SecOpsToolkitManager.create_manager_instance(
            user_service_account=parser.creds,
            chronicle_soar=siemplify,
            api_root=parser.api_root,
            verify_ssl=parser.verify_ssl,
            workload_identity_email=parser.workload_identity_email,
        )

        siemplify.LOGGER.info("Fetching rules from SecOps...")
        rules = manager.list_rules()
        deployments = manager.list_rule_deployments()
        siemplify.LOGGER.info(
            f"Found {len(rules)} rules and {len(deployments)} deployments."
        )

        # Build map of rule name -> deployment state
        deployment_map = {}
        archive_map = {}
        for d in deployments:
            # name format is typically projects/.../rules/ru_.../deployment
            rule_name = d.get("name", "").removesuffix("/deployment")
            deployment_map[rule_name] = d.get("executionState", "UNSPECIFIED")
            archive_map[rule_name] = d.get("archived", False)

        affected_rules = []
        for r in rules:
            r_name = r.get("name")
            if archive_map.get(r_name, False):
                continue
            exec_state = deployment_map.get(r_name, "UNSPECIFIED")
            r["executionState"] = exec_state

            if exec_state in ["LIMITED", "PAUSED"]:
                affected_rules.append(r)

        siemplify.LOGGER.info(
            f"Found {len(affected_rules)} rules in LIMITED or PAUSED state."
        )

        if not affected_rules:
            siemplify.LOGGER.info("No affected rules found. Job finished.")
            siemplify.end("No affected rules found. Job finished.", "true")
            return

        table_name = "rules_monitoring"
        data_table_exists = False
        notified_rule_names = set()

        try:
            manager.get_data_table(table_name)
            data_table_exists = True
            siemplify.LOGGER.info(f"Data table '{table_name}' exists.")
        except Exception:  # noqa: BLE001
            siemplify.LOGGER.info(
                f"Data table '{table_name}' does not exist. Will create it."
            )

        if data_table_exists:
            # Fetch existing rows
            try:
                rows = manager.list_data_table_rows(table_name)
                for row in rows:
                    if row.get("values"):
                        notified_rule_names.add(row["values"][0])
            except Exception as e:  # noqa: BLE001
                siemplify.LOGGER.error(f"Failed to list data table rows: {e}")

        else:
            # Create data table
            try:
                manager.create_data_table(
                    name=table_name,
                    description="Stores rules that have been notified as PAUSED or LIMITED.",
                    header={"rule_name": "STRING"},
                    column_options={"rule_name": {"keyColumn": True}},
                )
                siemplify.LOGGER.info(
                    f"Successfully created data table '{table_name}'."
                )

                # Set TTL to 7 days (604800s)
                manager.update_data_table(
                    name=table_name,
                    row_time_to_live="604800s",
                    update_mask=["row_time_to_live"],
                )
                siemplify.LOGGER.info(
                    f"Successfully set TTL of 7 days for '{table_name}'."
                )
            except Exception as e:  # noqa: BLE001
                siemplify.LOGGER.error(f"Failed to create data table: {e}")

        rules_to_notify = []
        new_rows = []
        for r in affected_rules:
            if r.get("name") not in notified_rule_names:
                rules_to_notify.append(r)
                new_rows.append([r.get("name")])

        if rules_to_notify:
            siemplify.LOGGER.info(
                f"Notifying about {len(rules_to_notify)} new affected rules."
            )
            send_notification_email(
                parser, rules_to_notify, siemplify, siemplify.LOGGER
            )

            try:
                manager.create_data_table_rows(table_name, new_rows)
                siemplify.LOGGER.info(
                    f"Successfully added {len(new_rows)} rows to '{table_name}'."
                )
            except Exception as e:  # noqa: BLE001
                siemplify.LOGGER.error(f"Failed to add rows to data table: {e}")

        else:
            siemplify.LOGGER.info(
                "All affected rules were already notified recently. No email sent."
            )

        siemplify.LOGGER.info("--------------- JOB FINISHED ---------------")
        siemplify.end("Job completed successfully.", "true")

    except Exception as e:
        siemplify.LOGGER.error(f"Job execution failed: {e}")
        siemplify.LOGGER.exception("Job execution failed")
        siemplify.end(f"Job execution failed: {e}", "false")


if __name__ == "__main__":
    main()

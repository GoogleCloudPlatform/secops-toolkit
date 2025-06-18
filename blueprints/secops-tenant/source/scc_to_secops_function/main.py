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
import json
from google.cloud import pubsub_v1
from concurrent import futures
from secops import SecOpsClient

# Default timeout to wait for subscriber to send a message.
DEFAULT_TIMEOUT = 5
SECOPS_REGION = os.environ.get("SECOPS_REGION")
SECOPS_CUSTOMER_ID = os.environ.get("SECOPS_CUSTOMER_ID")
PROJECT_ID = os.environ.get("PROJECT_ID")


def main(req):
    """Entrypoint.

  Args:
    req: Request to execute the cloud function.

  Returns:
    string: "Ingestion completed."
  """
    client = SecOpsClient()
    chronicle = client.chronicle(customer_id=SECOPS_CUSTOMER_ID,
                                 project_id=PROJECT_ID,
                                 region=SECOPS_REGION)

    # Expecting values from cloud schedule trigger.
    request_json = req.get_json(silent=True)

    if request_json:
        subscription_id = request_json.get("SUBSCRIPTION_ID")
        secops_data_type = request_json.get("SECOPS_DATA_TYPE")
    else:
        print("Did not get configuration parameters from request body.")

    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID,
                                                     subscription_id)

    def get_and_ingest_messages(
            message: pubsub_v1.subscriber.message.Message) -> None:
        """Get message from the subscription.

    Args:
      message: Message received from subscription.

    Raises:
      ValueError, TypeError: Error when received message is not in json format.
    """
        print(f"Received {message.data!r}.")
        message.ack()
        data = (message.data).decode("utf-8")
        try:
            data = json.loads(data)
        except (ValueError, TypeError) as error:
            print("ERROR: Unexpected data format received "
                  "while collecting message details from subscription")
            raise error

        chronicle.ingest_log(log_type=secops_data_type,
                             log_message=json.dumps(data))

    future = subscriber.subscribe(subscription_path,
                                  callback=get_and_ingest_messages)

    with subscriber:
        try:
            future.result(timeout=DEFAULT_TIMEOUT)
        except futures.TimeoutError:
            future.cancel()
            future.result()

    return "Ingestion completed."

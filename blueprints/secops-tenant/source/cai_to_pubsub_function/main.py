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
import time
import logging
import google.auth
import os
import urllib.request
from datetime import datetime, timedelta
from googleapiclient import _auth
from google.cloud import pubsub_v1
from google.auth.transport.requests import AuthorizedSession

HTTP = AuthorizedSession(google.auth.default()[0])
LOGGER = logging.getLogger('cai-chronicle')


def generate_timestamp(offset_days=0):
    """
  Generates a timestamp string in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)
  based on the current UTC time with an optional offset in days.

  Args:
      offset_days (int, optional): Number of days to offset from current time. Defaults to 0.

  Returns:
      str: Timestamp string in ISO 8601 format.
  """
    # Get current UTC time
    now = datetime.utcnow()
    # Apply offset
    timestamp = now + timedelta(days=offset_days)
    # Format timestamp in ISO 8601 format
    formatted_time = timestamp.isoformat() + 'Z'
    return formatted_time


def assets_list(parent,
                asset_types,
                content_type,
                page_size,
                read_time,
                next_page=None):
    """Fetches assets from Cloud Asset Inventory (CAI) with pagination.

  Args:
      parent (str): The parent resource name (e.g., projects/your-project-id).
      asset_types (str): Comma-separated list of asset types to search for.
      content_type (str): Asset content type (e.g., RESOURCE).
      page_size (int): The maximum number of assets to return per page.
      read_time (str): Read time for assets as an RFC3339 timestamp.
      next_page (str, optional): Optional next page token for pagination.

  Returns:
      dict: A dictionary containing the response data (including status code and potentially JSON content).

  Raises:
      Exception: An exception if an error occurs during the request.
  """
    params = {
        "assetTypes": asset_types,
        'contentType': content_type,
        'pageSize': page_size,
        'readTime': read_time
    }
    if next_page:
        params['pageToken'] = next_page

    url = 'https://cloudasset.googleapis.com/v1/{parent}/assets'.format(
        parent=parent)
    headers = {"Content-Type": "application/json"}

    try:
        response = HTTP.get(url, headers=headers, params=params)
        return response
    except Exception as e:
        raise Exception(f"Error fetching assets: {e}")


def send_to_pubsub(pubsub_topic_id, asset):
    """
  Publishes a message to a Pub/Sub.

  Args:
      :param asset: The message data to be published.
      :param pubsub_topic_id: The pubsub topic ID where to publish asset

  Returns:
      str: The message ID of the published message (if successful).
      Exception: Raises an exception if there's an error publishing.
  """
    publisher = pubsub_v1.PublisherClient()

    try:
        # Encode message and publish
        data = json.dumps(asset).encode("utf-8")
        future = publisher.publish(pubsub_topic_id, data)
        # Get message ID (success)
        message_id = future.result()
        return message_id
    except Exception as e:
        # Handle exception (e.g., log error, retry)
        print(f"Error publishing message to Pub/Sub: {e}")
        raise  # Re-raise the exception for further handling


def main(request):
    """Fetches Cloud Asset Inventory (CAI) assets within a specified lookback period, 
  handles pagination, and sends retrieved assets to Pub/Sub.

  This function retrieves assets from CAI based on provided parameters and a 
  configurable lookback period. It iterates through paginated results, 
  extracts assets, and sends them to Pub/Sub. Error handling is included for 
  common conditions (success, throttling errors, unexpected exceptions).

  Raises:
      Exception: An exception for critical errors.
  """
    logging.basicConfig(
        level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO,
        format="[%(levelname)-8s] - %(asctime)s - %(message)s",
    )
    logging.root.setLevel(logging.DEBUG)
    # TODO(): should the lookback period be user configurable
    lookback_timestamp = generate_timestamp(-1)

    # Expecting values during cloud schedule trigger.
    request_json = request.get_json(silent=True)

    if request_json:
        nodes = request_json.get("NODES", [])
        chronicle_assets_config = request_json.get("CHRONICLE_ASSETS_CONFIG")
        content_type = request_json.get("CONTENT_TYPE")
        page_size = request_json.get("PAGE_SIZE")
        pubsub_project_id = request_json.get("PUBSUB_PROJECT_ID")
    else:
        LOGGER.error("Did not get configuration parameters from request body.")
        raise SystemExit('No configuration sent from Cloud Scheduler')

    # iterate through all the asset types
    for chronicle_ingestion_label in chronicle_assets_config.keys():
        asset_types = chronicle_assets_config[chronicle_ingestion_label][
            'asset_types']
        # iterate through all the GCP nodes for tenant
        for node in nodes:
            # List to store GCP CAI Assets
            assets = []
            more_results = True
            try:
                response = assets_list(node, asset_types, content_type,
                                       page_size, lookback_timestamp)
                while more_results:
                    LOGGER.info(f"response_code: {response.status_code}")
                    if response.status_code == 200:
                        fetched_assets = json.loads(response.text)
                        if "assets" in fetched_assets:
                            for each_asset in fetched_assets[
                                    "assets"]:  # refactor
                                assets.append(each_asset)
                        if 'nextPageToken' in fetched_assets:
                            LOGGER.info(f"More pages available.")
                            LOGGER.info(
                                f"nextPageToken: {fetched_assets['nextPageToken']}"
                            )
                            response = assets_list(
                                node, asset_types, content_type, page_size,
                                lookback_timestamp,
                                fetched_assets['nextPageToken'])
                        else:
                            if assets:
                                LOGGER.info(
                                    f"{len(assets)} assets to be sent to PubSub."
                                )
                                for asset in assets:
                                    send_to_pubsub(
                                        pubsub_topic_id=chronicle_assets_config[
                                            chronicle_ingestion_label]
                                        ['pubsub_topic_id'],
                                        asset=asset)
                            else:
                                LOGGER.info("No assets returned from GCP CAI.")
                            more_results = False
                    elif response.status_code == 429:
                        LOGGER.info(f"Sleeping for 60 seconds.")
                        time.sleep(60)
                    else:
                        LOGGER.info(
                            f"Catch all for any other HTTP error codes.")
                        more_results = False
                        break

            except Exception as e:
                LOGGER.error(f"Unexpected error: {e}")
                return f'{"status":"500", "data": "{e}"}'

    return '{"status":"200", "data": "OK"}'

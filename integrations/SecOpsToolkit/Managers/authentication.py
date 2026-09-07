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

from __future__ import annotations
import google.auth.credentials
import google.auth.exceptions
import google.auth.transport.requests
import google.cloud.bigquery
import requests
import requests.adapters
import TIPCommon.rest.auth
import TIPCommon.rest.gcp
import exceptions


def create_session(
    api_root: str | None,
    credentials: google.auth.credentials.Credentials,
    project_id: str | None,
    verify_ssl: bool,
) -> google.cloud.bigquery.Client:
    """Create a session for big query

    Args:
        api_root: The API root of big query instance
        credentials: The session credentials
        project_id: The Google project ID
        verify_ssl: Whether to verify the session

    Returns:
        A  big query client object
    """
    session = google.auth.transport.requests.AuthorizedSession(
        credentials, auth_request=_prepare_auth_request(verify_ssl)
    )
    session.verify = verify_ssl
    return google.cloud.bigquery.Client(
        project=project_id, _http=session, client_options={"api_endpoint": api_root}
    )


def _prepare_auth_request(verify_ssl: bool) -> google.auth.transport.requests.Request:
    """Prepare an authenticated request.

    Notes:
        This method is a duplicate of the same method in the AuthorizedSession class.
        The only change is that created session is using verify_ssl parameter to
        allow self-signed certificates.

    Args:
        verify_ssl: Whether to verify the session

    Returns:
        The request object
    """
    auth_request_session = requests.Session()
    auth_request_session.verify = verify_ssl

    retry_adapter = requests.adapters.HTTPAdapter(max_retries=3)
    auth_request_session.mount("https://", retry_adapter)

    return google.auth.transport.requests.Request(auth_request_session)


def get_credentials_using_workload_identity_email(
    workload_identity_email: str, quota_project_id: str, verify_ssl: bool
) -> google.auth.credentials.Credentials:
    try:
        return TIPCommon.rest.auth.build_credentials_from_sa(
            target_principal=workload_identity_email,
            quota_project_id=quota_project_id,
            verify_ssl=verify_ssl,
            scopes=google.cloud.bigquery.Client.SCOPE,
        )
    except google.auth.exceptions.RefreshError as e:
        workload_sa = TIPCommon.rest.gcp.get_workload_sa_email("Unknown Principal")
        raise exceptions.GoogleBigQueryValidationError(
            "Impersonation is not allowed for the provided service "
            f"account {workload_identity_email}. "
            'Please add the "Service Account Token Creator" role to the '
            f"service account: {workload_sa}"
        ) from e

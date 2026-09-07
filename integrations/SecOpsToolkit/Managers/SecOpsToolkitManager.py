import json
import datetime
import time
from typing import Optional
import requests
import requests.adapters
import google.auth
import google.auth.transport.requests
import google.oauth2.service_account
import exceptions, consts
import TIPCommon.types
import TIPCommon.rest.auth

class SecOpsToolkitManager:
    def __init__(self, session: requests.Session, api_root: str, chronicle_soar=None):
        self.session = session
        self.api_root = api_root.rstrip("/")
        self.chronicle_soar = chronicle_soar

    @classmethod
    def create_manager_instance(
        cls,
        user_service_account: str | TIPCommon.types.SingleJson | None,
        chronicle_soar: TIPCommon.types.ChronicleSOAR,
        api_root: str = consts.API_URL,
        verify_ssl: bool = False,
        workload_identity_email: str | None = None,
        scopes: list[str] = consts.OAUTH_SCOPES,
    ):

        credentials = None
        
        if workload_identity_email:
            credentials = TIPCommon.rest.auth.build_credentials_from_sa(
                target_principal=workload_identity_email,
                quota_project_id=None,
                verify_ssl=verify_ssl,
                scopes=scopes,
            )
        elif user_service_account:
            if isinstance(user_service_account, str):
                info = json.loads(user_service_account)
            else:
                info = user_service_account
            credentials = google.oauth2.service_account.Credentials.from_service_account_info(
                info, scopes=scopes
            )
        else:
            # Application Default Credentials
            credentials, _ = google.auth.default(scopes=scopes)

        auth_request_session = requests.Session()
        auth_request_session.verify = verify_ssl
        retry_adapter = requests.adapters.HTTPAdapter(max_retries=3)
        auth_request_session.mount("https://", retry_adapter)
        auth_req = google.auth.transport.requests.Request(auth_request_session)
        
        session = google.auth.transport.requests.AuthorizedSession(
            credentials, auth_request=auth_req
        )
        session.verify = verify_ssl

        return cls(session=session, api_root=api_root, chronicle_soar=chronicle_soar)

    def validate_response(self, response: requests.Response, error_msg: str = "Request failed"):
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            raise exceptions.SecOpsToolkitManagerError(f"{error_msg}: {e}. Response: {response.text}")

    def test_connectivity(self) -> bool:
        url = f"{self.api_root}"
        response = self.session.get(url)
        self.validate_response(response, "Failed to test connectivity")
        return True

    def get_search_query(self, name: str) -> dict:
        url = f"{self.api_root}/users/me/searchQueries"
        
        response = self.session.get(url)
        self.validate_response(response, "Failed to list search queries")
            
        queries = []
        data = response.json()
        queries.extend(data.get("searchQueries", []))
        while data.get("nextPageToken"):
            res = self.session.get(url, params={"pageToken": data.get("nextPageToken")})
            self.validate_response(res, "Failed to list search queries (pagination)")
            data = res.json()
            queries.extend(data.get("searchQueries", []))
            
        for q in queries:
            if q.get("name") == name or q.get("displayName") == name:
                return q
                
        raise exceptions.SecOpsToolkitManagerError(f"Search query {name} not found.")

    def search(
        self,
        query: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        instance_name: Optional[str] = None,
        case_insensitive: bool = False,
        snapshot_query: Optional[str] = None,
        max_detections: Optional[int] = None,
        max_events: Optional[int] = None,
    ) -> dict:
        url = f"{self.api_root}:search"

        if not instance_name and "projects/" in self.api_root:
            instance_name = self.api_root[self.api_root.find("projects/"):]

        search_query = {
            "query": query,
            "timeRange": {
                "startTime": start_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "endTime": end_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            },
            "resultLimit": max_events if max_events else 1000000,
        }

        if instance_name:
            search_query["parent"] = instance_name

        response = self.session.post(url, json=search_query)
        self.validate_response(response, "Failed to fetch UDM search view")
        return response.json()

    def create_data_table(self, name: str, description: str, header: dict, column_options: dict = None) -> dict:
        url = f"{self.api_root}/dataTables"
        params = {"dataTableId": name}
        
        column_info = []
        i = 0
        for col_name, col_val in header.items():
            column = {"columnIndex": i, "originalColumn": col_name}
            
            if isinstance(col_val, dict):
                t = col_val.get("type", "STRING")
                column["columnType"] = t.upper()
                for k, v in col_val.items():
                    if k != "type":
                        column[k] = v
            elif hasattr(col_val, "value"):
                column["columnType"] = col_val.value
            else:
                column["columnType"] = str(col_val).upper()
                
            if column_options and col_name in column_options:
                column.update(column_options[col_name])
                
            column_info.append(column)
            i += 1

        payload = {
            "description": description,
            "columnInfo": column_info,
        }

        response = self.session.post(url, params=params, json=payload)
        self.validate_response(response, "Failed to create data table")
        return response.json()

    def replace_data_table_rows(self, name: str, rows: list) -> dict:
        url = f"{self.api_root}/dataTables/{name}/dataTableRows:bulkReplace"
        payload = {"requests": [{"data_table_row": {"values": row}} for row in rows]}
        
        response = self.session.post(url, json=payload)
        self.validate_response(response, "Failed to replace data table rows")
        return response.json()

    def bulk_delete_data_table_rows(
        self,
        name: str,
        row_names: list,
        max_retries: int = 5,
        initial_backoff: float = 2.0,
    ) -> dict:
        """
        Deletes data table rows in bulk (up to 1000 rows per request) using dataTableRows:bulkDelete.
        Retries on 429 status code with exponential backoff.
        """
        url = f"{self.api_root}/dataTables/{name}/dataTableRows:bulkDelete"
        payload = {"names": row_names}
        
        response = None
        for attempt in range(max_retries + 1):
            response = self.session.post(url, json=payload)
            if response.status_code == 429:
                if attempt < max_retries:
                    backoff = initial_backoff * (2 ** attempt)
                    time.sleep(backoff)
                    continue
            break

        self.validate_response(response, "Failed to bulk delete data table rows")
        return response.json() if response.text else {}

    def clear_data_table(
        self,
        name: str,
        batch_size: int = 1000,
        max_retries: int = 5,
        initial_backoff: float = 2.0,
        logger=None,
    ) -> int:
        """
        Lists all rows in a data table and deletes them using bulkDelete in batches of up to 1000,
        handling 429 rate limits with exponential backoff.
        """
        if logger:
            logger.info(f"Listing rows for data table '{name}' to prepare deletion...")
            
        rows = self.list_data_table_rows(
            name=name,
            page_size=batch_size,
            max_retries=max_retries,
            initial_backoff=initial_backoff,
        )
        
        if not rows:
            if logger:
                logger.info(f"Data table '{name}' is already empty. Nothing to delete.")
            return 0
            
        row_names = []
        for r in rows:
            if isinstance(r, dict) and "name" in r:
                row_names.append(r["name"])
            elif isinstance(r, str):
                row_names.append(r)

        total_rows = len(row_names)
        if logger:
            logger.info(f"Found {total_rows} rows in data table '{name}'. Deleting in batches of {batch_size}...")

        total_deleted = 0
        for i in range(0, total_rows, batch_size):
            batch = row_names[i : i + batch_size]
            if logger:
                logger.info(
                    f"Bulk deleting rows {i + 1} to {min(i + batch_size, total_rows)} of {total_rows} for table '{name}'..."
                )
            self.bulk_delete_data_table_rows(
                name=name,
                row_names=batch,
                max_retries=max_retries,
                initial_backoff=initial_backoff,
            )
            total_deleted += len(batch)

        if logger:
            logger.info(f"Successfully deleted all {total_deleted} rows from data table '{name}'.")
            
        return total_deleted

    def get_operation(self, operation_name: str) -> dict:
        """
        Retrieves the latest state of a long-running operation.
        """
        if operation_name.startswith("http"):
            url = operation_name
        else:
            op_id = operation_name.split("/")[-1]
            url = f"{self.api_root}/operations/{op_id}"

        response = self.session.get(url)
        self.validate_response(response, f"Failed to get operation '{operation_name}'")
        return response.json()

    def wait_for_operation(
        self,
        operation_name: str,
        poll_interval_seconds: int = 5,
        timeout_seconds: int = 600,
        logger=None,
    ) -> dict:
        """
        Polls the operation until done is True or timeout is reached.
        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            op = self.get_operation(operation_name)
            is_done = op.get("done", False)
            state = op.get("metadata", {}).get("state", "RUNNING")
            
            if logger:
                logger.info(f"Operation {operation_name} status: done={is_done}, state={state}")
                
            if is_done:
                return op
                
            time.sleep(poll_interval_seconds)
            
        raise exceptions.SecOpsToolkitManagerError(
            f"Operation {operation_name} timed out after {timeout_seconds} seconds."
        )

    def list_rules(self, view: str = "FULL", page_size: int = 1000) -> list:
        url = f"{self.api_root}/rules"
        
        rules = []
        params = {"view": view, "pageSize": page_size}
        response = self.session.get(url, params=params)
        self.validate_response(response, "Failed to list rules")
        
        data = response.json()
        rules.extend(data.get("rules", []))
        
        while data.get("nextPageToken"):
            params["pageToken"] = data.get("nextPageToken")
            response = self.session.get(url, params=params)
            self.validate_response(response, "Failed to list rules (pagination)")
            data = response.json()
            rules.extend(data.get("rules", []))
            
        return rules

    def list_rule_deployments(self, page_size: int = 1000) -> list:
        url = f"{self.api_root}/rules/-/deployments"
        
        deployments = []
        params = {"pageSize": page_size}
        response = self.session.get(url, params=params)
        self.validate_response(response, "Failed to list rule deployments")
        
        data = response.json()
        deployments.extend(data.get("ruleDeployments", []))
        
        while data.get("nextPageToken"):
            params["pageToken"] = data.get("nextPageToken")
            response = self.session.get(url, params=params)
            self.validate_response(response, "Failed to list rule deployments (pagination)")
            data = response.json()
            deployments.extend(data.get("ruleDeployments", []))
            
        return deployments

    def get_data_table(self, name: str) -> dict:
        url = f"{self.api_root}/dataTables/{name}"
        
        response = self.session.get(url)
        self.validate_response(response, "Failed to get data table")
        return response.json()

    def update_data_table(self, name: str, description: str = None, row_time_to_live: str = None, update_mask: list = None) -> dict:
        url = f"{self.api_root}/dataTables/{name}"
        payload = {}
        if description is not None:
            payload["description"] = description
        if row_time_to_live is not None:
            payload["rowTimeToLive"] = row_time_to_live
            
        params = {}
        if update_mask:
            params["updateMask"] = ",".join(update_mask)
            
        if "updateMask" in params and "row_time_to_live" in params["updateMask"]:
            params["updateMask"] = params["updateMask"].replace("row_time_to_live", "rowTimeToLive")
            
        response = self.session.patch(url, params=params, json=payload)
        self.validate_response(response, "Failed to update data table")
        return response.json()

    def list_data_table_rows(
        self,
        name: str,
        page_size: int = 1000,
        max_retries: int = 5,
        initial_backoff: float = 2.0,
    ) -> list:
        """
        Lists all rows in a data table with pagination and 429 retry handling.
        """
        url = f"{self.api_root}/dataTables/{name}/dataTableRows"
        params = {"pageSize": page_size}
        
        rows = []
        page_token = None
        
        while True:
            if page_token:
                params["pageToken"] = page_token
                
            response = None
            for attempt in range(max_retries + 1):
                response = self.session.get(url, params=params)
                if response.status_code == 429:
                    if attempt < max_retries:
                        backoff = initial_backoff * (2 ** attempt)
                        time.sleep(backoff)
                        continue
                break
                
            self.validate_response(response, "Failed to list data table rows")
            data = response.json()
            rows.extend(data.get("dataTableRows", []))
            
            page_token = data.get("nextPageToken")
            if not page_token:
                break
                
        return rows

    def create_data_table_rows(self, name: str, rows: list) -> dict:
        url = f"{self.api_root}/dataTables/{name}/dataTableRows:bulkCreate"
        payload = {"requests": [{"data_table_row": {"values": row}} for row in rows]}
        
        response = self.session.post(url, json=payload)
        self.validate_response(response, "Failed to create data table rows")
        return response.json()

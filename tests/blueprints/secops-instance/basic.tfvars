# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

project_id = "test-project"
project_create_config = {
  billing_account = "12345-ABCDEF-12345"
  parent          = "folders/2345678901"
}
secops_tenant_config = {
  customer_id = "xxxxxxx-xxxxx-xxxxxx-xxxxxxx"
  region      = "europe"
}
secops_ingestion_config = {
  ingest_workspace_data = false
}
secops_group_principals = {
  viewers = ["gcp-secops-admins@example.com"]
}
secops_iam = {
  "user:bruzzechesse@google.com" = {
    roles  = ["roles/chronicle.editor"]
    scopes = ["gscope"]
  }
}
third_party_integration_config = {
  azure_ad = {
    oauth_credentials = {
      client_id     = "xxxxxxx-xxxxx-xxxxx-xxxxxxx"
      client_secret = "xxxxxxxxxxxxxxxxxxxxxxxxx"
    }
    retrieve_devices = true
    retrieve_groups  = true
    tenant_id        = "xxxxxx-xxxxx-xxxxx-xxxxxxx"
  }
  workspace = {
    delegated_user = "secops-feed@example.com"
    customer_id    = "CXXXXXXXX"
  }
  okta = {
    auth_header_key_values = {
      "Authorization" : "XXXXXXXXXXXXX"
    }
    hostname                   = "xxxxx.okta.com"
    manager_id_reference_field = "managerId"
  }
}
monitoring_config = {
  enabled             = true
  notification_emails = ["user@example.com"]
}
secops_data_rbac_config = {
  labels = {
    google = {
      description = "Google logs"
      label_id    = "google"
      udm_query   = "principal.hostname=\"google.com\""
    }
  }
  scopes = {
    google = {
      description = "Google logs"
      scope_id    = "gscope"
      allowed_data_access_labels = [{
        data_access_label = "google"
      }]
    }
  }
}
webhook_feeds_config = {
  okta = {
    log_type     = "OKTA"
    display_name = "webhook-okta"
  }
}

/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

# Workspace logs integration SA
module "workspace-integration-sa" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/iam-service-account"
  count      = var.third_party_integration_config.workspace == null ? 0 : 1
  project_id = module.project.project_id
  name       = "workspace-integration"
}

resource "google_service_account_key" "workspace_integration_key" {
  count              = var.third_party_integration_config.workspace == null ? 0 : 1
  service_account_id = module.workspace-integration-sa[0].email
}

module "workspace-feeds" {
  source = "../../modules/secops-feeds"
  count  = var.third_party_integration_config.workspace == null ? 0 : 1
  secops_config = merge(var.secops_tenant_config, {
    project = module.project.project_id
  })
  feeds = {
    ws-users = {
      display_name = "Workspace Users"
      log_type     = "WORKSPACE_USERS"
      workspace_users_settings = {
        workspace_customer_id = var.third_party_integration_config.workspace.customer_id
        projection_type       = "FULL_PROJECTION"
        authentication = {
          token_endpoint = "https://oauth2.googleapis.com/token",
          claims = {
            audience = "https://oauth2.googleapis.com/token",
            issuer   = module.workspace-integration-sa[0].email,
            subject  = var.third_party_integration_config.workspace.delegated_user
          }
          rs_credentials = {
            private_key = jsondecode(base64decode(google_service_account_key.workspace_integration_key[0].private_key)).private_key
          }
        }
      }
    }
    ws-activity = {
      display_name = "Workspace Activity"
      log_type     = "WORKSPACE_ACTIVITY"
      workspace_activity_settings = {
        workspace_customer_id = var.third_party_integration_config.workspace.customer_id
        applications          = var.third_party_integration_config.workspace.applications
        authentication = {
          token_endpoint = "https://oauth2.googleapis.com/token",
          claims = {
            audience = "https://oauth2.googleapis.com/token",
            issuer   = module.workspace-integration-sa[0].email,
            subject  = var.third_party_integration_config.workspace.delegated_user
          }
          rs_credentials = {
            private_key = jsondecode(base64decode(google_service_account_key.workspace_integration_key[0].private_key)).private_key
          }
        }
      }
    }
    ws-alerts = {
      display_name = "Workspace Alerts"
      log_type     = "WORKSPACE_ALERTS"
      workspace_alerts_settings = {
        workspace_customer_id = var.third_party_integration_config.workspace.customer_id
        authentication = {
          token_endpoint = "https://oauth2.googleapis.com/token",
          claims = {
            audience = "https://oauth2.googleapis.com/token",
            issuer   = module.workspace-integration-sa[0].email,
            subject  = var.third_party_integration_config.workspace.delegated_user
          }
          rs_credentials = {
            private_key = jsondecode(base64decode(google_service_account_key.workspace_integration_key[0].private_key)).private_key
          }
        }
      }
    }
    ws-mobile = {
      display_name = "Workspace Mobile"
      log_type     = "WORKSPACE_MOBILE"
      workspace_mobile_settings = {
        workspace_customer_id = var.third_party_integration_config.workspace.customer_id
        authentication = {
          token_endpoint = "https://oauth2.googleapis.com/token",
          claims = {
            audience = "https://oauth2.googleapis.com/token",
            issuer   = module.workspace-integration-sa[0].email,
            subject  = var.third_party_integration_config.workspace.delegated_user
          }
          rs_credentials = {
            private_key = jsondecode(base64decode(google_service_account_key.workspace_integration_key[0].private_key)).private_key
          }
        }
      }
    }
    ws-chrome = {
      display_name = "Workspace ChromeOS"
      log_type     = "WORKSPACE_CHROMEOS"
      workspace_chrome_os_settings = {
        workspace_customer_id = var.third_party_integration_config.workspace.customer_id
        authentication = {
          token_endpoint = "https://oauth2.googleapis.com/token",
          claims = {
            audience = "https://oauth2.googleapis.com/token",
            issuer   = module.workspace-integration-sa[0].email,
            subject  = var.third_party_integration_config.workspace.delegated_user
          }
          rs_credentials = {
            private_key = jsondecode(base64decode(google_service_account_key.workspace_integration_key[0].private_key)).private_key
          }
        }
      }
    }
    ws-group = {
      display_name = "Workspace Groups"
      log_type     = "WORKSPACE_GROUPS"
      workspace_groups_settings = {
        workspace_customer_id = var.third_party_integration_config.workspace.customer_id
        authentication = {
          token_endpoint = "https://oauth2.googleapis.com/token",
          claims = {
            audience = "https://oauth2.googleapis.com/token",
            issuer   = module.workspace-integration-sa[0].email,
            subject  = var.third_party_integration_config.workspace.delegated_user
          }
          rs_credentials = {
            private_key = jsondecode(base64decode(google_service_account_key.workspace_integration_key[0].private_key)).private_key
          }
        }
      }
    }
  }
}

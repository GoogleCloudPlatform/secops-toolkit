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

module "webhook_feeds" {
  source = "../../modules/secops-feeds"
  secops_config = merge(var.secops_tenant_config, {
    project = module.project.project_id
  })
  feeds = { for key, value in var.webhook_feeds_config : key => {
    display_name = value.display_name
    log_type     = value.log_type
    https_push_webhook_settings = {
      split_delimiter = value.split_delimiter
    }
  } }
}

resource "restful_operation" "webhook_feeds_secret" {
  for_each = var.webhook_feeds_config
  path     = "${local.secops_feeds_api_path}/${module.webhook_feeds.feeds_id[each.key]}:generateSecret"
  method   = "POST"
}

# Azure AD feeds
module "azure_ad_feeds" {
  count  = var.third_party_integration_config.azure_ad == null ? 0 : 1
  source = "../../modules/secops-feeds"
  secops_config = merge(var.secops_tenant_config, {
    project = module.project.project_id
  })
  feeds = {
    azure-ad = {
      display_name          = "Azure AD",
      secret_manager_config = var.third_party_integration_config.azure_ad.secret_manager_config,
      azure_ad_settings = {
        auth_endpoint = "login.microsoftonline.com",
        hostname      = "graph.microsoft.com/v1.0/auditLogs/signIns",
        tenant_id     = var.third_party_integration_config.azure_ad.tenant_id,
        authentication = {
          client_id     = var.third_party_integration_config.azure_ad.oauth_credentials.client_id
          client_secret = var.third_party_integration_config.azure_ad.oauth_credentials.client_secret
        }
      }
      log_type = "AZURE_AD"
    }
    azure-ad-audit = {
      display_name          = "Azure AD Audit",
      secret_manager_config = var.third_party_integration_config.azure_ad.secret_manager_config,
      azure_ad_audit_settings = {
        auth_endpoint = "login.microsoftonline.com",
        hostname      = "graph.microsoft.com/v1.0/auditLogs/directoryAudits",
        tenant_id     = var.third_party_integration_config.azure_ad.tenant_id,
        authentication = {
          client_id     = var.third_party_integration_config.azure_ad.oauth_credentials.client_id
          client_secret = var.third_party_integration_config.azure_ad.oauth_credentials.client_secret
        }
      }
      log_type = "AZURE_AD_AUDIT"
    }
    azure-ad-context = {
      display_name          = "Azure AD Context",
      secret_manager_config = var.third_party_integration_config.azure_ad.secret_manager_config,
      azure_ad_context_settings = {
        auth_endpoint = "login.microsoftonline.com",
        hostname      = "graph.microsoft.com/beta",
        tenant_id     = var.third_party_integration_config.azure_ad.tenant_id,
        authentication = {
          client_id     = var.third_party_integration_config.azure_ad.oauth_credentials.client_id
          client_secret = var.third_party_integration_config.azure_ad.oauth_credentials.client_secret
        }
      }
      log_type = "AZURE_AD_CONTEXT"
    }
  }
}

# Okta Feeds
module "okta_feeds" {
  count  = var.third_party_integration_config.okta == null ? 0 : 1
  source = "../../modules/secops-feeds"
  secops_config = merge(var.secops_tenant_config, {
    project = module.project.project_id
  })
  feeds = {
    okta = {
      display_name          = "Okta",
      secret_manager_config = var.third_party_integration_config.okta.secret_manager_config,
      okta_settings = {
        authentication = {
          header_key_values = [
            {
              key   = "Authorization"
              value = var.third_party_integration_config.okta.api_key
            }
          ]
        },
        hostname = var.third_party_integration_config.okta.hostname
      }
      log_type = "OKTA"
    }
    okta-user-context = {
      display_name          = "Okta User Context",
      secret_manager_config = var.third_party_integration_config.okta.secret_manager_config,
      okta_user_context_settings = {
        authentication = {
          header_key_values = [
            {
              key   = "Authorization"
              value = var.third_party_integration_config.okta.api_key
            }
          ]
        },
        hostname                   = var.third_party_integration_config.okta.hostname,
        manager_id_reference_field = var.third_party_integration_config.okta.manager_id_reference_field
      }
      log_type = "OKTA_USER_CONTEXT"
    }
  }
}

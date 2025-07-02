/**
 * Copyright 2025 Google LLC
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

locals {
  azure_ad_feeds = {
    azure-ad = {
      log_type  = "AZURE_AD"
      feed_type = "azure_ad_settings"
      hostname  = "graph.microsoft.com/v1.0/auditLogs/signIns"
    }
    azure-ad-audit = {
      log_type  = "AZURE_AD_AUDIT"
      feed_type = "azure_ad_audit_settings"
      hostname  = "graph.microsoft.com/v1.0/auditLogs/directoryAudits"
    }
    azure-ad-context = {
      log_type  = "AZURE_AD_CONTEXT"
      feed_type = "azure_ad_context_settings"
      hostname  = "graph.microsoft.com/beta"
    }
  }
  okta_feeds = {
    okta = {
      log_type  = "OKTA"
      feed_type = "okta_settings"
    }
    okta-user-context = {
      log_type  = "OKTA_USER_CONTEXT"
      feed_type = "okta_user_context_settings"
    }
  }
  secops_webhook_feeds_id = {
    for key, value in restful_resource.webhook_feeds : key =>
    [for feed in value.output.feeds : element(split("/", feed.name), length(split("/", feed.name)) - 1)
    if try(feed.displayName == lower(key), false)][0]
  }
}

resource "restful_resource" "webhook_feeds" {
  for_each        = var.webhook_feeds_config
  path            = local.secops_feeds_api_path
  create_method   = "POST"
  delete_method   = "DELETE"
  check_existance = false
  delete_path     = "$query_unescape(body.name)"
  read_selector   = "feeds.#(displayName==\"${lower(each.key)}\")"
  body = {
    name : lower(each.key),
    display_name : coalesce(each.value.display_name, lower(each.key)),
    details : {
      feed_source_type : "HTTPS_PUSH_WEBHOOK",
      log_type : "projects/${module.project.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/logTypes/${each.key}",
      httpsPushWebhookSettings : {}
    }
  }
  write_only_attrs = ["details"]
  lifecycle {
    ignore_changes = [body, output]
  }
}

resource "restful_operation" "webhook_feeds_secret" {
  for_each = var.webhook_feeds_config
  path     = "${local.secops_feeds_api_path}/${local.secops_webhook_feeds_id[each.key]}:generateSecret"
  method   = "POST"
}

# Azure AD feeds

resource "restful_resource" "azure_ad_feeds" {
  for_each        = var.third_party_integration_config.azure_ad == null ? {} : local.azure_ad_feeds
  path            = local.secops_feeds_api_path
  create_method   = "POST"
  delete_method   = "DELETE"
  check_existance = false
  delete_path     = "$query_unescape(body.name)"
  read_selector   = "feeds.#(displayName==\"${lower(each.key)}\")"
  body = {
    "name" : lower(each.key),
    "display_name" : lower(each.key),
    "details" : {
      feed_source_type : "API",
      log_type : "projects/${module.project.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/logTypes/${each.value.log_type}",
      (each.value.feed_type) : merge({
        authentication : {
          client_id : var.third_party_integration_config.azure_ad.oauth_credentials.client_id,
          client_secret : var.third_party_integration_config.azure_ad.oauth_credentials.client_secret,
        },
        hostname : each.value.hostname,
        auth_endpoint : "login.microsoftonline.com",
        tenant_id : var.third_party_integration_config.azure_ad.tenant_id,
        }, each.key == "azure-ad-context" ? {
        retrieve_groups : var.third_party_integration_config.azure_ad.retrieve_groups
        retrieve_devices : var.third_party_integration_config.azure_ad.retrieve_devices
      } : {})
    }
  }
  write_only_attrs = ["details"]
  lifecycle {
    ignore_changes = [body, output]
  }
}

# Okta feeds

resource "restful_resource" "okta_ad_feeds" {
  for_each        = var.third_party_integration_config.okta == null ? {} : local.okta_feeds
  path            = local.secops_feeds_api_path
  create_method   = "POST"
  delete_method   = "DELETE"
  check_existance = false
  delete_path     = "$query_unescape(body.name)"
  read_selector   = "feeds.#(displayName==\"${lower(each.key)}\")"
  body = {
    "name" : lower(each.key),
    "display_name" : lower(each.key),
    "details" : {
      "feed_source_type" : "API",
      "log_type" : "projects/${module.project.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/logTypes/${each.value.log_type}",
      (each.value.feed_type) : merge({
        "authentication" : {
          "header_key_values" : [for k, v in var.third_party_integration_config.okta.auth_header_key_values : { key = k, value = v }]
        },
        "hostname" : var.third_party_integration_config.okta.hostname
        }, each.key == "okta-user-context" ? {
        "manager_id_reference_field" : var.third_party_integration_config.okta.manager_id_reference_field
      } : {})
    }
  }
  write_only_attrs = ["details"]
  lifecycle {
    ignore_changes = [body, output]
  }
}
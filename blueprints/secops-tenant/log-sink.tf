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
  secops_to_gcp_logs_feeds_mapping = {
    GCP_CLOUDAUDIT = [
      "log_id(\"cloudaudit.googleapis.com/activity\")",
      "log_id(\"cloudaudit.googleapis.com/system_event\")",
      "log_id(\"cloudaudit.googleapis.com/policy\")",
      "log_id(\"cloudaudit.googleapis.com/access_transparency\")"
    ]
    GCP_CLOUD_NAT = [
      "log_id(\"compute.googleapis.com/nat_flows\")"
    ]
    GCP_DNS = [
      "log_id(\"dns.googleapis.com/dns_queries\")"
    ]
    GCP_FIREWALL = [
      "log_id(\"compute.googleapis.com/firewall\")"
    ]
    GCP_IDS = [
      "log_id(\"ids.googleapis.com/threat\")",
      "log_id(\"ids.googleapis.com/traffic\")"
    ]
    GCP_LOADBALANCING = [
      "log_id(\"requests\")",
      "log_id(\"loadbalancing.googleapis.com/external_regional_requests\")",
      "log_id(\"networksecurity.googleapis.com/network_dos_attack_mitigations\")",
      "log_id(\"networksecurity.googleapis.com/dos_attack\")"
    ]
    GCP_CLOUDSQL = [
      "log_id(\"cloudsql.googleapis.com/mysql-general.log\")",
      "log_id(\"cloudsql.googleapis.com/mysql.err\")",
      "log_id(\"cloudsql.googleapis.com/postgres.log\")",
      "log_id(\"cloudsql.googleapis.com/sqlagent.out\")",
      "log_id(\"cloudsql.googleapis.com/sqlserver.err\")"
    ]
    NIX_SYSTEM = [
      "log_id(\"syslog\")",
      "log_id(\"authlog\")",
      "log_id(\"securelog\")"
    ]
    LINUX_SYSMON = [
      "log_id(\"sysmon.raw\")"
    ]
    WINEVTLOG = [
      "log_id(\"winevt.raw\")",
      "log_id(\"windows_event_log\")"
    ]
    BRO_JSON = [
      "log_id(\"zeek_json_streaming_conn\")",
      "log_id(\"zeek_json_streaming_dhcp\")",
      "log_id(\"zeek_json_streaming_dns\")",
      "log_id(\"zeek_json_streaming_http\")",
      "log_id(\"zeek_json_streaming_ssh\")",
      "log_id(\"zeek_json_streaming_ssl\")"
    ]
    KUBERNETES_NODE = [
      "log_id(\"events\")",
      "log_id(\"stdout\")",
      "log_id(\"stderr\")"
    ]
    AUDITD = [
      "log_id(\"audit_log\")"
    ]
    GCP_APIGEE_X = [
      "logName =~ \"^projects/[\\w\\-]+/logs/apigee\\.googleapis\\.com[\\w\\-]*$\""
    ]
  }
  logging_sink = {
    for k, v in var.gcp_logs_ingestion_config : k =>
    {
      filter = join(" OR ", local.secops_to_gcp_logs_feeds_mapping[k])
      type   = "pubsub"
    } if v.enabled
  }
  secops_log_feeds_id = {
    for key, value in restful_resource.feeds : key => element(split("/", value.output.name), length(split("/", value.output.name)) - 1)
  }
  secops_log_feeds_secret = {
    for key, value in restful_operation.feeds_secret : key => value.output.secret
  }
}

module "gcp-logs-to-chronicle-pubsub-sa" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/iam-service-account"
  count      = local.bootstrap_log_integration ? 1 : 0
  project_id = module.project.project_id
  name       = "gcp-logs-to-secops-pubsub"
  iam = {
    "roles/iam.serviceAccountTokenCreator" = [
      module.project.service_agents.pubsub.iam_email
    ]
  }
}

module "pubsub-gcp-logs-topics" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/pubsub"
  for_each   = local.bootstrap_log_integration ? local.logging_sink : {}
  project_id = module.project.project_id
  name       = "secops_sink_${lower(each.key)}"
  subscriptions = {
    (lower(each.key)) = {
      push = {
        endpoint   = "https://${var.secops_tenant_config.region}-chronicle.googleapis.com/v1alpha/projects/${module.project.number}/locations/${var.secops_tenant_config.region}/instances/${local.secops_customer_id}/feeds/${local.secops_log_feeds_id[each.key]}:importPushLogs${var.secops_ingestion_config.ingest_feed_type == "HTTPS_PUSH_WEBHOOK" ? format("?key=%s&secret=%s", google_apikeys_key.feed_api_key.key_string, local.secops_log_feeds_secret[each.key]) : ""}"
        attributes = {}
        no_wrapper = var.secops_ingestion_config.ingest_feed_type == "HTTPS_PUSH_GOOGLE_CLOUD_PUBSUB" ? { write_metadata = false } : { write_metadata = true }
        oidc_token = var.secops_ingestion_config.ingest_feed_type == "HTTPS_PUSH_GOOGLE_CLOUD_PUBSUB" ? {
          service_account_email = module.gcp-logs-to-chronicle-pubsub-sa[0].email
        } : null
      }
    }
  }
}

resource "restful_resource" "feeds" {
  for_each = local.bootstrap_log_integration ? {
    for k, v in var.gcp_logs_ingestion_config : k => v if v.enabled
  } : {}
  provider = restful.feeds
  path            = local.secops_feeds_api_path
  create_method   = "POST"
  delete_method   = "DELETE"
  check_existance = false
  delete_path     = "$query_unescape(body.name)"
  read_selector   = "feeds.#(displayName==\"${lower(each.key)}\")"
  body = {
    "name" : lower(each.key),
    "display_name" : lower(each.key),
    "details" : merge({
      "feed_source_type" : var.secops_ingestion_config.ingest_feed_type,
      "log_type" : "projects/${module.project.project_id}/locations/${var.secops_tenant_config.region}/instances/${local.secops_customer_id}/logTypes/${each.key}",
      }, var.secops_ingestion_config.ingest_feed_type == "HTTPS_PUSH_GOOGLE_CLOUD_PUBSUB" ?
    { https_push_google_cloud_pubsub_settings : {} } : { httpsPushWebhookSettings : {} })
  }
  write_only_attrs = ["details"]
  lifecycle {
    ignore_changes = [body]
  }
}

resource "restful_operation" "feeds_secret" {
  for_each = local.bootstrap_log_integration ? {
    for k, v in var.gcp_logs_ingestion_config : k => v if v.enabled && var.secops_ingestion_config.ingest_feed_type == "HTTPS_PUSH_WEBHOOK"
  } : {}
  provider = restful.feeds
  path   = "${local.secops_feeds_api_path}/${local.secops_log_feeds_id[each.key]}:generateSecret"
  method = "POST"
}

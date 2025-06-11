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
  secops_to_gcp_assets_mapping = {
    GCP_BIGQUERY_CONTEXT = [
      "bigquery.googleapis.com/Dataset",
      "bigquery.googleapis.com/Model",
      "bigquery.googleapis.com/Table"
    ]
    GCP_CLOUD_FUNCTIONS_CONTEXT = [
      "cloudfunctions.googleapis.com/CloudFunction",
      "cloudfunctions.googleapis.com/Function"
    ]
    GCP_SQL_CONTEXT = [
      "sqladmin.googleapis.com/BackupRun",
      "sqladmin.googleapis.com/Instance"
    ]
    GCP_COMPUTE_CONTEXT = [
      "compute.googleapis.com/Autoscaler",
      "compute.googleapis.com/Address",
      "compute.googleapis.com/BackendBucket",
      "compute.googleapis.com/BackendService",
      "compute.googleapis.com/Commitment",
      "compute.googleapis.com/Disk",
      "compute.googleapis.com/ExternalVpnGateway",
      "compute.googleapis.com/Firewall",
      "compute.googleapis.com/FirewallPolicy",
      "compute.googleapis.com/ForwardingRule",
      "compute.googleapis.com/GlobalAddress",
      "compute.googleapis.com/GlobalForwardingRule",
      "compute.googleapis.com/HealthCheck",
      "compute.googleapis.com/HttpHealthCheck",
      "compute.googleapis.com/HttpsHealthCheck",
      "compute.googleapis.com/Image",
      "compute.googleapis.com/Instance",
      "compute.googleapis.com/InstanceGroup",
      "compute.googleapis.com/InstanceGroupManager",
      "compute.googleapis.com/InstanceTemplate",
      "compute.googleapis.com/Interconnect",
      "compute.googleapis.com/InterconnectAttachment",
      "compute.googleapis.com/License",
      "compute.googleapis.com/MachineImage",
      "compute.googleapis.com/Network",
      "compute.googleapis.com/NetworkEndpointGroup",
      "compute.googleapis.com/NodeGroup",
      "compute.googleapis.com/NodeTemplate",
      "compute.googleapis.com/PacketMirroring",
      "compute.googleapis.com/Project",
      "compute.googleapis.com/PublicDelegatedPrefix",
      "compute.googleapis.com/RegionBackendService",
      "compute.googleapis.com/RegionDisk",
      "compute.googleapis.com/Reservation",
      "compute.googleapis.com/ResourcePolicy",
      "compute.googleapis.com/Route",
      "compute.googleapis.com/Router",
      "compute.googleapis.com/SecurityPolicy",
      "compute.googleapis.com/Snapshot",
      "compute.googleapis.com/SslCertificate",
      "compute.googleapis.com/SslPolicy",
      "compute.googleapis.com/Subnetwork",
      "compute.googleapis.com/ServiceAttachment",
      "compute.googleapis.com/TargetHttpProxy",
      "compute.googleapis.com/TargetHttpsProxy",
      "compute.googleapis.com/TargetInstance",
      "compute.googleapis.com/TargetPool",
      "compute.googleapis.com/TargetTcpProxy",
      "compute.googleapis.com/TargetSslProxy",
      "compute.googleapis.com/TargetVpnGateway",
      "compute.googleapis.com/UrlMap",
      "compute.googleapis.com/VpnGateway",
      "compute.googleapis.com/VpnTunnel"
    ]
    GCP_KUBERNETES_CONTEXT = [
      "apps.k8s.io/Deployment",
      "apps.k8s.io/ReplicaSet",
      "batch.k8s.io/Job",
      "container.googleapis.com/Cluster",
      "container.googleapis.com/NodePool",
      "extensions.k8s.io/Ingress",
      "k8s.io/Namespace",
      "k8s.io/Node",
      "k8s.io/Pod",
      "k8s.io/Service",
      "networking.k8s.io/Ingress",
      "networking.k8s.io/NetworkPolicy",
      "rbac.authorization.k8s.io/ClusterRole",
      "rbac.authorization.k8s.io/ClusterRoleBinding",
      "rbac.authorization.k8s.io/Role",
      "rbac.authorization.k8s.io/RoleBinding"
    ]
    GCP_IAM_CONTEXT = [
      "iam.googleapis.com/ServiceAccount",
      "iam.googleapis.com/Role",
      "iam.googleapis.com/ServiceAccountKey"
    ]
    GCP_NETWORK_CONNECTIVITY_CONTEXT = [
      "networkconnectivity.googleapis.com/Hub",
      "networkconnectivity.googleapis.com/PolicyBasedRoutes",
      "networkconnectivity.googleapis.com/Spoke"
    ]
    GCP_RESOURCE_MANAGER_CONTEXT = [
      "cloudresourcemanager.googleapis.com/Folder",
      "cloudresourcemanager.googleapis.com/Organization",
      "cloudresourcemanager.googleapis.com/Project",
      "cloudresourcemanager.googleapis.com/TagBinding",
      "cloudresourcemanager.googleapis.com/TagKey",
      "cloudresourcemanager.googleapis.com/TagValue"
    ]
  }
  secops_assets_config = var.secops_ingestion_config.ingest_assets_data ? {
    for k, v in var.secops_ingestion_config.assets_data_config : k => {
      asset_types     = v.override_asset_types == null ? local.secops_to_gcp_assets_mapping[k] : v.override_asset_types
      pubsub_topic_id = module.cai-pubsub-topics[k].id
    } if v.enabled
  } : {}
  cai_feeds_id = {
    for key, value in restful_resource.cai_feeds : key =>
    [
      for feed in jsondecode(value.output).feeds :
      element(split("/", feed.name), length(split("/", feed.name)) - 1)
      if try(feed.displayName == lower(key), false)
    ][0]
  }
  cai_feeds_secret = {
    for key, value in restful_operation.cai_feeds_secret : key => jsondecode(value.output).secret
  }
  cai_function_config = {
    NODES                = try([for k, v in var.tenant_nodes.folders : v.folder_id], [])
    secops_ASSETS_CONFIG = local.secops_assets_config
    CONTENT_TYPE         = "RESOURCE"
    PAGE_SIZE            = 1000
    ORG_ID               = try(var.organization_id, "")
  }
}

module "cai-to-secops-pubsub-sa" {
  count      = var.secops_ingestion_config.ingest_assets_data ? 1 : 0
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/iam-service-account"
  project_id = module.project.project_id
  name       = "cai-to-secops-pubsub"
}

module "cai-to-secops-scheduler-sa" {
  count      = var.secops_ingestion_config.ingest_assets_data ? 1 : 0
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/iam-service-account"
  project_id = module.project.project_id
  name       = "cai-to-secops-scheduler"
}

module "cai-pubsub-topics" {
  source = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/pubsub"
  for_each = var.secops_ingestion_config.ingest_assets_data ? {
    for k, v in var.secops_ingestion_config.assets_data_config : k => v
    if v.enabled
  } : {}
  project_id = module.project.project_id
  name       = "secops_topic_${lower(each.key)}"
  iam = {
    "roles/pubsub.publisher" = ["serviceAccount:${module.cai-to-secops.0.service_account_email}"]
  }
  subscriptions = {
    (lower(each.key)) = {
      push = {
        endpoint   = "https://${var.secops_tenant_config.region}-secops.googleapis.com/v1alpha/projects/${module.project.number}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/feeds/${local.cai_feeds_id[each.key]}:importPushLogs${var.secops_ingestion_config.ingest_feed_type == "HTTPS_PUSH_WEBHOOK" ? format("?key=%s&secret=%s", google_apikeys_key.feed_api_key.key_string, local.cai_feeds_secret[each.key]) : ""}"
        attributes = {}
        no_wrapper = var.secops_ingestion_config.ingest_feed_type == "HTTPS_PUSH_GOOGLE_CLOUD_PUBSUB" ? false : true
        oidc_token = var.secops_ingestion_config.ingest_feed_type == "HTTPS_PUSH_GOOGLE_CLOUD_PUBSUB" ? {
          service_account_email = module.cai-to-secops-pubsub-sa.0.email
        } : null
      }
    }
  }
}

resource "restful_resource" "cai_feeds" {
  for_each = var.secops_ingestion_config.ingest_assets_data ? {
    for k, v in var.secops_ingestion_config.assets_data_config : k => v
    if v.enabled
  } : {}
  path            = local.secops_feeds_api_path
  create_method   = "POST"
  delete_method   = "DELETE"
  check_existance = false
  delete_path     = "$query_unescape(body.name)"
  read_selector   = "feeds.#(displayName==\"${lower(each.key)}\")"
  body = {
    name: lower(each.key),
    display_name: lower(each.key),
    details: merge({
      feed_source_type: var.secops_ingestion_config.ingest_feed_type,
      log_type: "projects/${module.project.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/logTypes/${each.key}",
      }, var.secops_ingestion_config.ingest_feed_type == "HTTPS_PUSH_GOOGLE_CLOUD_PUBSUB" ?
    { https_push_google_cloud_pubsub_settings : {} } : { httpsPushWebhookSettings : {} })
  }
  write_only_attrs = ["details"]
}

resource "restful_operation" "cai_feeds_secret" {
  for_each = var.secops_ingestion_config.ingest_assets_data ? {
    for k, v in var.secops_ingestion_config.assets_data_config : k => v
    if v.enabled && var.secops_ingestion_config.ingest_feed_type == "HTTPS_PUSH_WEBHOOK"
  } : {}
  path   = "${local.secops_feeds_api_path}/${local.cai_feeds_id[each.key]}:generateSecret"
  method = "POST"
}

module "cai-to-secops" {
  count                  = var.secops_ingestion_config.ingest_assets_data ? 1 : 0
  source                 = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/cloud-function-v2"
  project_id             = module.project.project_id
  region                 = var.regions.primary
  name                   = "cai-to-secops"
  bucket_name            = "${module.project.project_id}-cai-cf-source"
  service_account_create = true
  ingress_settings       = "ALLOW_INTERNAL_AND_GCLB"
  build_worker_pool      = google_cloudbuild_worker_pool.dev_private_pool.0.id
  build_service_account  = module.cloudbuild-sa.0.id
  bucket_config = {
    lifecycle_delete_age_days = 1
  }
  bundle_config = {
    path = "${path.module}/source/cai_to_pubsub_function"
  }
  environment_variables = {
    PIP_DISABLE_PIP_VERSION_CHECK = "True"
    LOG_EXECUTION_ID              = "true"
  }
  iam = {
    "roles/run.invoker" = [
      "serviceAccount:${module.cai-to-secops-scheduler-sa.0.email}"
    ]
  }
}

resource "google_cloud_scheduler_job" "cai_job" {
  count            = var.secops_ingestion_config.ingest_assets_data ? 1 : 0
  project          = module.project.project_id
  name             = "cai_to_secops_siem"
  description      = "Call cloud function to export CAI data to secops"
  schedule         = "0 * * * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "320s"
  region           = var.regions.secondary
  retry_config {
    retry_count = 1
  }
  http_target {
    http_method = "POST"
    uri         = module.cai-to-secops.0.uri
    body        = base64encode(jsonencode(local.cai_function_config))
    headers     = { "Content-Type" : "application/json" }
    oidc_token {
      service_account_email = module.cai-to-secops-scheduler-sa.0.email
      audience              = module.cai-to-secops.0.uri
    }
  }
}

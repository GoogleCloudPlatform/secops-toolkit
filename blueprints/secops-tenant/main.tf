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

# tfdoc:file:description Project and IAM.

locals {
  secops_api_key_secret_key    = "secops-feeds-api-key"
  secops_workspace_int_sa_key  = "secops-workspace-ing-sa-key"
  secops_feeds_api_path        = "projects/${module.project.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/feeds"
  bootstrap_log_integration    = var.tenant_nodes.include_org == true || try(length(var.tenant_nodes.folders), 0) != 0
  bootstrap_secops_integration = var.secops_ingestion_config.ingest_assets_data || var.secops_ingestion_config.ingest_scc_findings || local.bootstrap_log_integration || var.secops_ingestion_config.ingest_workspace_data
}

module "organization" {
  count           = var.tenant_nodes.include_org ? 1 : 0
  source          = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/organization"
  organization_id = "organizations/${var.organization_id}"
  logging_sinks = {
    for k, v in local.logging_sink : lower(k) => {
      destination      = module.pubsub-gcp-logs-topics[k].id
      filter           = v.filter
      include_children = true
      type             = v.type
    }
  }
}

module "folders" {
  for_each      = coalesce(var.tenant_nodes.folders, {})
  source        = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/folder"
  id            = each.value.folder_id
  folder_create = false
  logging_sinks = {
    for k, v in local.logging_sink : lower(k) => {
      destination      = module.pubsub-gcp-logs-topics[k].id
      filter           = v.filter
      include_children = true
      type             = v.type
    }
  }
  iam = var.secops_ingestion_config.ingest_assets_data ? {
    "roles/cloudasset.viewer" = [
      "serviceAccount:${module.cai-to-secops[0].service_account_email}"
    ]
  } : {}
}

module "project" {
  source          = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/project"
  name            = var.project_id
  billing_account = try(var.project_create_config.billing_account, null)
  parent          = try(var.project_create_config.parent, null)
  project_reuse   = var.project_create_config != null ? null : {}
  org_policies = var.secops_ingestion_config.ingest_workspace_data ? {
    "iam.disableServiceAccountKeyCreation" = {
      rules = [{ enforce = false }]
    }
  } : {}
  services = concat([
    "apikeys.googleapis.com",
    "compute.googleapis.com",
    "iap.googleapis.com",
    "secretmanager.googleapis.com",
    "stackdriver.googleapis.com",
    "pubsub.googleapis.com",
    "cloudfunctions.googleapis.com",
    ],
    local.bootstrap_secops_integration ? [
      "cloudasset.googleapis.com",
      "run.googleapis.com",
      "cloudscheduler.googleapis.com",
      "cloudbuild.googleapis.com",
      "cloudresourcemanager.googleapis.com",
      "vpcaccess.googleapis.com"
    ] : [],
    var.secops_ingestion_config.ingest_workspace_data ? [
      "admin.googleapis.com",
      "alertcenter.googleapis.com"
    ] : [],
  )
  custom_roles = {
    "secopsDashboardViewer" = [
      "chronicle.dashboardCharts.get",
      "chronicle.dashboardCharts.list",
      "chronicle.dashboardQueries.execute",
      "chronicle.dashboardQueries.get",
      "chronicle.dashboardQueries.list",
      "chronicle.dashboards.get",
      "chronicle.dashboards.list",
      "chronicle.dashboards.schedule",
      "chronicle.nativeDashboards.get",
      "chronicle.nativeDashboards.list"
    ]
    "secopsDataViewer" = [
      "chronicle.legacies.legacyFindRawLogs",
      "chronicle.legacies.legacySearchRawLogs",
      "chronicle.referenceLists.get",
      "chronicle.referenceLists.update"
    ]
    "secopsIngestion" = [
      "chronicle.logs.import"
    ]
  }
  iam = merge(
    {
      "roles/pubsub.publisher" = concat(
        try([for identity in module.organization[0].sink_writer_identities : identity], []),
        try(flatten([for k, v in module.folders : [for identity in v.sink_writer_identities : identity]]), [])
      )
      "roles/chronicle.viewer" = compact(concat(
        [for group in var.secops_group_principals.viewers : "group:${group}"]
      ))
    },
    local.bootstrap_secops_integration ? {
      "roles/artifactregistry.writer" = ["serviceAccount:${module.cloudbuild-sa[0].email}"]
      "roles/storage.objectAdmin"     = ["serviceAccount:${module.cloudbuild-sa[0].email}"]
      "roles/logging.logWriter"       = ["serviceAccount:${module.cloudbuild-sa[0].email}"]
    } : {}
  )
  iam_bindings_additive = merge(
    { for group in var.secops_group_principals.admins :
    "${group}-admins" => { member = "group:${group}", role = "roles/chronicle.admin" } },
    { for group in var.secops_group_principals.editors :
    "${group}-editors" => { member = "group:${group}", role = "roles/chronicle.editor" } },
    { for group in var.secops_group_principals.editors :
    "${group}-viewers" => { member = "group:${group}", role = "roles/chronicle.viewer" } },
    { for k, v in var.secops_iam :
      k => {
        member = k
        role   = "roles/chronicle.restrictedDataAccess"
        condition = {
          expression  = join(" || ", [for scope in v.scopes : "resource.name.endsWith('/${scope}')"])
          title       = "datarbac"
          description = "datarbac"
        }
      }
  })
  iam_by_principals_additive = { for k, v in var.secops_iam : k => v.roles }
}

module "vpc" {
  count       = local.bootstrap_secops_integration ? 1 : 0
  source      = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/net-vpc"
  project_id  = module.project.project_id
  name        = "secops-vpc"
  subnets     = []
  subnets_psc = []
  create_googleapis_routes = {
    private    = true
    restricted = true
  }
  psa_configs = [{
    ranges        = { cloudbuild = var.network_config.cloud_build_ip_range }
    export_routes = true
    import_routes = true
  }]
}

resource "google_vpc_access_connector" "connector" {
  count         = var.secops_ingestion_config.ingest_assets_data || var.secops_ingestion_config.ingest_scc_findings ? 1 : 0
  project       = module.project.project_id
  name          = "connector"
  region        = var.regions.primary
  ip_cidr_range = var.network_config.functions_connector_ip_range
  network       = module.vpc[0].self_link
}

module "cloudbuild-sa" {
  count      = local.bootstrap_secops_integration ? 1 : 0
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/iam-service-account"
  project_id = module.project.project_id
  name       = "cloudbuild"
}

resource "google_cloudbuild_worker_pool" "dev_private_pool" {
  count    = local.bootstrap_secops_integration ? 1 : 0
  project  = module.project.project_id
  name     = "shared-private-pool"
  location = var.regions.primary
  worker_config {
    disk_size_gb   = 100
    machine_type   = "e2-standard-4"
    no_external_ip = false
  }
  network_config {
    peered_network          = module.vpc[0].id
    peered_network_ip_range = var.network_config.cloud_build_ip_range
  }
}

resource "google_apikeys_key" "feed_api_key" {
  project      = module.project.project_id
  name         = "secops-feed-key"
  display_name = "SecOps Feeds API Key"

  restrictions {
    api_targets {
      service = "chronicle.googleapis.com"
    }
  }
}

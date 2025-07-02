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
  scc_secops_data_type = {
    GCP_SECURITYCENTER_MISCONFIGURATION = {
      scc_finding_class = "MISCONFIGURATION"
    }
    GCP_SECURITYCENTER_OBSERVATION = {
      scc_finding_class = "OBSERVATION"
    }
    GCP_SECURITYCENTER_THREAT = {
      scc_finding_class = "THREAT"
    }
    GCP_SECURITYCENTER_VULNERABILITY = {
      scc_finding_class = "VULNERABILITY"
    }
  }
  scc_tenant_query = join(" OR ", concat(
    [
      for k, v in var.tenant_nodes.folders :
      "resource.folders.resource_folder:\"${split("/", v.folder_id)[1]}\""
    ],
    var.tenant_nodes.include_org ? [
      "resource.type:\"google.cloud.resourcemanager.Organization\""
    ] : []
  ))
}

module "scc-to-secops-scheduler-sa" {
  count      = var.secops_ingestion_config.ingest_scc_findings ? 1 : 0
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/iam-service-account"
  project_id = module.project.project_id
  name       = "scc-to-secops-scheduler"
}

module "pubsub-gcp-scc-topics" {
  for_each   = try(var.secops_ingestion_config.ingest_scc_findings, false) == true ? local.scc_secops_data_type : {}
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/pubsub"
  project_id = module.project.project_id
  name       = "gcp_scc_${lower(each.value.scc_finding_class)}"
  subscriptions = {
    ("sub_gcp_scc_${lower(each.value.scc_finding_class)}") = {
      iam = {
        "roles/pubsub.subscriber" = [
          "serviceAccount:${module.scc-to-secops[0].service_account_email}"
        ]
      }
    }
  }
}

resource "google_scc_notification_config" "scc_notification_configs" {
  for_each     = try(var.secops_ingestion_config.ingest_scc_findings, false) == true ? local.scc_secops_data_type : {}
  config_id    = "cs-${module.project.project_id}-${lower(each.value.scc_finding_class)}"
  organization = try(var.organization_id, null)
  description  = "SCC ${lower(each.value.scc_finding_class)} Notifications"
  pubsub_topic = module.pubsub-gcp-scc-topics[each.key].id

  streaming_config {
    filter = "state=\"ACTIVE\" AND NOT mute=\"MUTED\" AND finding_class=\"${each.value.scc_finding_class}\" AND (${local.scc_tenant_query})"
  }
}

module "scc-to-secops" {
  count                  = var.secops_ingestion_config.ingest_scc_findings ? 1 : 0
  source                 = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/cloud-function-v2"
  project_id             = module.project.project_id
  region                 = var.regions.primary
  name                   = "scc-to-secops"
  bucket_name            = "${var.project_id}-cf-source"
  service_account_create = true
  ingress_settings       = "ALLOW_INTERNAL_AND_GCLB"
  build_worker_pool      = google_cloudbuild_worker_pool.dev_private_pool[0].id
  build_service_account  = module.cloudbuild-sa[0].id
  bucket_config = {
    lifecycle_delete_age_days = 1
  }
  bundle_config = {
    path = "${path.module}/source/scc_to_secops_function"
  }
  environment_variables = {
    PROJECT_ID         = module.project.project_id
    SECOPS_CUSTOMER_ID = local.secops_customer_id
    SECOPS_REGION      = var.secops_tenant_config.region
  }
  secrets = {}
  iam = {
    "roles/run.invoker" = [
      "serviceAccount:${module.scc-to-secops-scheduler-sa[0].email}"
    ]
  }
  vpc_connector = {
    create          = false
    name            = google_vpc_access_connector.connector[0].id
    egress_settings = "ALL_TRAFFIC"
  }
}

resource "google_cloud_scheduler_job" "scc_jobs" {
  for_each         = var.secops_ingestion_config.ingest_scc_findings ? local.scc_secops_data_type : {}
  project          = module.project.project_id
  name             = "scc_${lower(each.value.scc_finding_class)}_to_secops_siem"
  description      = "Call cloud function to export SCC ${lower(each.value.scc_finding_class)} to SecOps"
  schedule         = "*/5 * * * *"
  time_zone        = "Etc/UTC"
  attempt_deadline = "320s"
  region           = var.regions.primary
  retry_config {
    retry_count = 1
  }
  http_target {
    http_method = "POST"
    uri         = module.scc-to-secops[0].uri
    body        = base64encode("{\"SUBSCRIPTION_ID\":\"${join("", ["sub_gcp_scc_", lower(each.value.scc_finding_class)])}\", \"SECOPS_DATA_TYPE\": \"${each.key}\"}")
    headers     = { "Content-Type" : "application/json" }
    oidc_token {
      service_account_email = module.scc-to-secops-scheduler-sa[0].email
      audience              = module.scc-to-secops[0].uri
    }
  }
}

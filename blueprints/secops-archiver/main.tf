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

module "project" {
  source          = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/project"
  name            = var.project_id
  billing_account = try(var.project_create_config.billing_account, null)
  parent          = try(var.project_create_config.parent, null)
  project_reuse   = var.project_create_config != null ? null : {}
  services = concat([
    "cloudfunctions.googleapis.com",
    "secretmanager.googleapis.com",
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "vpcaccess.googleapis.com",
    "dlp.googleapis.com",
    "vpcaccess.googleapis.com"
  ])
  iam = {
    "roles/dlp.reader"                        = [module.function.service_account_iam_email]
    "roles/dlp.jobsEditor"                    = [module.function.service_account_iam_email]
    "roles/serviceusage.serviceUsageConsumer" = [module.function.service_account_iam_email]
    "roles/chronicle.editor"                  = [module.function.service_account_iam_email]
  }
  iam_bindings_additive = {
    function-log-writer = {
      member = module.function.service_account_iam_email
      role   = "roles/logging.logWriter"
    }
    function-storage-admin = {
      member = module.project.service_agents.gcf-admin-robot.iam_email
      role   = "roles/storage.admin"
    }
    function-artifact-reader = {
      member = module.project.service_agents.gcf-admin-robot.iam_email
      role   = "roles/artifactregistry.reader"
    }
  }
}

module "export-bucket" {
  source        = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/gcs"
  project_id    = module.project.project_id
  name          = "secops-data-archiver"
  prefix        = var.prefix
  location      = var.regions.primary
  storage_class = "REGIONAL"
  versioning    = true
  iam = {
    "roles/storage.legacyBucketReader" = [
      "user:malachite-data-export-batch@prod.google.com",
      module.function.service_account_iam_email
    ]
    "roles/storage.objectAdmin" = [
      "user:malachite-data-export-batch@prod.google.com",
      module.function.service_account_iam_email
    ]
    "roles/storage.objectViewer" = [module.function.service_account_iam_email]
  }
}

module "function" {
  source                 = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/cloud-function-v2"
  project_id             = module.project.project_id
  region                 = var.regions.primary
  prefix                 = var.prefix
  name                   = "secops-archiver"
  bucket_name            = "${var.project_id}-archiver"
  service_account_create = true
  ingress_settings       = "ALLOW_INTERNAL_AND_GCLB"
  build_worker_pool      = var.cloud_function_config.build_worker_pool_id
  build_service_account  = var.cloud_function_config.build_sa != null ? var.cloud_function_config.build_sa : module.cloudbuild-sa[0].id
  bucket_config = {
    lifecycle_delete_age_days = 1
  }
  bundle_config = {
    path = "${path.module}/source"
  }
  environment_variables = merge({
    GCP_PROJECT        = module.project.project_id
    SECOPS_PROJECT_ID  = var.secops_config.gcp_project
    SECOPS_CUSTOMER_ID = var.secops_config.customer_id
    SECOPS_REGION      = var.secops_config.region
    GCS_BUCKET         = module.export-bucket.name
  })
  function_config = {
    cpu             = var.cloud_function_config.cpu
    memory_mb       = var.cloud_function_config.memory_mb
    timeout_seconds = var.cloud_function_config.timeout_seconds
  }
  iam = {
    "roles/run.invoker" = [
      "serviceAccount:${module.scheduler-sa.email}"
    ]
  }
  secrets = {}
  vpc_connector = (
    var.cloud_function_config.vpc_connector == null
    ? {}
    : {
      create          = false
      name            = var.cloud_function_config.vpc_connector.name
      egress_settings = var.cloud_function_config.vpc_connector.egress_settings
    }
  )
}

module "cloudbuild-sa" {
  count      = var.cloud_function_config.build_sa == null ? 1 : 0
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/iam-service-account"
  project_id = module.project.project_id
  name       = "cloudbuild"
  iam_project_roles = {
    (module.project.project_id) = [
      "roles/logging.logWriter",
      "roles/monitoring.metricWriter",
      "roles/artifactregistry.writer",
      "roles/storage.objectAdmin"
    ]
  }
}

module "scheduler-sa" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/iam-service-account"
  project_id = module.project.project_id
  name       = "secops-scheduler"
}

resource "google_cloud_scheduler_job" "anonymization_jobs" {
  for_each         = var.schedule_config
  project          = module.project.project_id
  name             = "secops-${each.key}"
  description      = "Trigger SecOps Data Export job."
  schedule         = each.value.schedule
  time_zone        = "Etc/UTC"
  attempt_deadline = "320s"
  region           = var.regions.secondary
  retry_config {
    retry_count = 1
  }
  http_target {
    http_method = "POST"
    uri         = module.function.uri
    body = base64encode(jsonencode({
      ACTION    = upper(each.value.action)
      LOG_TYPES = each.value.log_types
    }))
    headers = { "Content-Type" : "application/json" }
    oidc_token {
      service_account_email = module.scheduler-sa.email
      audience              = module.function.uri
    }
  }
  lifecycle {
    ignore_changes = [
      http_target
    ]
  }
}

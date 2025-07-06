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
  secops_api_key_secret_key   = "secops-feeds-api-key"
  secops_workspace_int_sa_key = "secops-workspace-ing-sa-key"
  secops_feeds_api_path       = "projects/${module.project.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/feeds"
}

module "project" {
  source          = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/project"
  name            = var.project_id
  billing_account = try(var.project_create_config.billing_account, null)
  parent          = try(var.project_create_config.parent, null)
  project_reuse   = var.project_create_config != null ? null : {}
  org_policies = var.third_party_integration_config.workspace == null ? {} : {
    "iam.disableServiceAccountKeyCreation" = {
      rules = [{ enforce = false }]
    }
  }
  services = concat([
    "apikeys.googleapis.com",
    "compute.googleapis.com",
    "iap.googleapis.com",
    "secretmanager.googleapis.com",
    "stackdriver.googleapis.com",
    "pubsub.googleapis.com",
    "cloudfunctions.googleapis.com",
    ],
    var.third_party_integration_config.workspace == null ? [] : [
      "admin.googleapis.com",
      "alertcenter.googleapis.com"
    ]
  )
  custom_roles = {}
  iam = {
    "roles/chronicle.viewer" = compact(concat(
      [for group in var.secops_group_principals.viewers : "group:${group}"]
    ))
  }
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

resource "google_apikeys_key" "feed_api_key" {
  count        = length(var.webhook_feeds_config) == 0 ? 0 : 1
  project      = module.project.project_id
  name         = "secops-feeds-key"
  display_name = "SecOps Feeds API Key"

  restrictions {
    api_targets {
      service = "chronicle.googleapis.com"
    }
  }
}


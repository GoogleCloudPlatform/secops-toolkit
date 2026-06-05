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

# tfdoc:file:description Project and APIs.

module "secops_folder" {
  count  = try(var.project_create_config.bootstrap_folder, false) ? 1 : 0
  source = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/folder"
  parent = "organizations/${var.organization_id}"
  name   = "SecOps"
}

module "project" {
  source          = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/project"
  name            = var.project_id
  billing_account = try(var.project_create_config.billing_account, null)
  parent          = try(var.project_create_config.bootstrap_folder, false) ? module.secops_folder[0].name : try(var.project_create_config.parent, null)
  project_reuse   = var.project_create_config != null ? null : {}
  org_policies    = {
    "iam.disableServiceAccountKeyCreation" = {
      rules = [{ enforce = false }]
    }
  }
  services = [
    "chronicle.googleapis.com",
    "essentialcontacts.googleapis.com"
  ]
  contacts = {
    for email in var.essential_contacts: email => ["ALL"]
  }
}

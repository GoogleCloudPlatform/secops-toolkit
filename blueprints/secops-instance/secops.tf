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

module "secops-data-rbac" {
  source = "../../modules/secops-data-rbac"
  secops_config = {
    customer_id = var.secops_tenant_config.customer_id
    project     = module.project.project_id
    region      = var.secops_tenant_config.region
  }
  labels = var.secops_data_rbac_config.labels
  scopes = var.secops_data_rbac_config.scopes
}

module "secops-rules" {
  source = "../../modules/secops-rules"
  secops_config = {
    customer_id = var.secops_tenant_config.customer_id
    project     = module.project.project_id
    region      = var.secops_tenant_config.region
  }
  factories_config = {
    rules                = "./data/secops_rules.yaml"
    rules_defs           = "./data/rules"
    reference_lists      = "./data/secops_reference_lists.yaml"
    reference_lists_defs = "./data/reference_lists"
  }
}

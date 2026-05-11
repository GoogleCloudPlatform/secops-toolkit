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

# ==============================================================================
# RESOURCE: SECOPS CASE STAGES 
# ==============================================================================
resource "restful_resource" "secops_case_stage" {
  for_each = var.secops_case_stages

  create_method = "POST"
  path          = "/projects/${var.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/caseStageDefinitions"

  read_path = "/projects/${var.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/caseStageDefinitions/$base(body.name)"

  update_method = "PATCH"
  update_path   = "/projects/${var.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/caseStageDefinitions/$base(body.name)?updateMask=displayName,order"

  delete_method = "DELETE"
  delete_path   = "/projects/${var.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/caseStageDefinitions/$base(body.name)"

  force_new_attrs = [
    "displayName",
    "order"
  ]

  body = {
    displayName = each.value.display_name
    order       = each.value.order
  }
}
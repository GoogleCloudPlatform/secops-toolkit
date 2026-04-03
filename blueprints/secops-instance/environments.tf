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
# RESOURCE: SECOPS ENVIRONMENTS 
# ==============================================================================
resource "restful_resource" "secops_environment" {
  for_each = var.secops_envs

  create_method = "POST"
  path          = "/projects/${var.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/environments"

  read_path = "/projects/${var.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/environments/$base(body.name)"

  update_method = "PATCH"
  update_path   = "/projects/${var.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/environments/$base(body.name)?updateMask=displayName,description,contact,contactEmails,contactPhone,instanceUri,aliasesJson,retentionDuration"

  delete_method = "DELETE"
  delete_path   = "/projects/${var.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/environments/$base(body.name)"

  body = {
    displayName       = each.value.display_name
    description       = each.value.description
    contact           = each.value.contact
    contactEmails     = each.value.contact_email
    contactPhone      = each.value.contact_phone
    retentionDuration = each.value.retention_duration
    instanceUri       = each.value.instance_uri
    aliasesJson       = jsonencode(each.value.aliases)
  }
}
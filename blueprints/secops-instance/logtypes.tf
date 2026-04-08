/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

# ==============================================================================
# RESOURCE: SECOPS LOG TYPES 
# ==============================================================================
resource "restful_resource" "secops_log_type" {
  for_each = var.secops_custom_logtypes

  create_method = "POST"
  path          = "/projects/${var.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}/logTypes?logTypeId=${each.key}"

  read_path = "/projects/${var.project_id}/locations/${var.secops_tenant_config.region}/instances/${var.secops_tenant_config.customer_id}"

  body = {
    customLogTypeLabel = each.value.log_type_label
    displayName        = each.value.display_name
    productSource      = each.value.product_source
    isCustom           = each.value.is_custom
    hasCustomParser    = each.value.has_custom_parser
  }

  lifecycle {
    prevent_destroy = true
    ignore_changes = [
      body
    ]
  }
}
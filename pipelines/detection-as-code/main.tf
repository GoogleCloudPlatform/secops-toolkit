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
  reference_lists = yamldecode(file("${path.module}/${var.secops_content_config.reference_lists}"))
  reference_list_type_mapping = {
    STRING = "REFERENCE_LIST_SYNTAX_TYPE_PLAIN_TEXT_STRING"
    REGEX  = "REFERENCE_LIST_SYNTAX_TYPE_REGEX"
    CIDR   = "REFERENCE_LIST_SYNTAX_TYPE_CIDR"
  }
  secops_rules = {
    for file_name in fileset("${path.module}/rules", "*.yaral") : replace(file_name, ".yaral", "") => file("${path.module}/rules/${file_name}")
  }
  secops_rule_deployment = yamldecode(file("${path.module}/${var.secops_content_config.rules}"))
  secops_parent = "projects/${var.secops_project_id}/locations/${var.secops_region}/instances/${var.secops_customer_id}"
}

resource "google_chronicle_reference_list" "reference_list" {
  for_each          = local.reference_lists
  project           = var.secops_project_id
  location          = var.secops_region
  instance          = var.secops_customer_id
  reference_list_id = each.key
  description       = each.value.description
  dynamic "scope_info" {
    for_each = length(try(each.value.scopes, [])) > 0 ? [""] : []
    content {
      reference_list_scope {
        scope_names = [for scope in each.value.scopes: "${local.secops_parent}/dataAccessScopes/${scope}"]
      }
    }
  }
  dynamic "entries" {
    for_each = toset(split("\n", file("${path.module}/reference_lists/${each.key}.txt")))
    content {
      value = entries.value
    }
  }
  syntax_type = local.reference_list_type_mapping[each.value.type]
}

resource "google_chronicle_rule" "rule" {
  for_each        = local.secops_rule_deployment
  project         = var.secops_project_id
  location        = var.secops_region
  instance        = var.secops_customer_id
  deletion_policy = "FORCE"
  text            = local.secops_rules[each.key]
  scope           = try("${local.secops_parent}/dataAccessScopes/${each.value.scope}", null)
  depends_on = [
    google_chronicle_reference_list.reference_list
  ]
}

resource "google_chronicle_rule_deployment" "rule_deployment" {
  for_each      = local.secops_rule_deployment
  project       = var.secops_project_id
  location      = var.secops_region
  instance      = var.secops_customer_id
  rule          = google_chronicle_rule.rule[each.key].rule_id
  enabled       = each.value.enabled
  alerting      = each.value.alerting
  archived      = each.value.archived
  run_frequency = each.value.run_frequency
}

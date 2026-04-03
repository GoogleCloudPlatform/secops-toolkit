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

locals {
  data_tables = try(yamldecode(file(var.secops_content_config.data_tables)), {})
  data_tables_csv = {
    for k, v in local.data_tables : k => csvdecode(file("${path.module}/data_tables/${k}.csv"))
    if fileexists("${path.module}/data_tables/${k}.csv")
  }
  flattened_rows = flatten([
    for table_id, rows in local.data_tables_csv : [
      for i, row in rows : {
        key      = "${table_id}_${i}"
        table_id = table_id
        ttl      = try(local.data_tables[table_id].row_time_to_live, null)
        values = [
          for col in local.data_tables[table_id].columns : row[col.original_column]
        ]
      }
    ]
  ])
  reference_lists = try(yamldecode(file("${path.module}/${var.secops_content_config.reference_lists}")), toset([]))
  reference_list_type_mapping = {
    STRING = "REFERENCE_LIST_SYNTAX_TYPE_PLAIN_TEXT_STRING"
    REGEX  = "REFERENCE_LIST_SYNTAX_TYPE_REGEX"
    CIDR   = "REFERENCE_LIST_SYNTAX_TYPE_CIDR"
  }
  secops_rules = {
    for file_name in fileset("${path.module}/rules", "*.yaral") : replace(file_name, ".yaral", "") => file("${path.module}/rules/${file_name}")
  }
  secops_rule_deployment = yamldecode(file(var.secops_content_config.rules))
  secops_parent          = "projects/${var.secops_project_id}/locations/${var.secops_region}/instances/${var.secops_customer_id}"
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
        scope_names = [for scope in each.value.scopes : "${local.secops_parent}/dataAccessScopes/${scope}"]
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
    google_chronicle_reference_list.reference_list,
    google_chronicle_data_table.data_table
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

resource "google_chronicle_data_table" "data_table" {
  provider      = google-beta
  for_each      = local.data_tables
  project       = var.secops_project_id
  location      = var.secops_region
  instance      = var.secops_customer_id
  data_table_id = each.key
  description   = each.value.description

  dynamic "scope_info" {
    for_each = length(try(each.value.scopes, [])) > 0 ? [""] : []
    content {
      data_access_scopes = [for scope in each.value.scopes : "${local.secops_parent}/dataAccessScopes/${scope}"]
    }
  }

  dynamic "column_info" {
    for_each = try(each.value.columns, [])
    content {
      column_index       = index(each.value.columns, column_info.value)
      column_type        = try(column_info.value.column_type, null)
      key_column         = try(column_info.value.key_column, null)
      mapped_column_path = try(column_info.value.mapped_column_path, null)
      original_column    = column_info.value.original_column
      repeated_values    = try(column_info.value.repeated_values, null)
    }
  }
}

resource "google_chronicle_data_table_row" "data_table_row" {
  provider         = google-beta
  for_each         = { for r in local.flattened_rows : r.key => r }
  project          = var.secops_project_id
  location         = var.secops_region
  instance         = var.secops_customer_id
  data_table_id    = each.value.table_id
  values           = each.value.values
  row_time_to_live = each.value.ttl

  depends_on = [google_chronicle_data_table.data_table]
  lifecycle {
    ignore_changes = all
  }
}

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
  secops_rules = {
    for file_name in fileset("${path.module}/rules", "*.yaral") : replace(file_name, ".yaral", "") => file("${path.module}/rules/${file_name}")
  }
  secops_parent         = "projects/${var.secops_project_id}/locations/${var.secops_region}/instances/${var.secops_customer_id}"
  _raw_rule_deployments = yamldecode(file(var.secops_content_config.rules))
  secops_rule_deployment = {
    for k in try(keys(local._raw_rule_deployments), []) : k => {
      enabled       = tobool(try(local._raw_rule_deployments[k].enabled, true))
      alerting      = tobool(try(local._raw_rule_deployments[k].alerting, false))
      archived      = tobool(try(local._raw_rule_deployments[k].archived, false))
      run_frequency = try(tostring(local._raw_rule_deployments[k].run_frequency), tostring(null))
      scope = try(local._raw_rule_deployments[k].scope, null) != null ? (
        startswith(local._raw_rule_deployments[k].scope, "projects/")
        ? tostring(local._raw_rule_deployments[k].scope)
        : "${local.secops_parent}/dataAccessScopes/${local._raw_rule_deployments[k].scope}"
      ) : tostring(null)
      tags = try(local._raw_rule_deployments[k].tags, null) != null ? try(
        [for t in local._raw_rule_deployments[k].tags : tostring(t)],
        ["__INVALID_TAGS_TYPE__"]
      ) : null
      schedule_customizations = try(local._raw_rule_deployments[k].schedule_customizations, null) != null ? {
        ensure_enrichment_completeness = try(
          tobool(local._raw_rule_deployments[k].schedule_customizations.ensure_enrichment_completeness),
          tobool(null)
        )
        late_arriving_data_adjustment = try(
          tostring(local._raw_rule_deployments[k].schedule_customizations.late_arriving_data_adjustment),
          tostring(null)
        )
      } : null
    }
  }
}

resource "google_chronicle_rule" "rule" {
  for_each        = local.secops_rule_deployment
  project         = var.secops_project_id
  location        = var.secops_region
  instance        = var.secops_customer_id
  deletion_policy = "FORCE"
  text            = try(local.secops_rules[each.key], null)
  scope           = each.value.scope
  depends_on = [
    google_chronicle_data_table.data_table
  ]

  lifecycle {
    precondition {
      condition     = contains(keys(local.secops_rules), each.key)
      error_message = "Rule '${each.key}' is defined in '${var.secops_content_config.rules}', but 'rules/${each.key}.yaral' does not exist."
    }
    precondition {
      condition = each.value.tags == null || alltrue([
        for tag in coalesce(each.value.tags, []) :
        can(regex("^(projects/[^/]+/locations/[^/]+/instances/[^/]+/tags/)?([a-zA-Z][a-zA-Z0-9_]{0,98}|google\\.[a-zA-Z0-9][a-zA-Z0-9._-]*)$", tag))
      ])
      error_message = "Rule '${each.key}': 'tags' must be a list of valid custom tag IDs, Google-managed 'google.*' tag IDs, or full 'projects/.../tags/...' resource names."
    }
  }
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

  dynamic "schedule_customizations" {
    for_each = each.value.schedule_customizations != null ? [each.value.schedule_customizations] : []
    content {
      ensure_enrichment_completeness = schedule_customizations.value.ensure_enrichment_completeness
      late_arriving_data_adjustment  = schedule_customizations.value.late_arriving_data_adjustment
    }
  }

  lifecycle {
    precondition {
      condition = each.value.run_frequency == null || contains([
        "LIVE",
        "HOURLY",
        "DAILY",
        "LIVE_CUSTOMIZABLE",
        "HOURLY_CUSTOMIZABLE",
      ], each.value.run_frequency)
      error_message = "Rule '${each.key}': 'run_frequency' must be null or one of LIVE, HOURLY, DAILY, LIVE_CUSTOMIZABLE, HOURLY_CUSTOMIZABLE."
    }
    precondition {
      condition = each.value.schedule_customizations == null || contains([
        "LIVE_CUSTOMIZABLE",
        "HOURLY_CUSTOMIZABLE",
      ], coalesce(each.value.run_frequency, "NONE"))
      error_message = "Rule '${each.key}': 'schedule_customizations' is only valid when 'run_frequency' is LIVE_CUSTOMIZABLE or HOURLY_CUSTOMIZABLE."
    }
    precondition {
      condition = (
        try(each.value.schedule_customizations.late_arriving_data_adjustment, null) == null ||
        can(regex("^\\d+(\\.\\d{1,9})?s$", each.value.schedule_customizations.late_arriving_data_adjustment))
      )
      error_message = "Rule '${each.key}': 'late_arriving_data_adjustment' must be a valid duration in seconds ending with 's' (e.g., '300s' or '3.5s')."
    }
    precondition {
      condition     = !each.value.archived || !each.value.enabled
      error_message = "Rule '${each.key}': rules with 'archived = true' must also set 'enabled = false'."
    }
  }
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

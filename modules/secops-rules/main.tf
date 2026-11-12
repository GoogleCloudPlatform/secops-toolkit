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
  _secops_rules_path = pathexpand(coalesce(var.factories_config.rules_defs, "-"))
  secops_parent      = "projects/${var.secops_config.project}/locations/${var.secops_config.region}/instances/${var.secops_config.customer_id}"
  reference_lists    = try(yamldecode(file(var.factories_config.reference_lists)), var.reference_lists_config)
  reference_lists_entries = {
    for k, v in local.reference_lists : k => split("\n", file("${var.factories_config.reference_lists_defs}/${k}.txt"))
  }
  reference_list_type_mapping = {
    STRING = "REFERENCE_LIST_SYNTAX_TYPE_PLAIN_TEXT_STRING"
    REGEX  = "REFERENCE_LIST_SYNTAX_TYPE_REGEX"
    CIDR   = "REFERENCE_LIST_SYNTAX_TYPE_CIDR"
  }
  secops_rules = {
    for file_name in fileset(local._secops_rules_path, "*.yaral") :
    replace(file_name, ".yaral", "") => file("${local._secops_rules_path}/${file_name}")
  }
  _raw_rule_deployments = try(yamldecode(file(var.factories_config.rules)), var.rules_config)
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

resource "google_chronicle_reference_list" "default" {
  for_each          = local.reference_lists
  project           = var.secops_config.project
  location          = var.secops_config.region
  instance          = var.secops_config.customer_id
  reference_list_id = each.key
  description       = each.value.description
  dynamic "entries" {
    for_each = local.reference_lists_entries[each.key]
    content {
      value = entries.value
    }
  }
  syntax_type = local.reference_list_type_mapping[each.value.type]
}

resource "google_chronicle_rule" "default" {
  for_each        = local.secops_rule_deployment
  project         = var.secops_config.project
  location        = var.secops_config.region
  instance        = var.secops_config.customer_id
  text            = try(local.secops_rules[each.key], null)
  scope           = each.value.scope
  deletion_policy = "FORCE"
  depends_on = [
    google_chronicle_reference_list.default
  ]

  lifecycle {
    precondition {
      condition     = contains(keys(local.secops_rules), each.key)
      error_message = "Rule '${each.key}' is defined in rules configuration, but '${each.key}.yaral' does not exist in '${local._secops_rules_path}'."
    }
  }
}

resource "google_chronicle_rule_deployment" "default" {
  for_each      = local.secops_rule_deployment
  project       = var.secops_config.project
  location      = var.secops_config.region
  instance      = var.secops_config.customer_id
  rule          = google_chronicle_rule.default[each.key].rule_id
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

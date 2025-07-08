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
  # --- Path Setup ---
  _secops_rules_path           = var.factories_config.rules_defs != null ? pathexpand(var.factories_config.rules_defs) : null
  _secops_reference_lists_path = var.factories_config.reference_lists_defs != null ? pathexpand(var.factories_config.reference_lists_defs) : null

  # --- Rule Discovery and Loading ---
  # Discover all .yaral files.
  _rule_files = local._secops_rules_path == null ? [] : fileset(local._secops_rules_path, "**/*.yaral")

  # Load rule text content. The key is the rule name derived from the filename.
  secops_rules_text = {
    for path in local._rule_files :
    replace(basename(path), ".yaral", "") => file("${local._secops_rules_path}/${path}")
  }

  # Load rule deployment config from corresponding .yaml files.
  # A rule is only considered for deployment if both its .yaral and .yaml files exist.
  secops_rule_deployment = {
    for path in local._rule_files :
    replace(basename(path), ".yaral", "") => yamldecode(
      file("${local._secops_rules_path}/${dirname(path)}/${replace(basename(path), ".yaral", ".yaml")}")
    )[replace(basename(path), ".yaral", "")]
    if fileexists("${local._secops_rules_path}/${dirname(path)}/${replace(basename(path), ".yaral", ".yaml")}")
  }

  # --- Reference List Discovery and Loading ---
  # Discover all .txt files for list entries.
  _reference_list_files = local._secops_reference_lists_path == null ? [] : fileset(local._secops_reference_lists_path, "**/*.txt")

  # Load reference list configurations from corresponding .yaml files.
  # A list is only created if both its .txt and .yaml files exist.
  secops_reference_lists = {
    for path in local._reference_list_files :
    replace(basename(path), ".txt", "") => yamldecode(
      file("${local._secops_reference_lists_path}/${dirname(path)}/${replace(basename(path), ".txt", ".yaml")}")
    )[replace(basename(path), ".txt", "")]
    if fileexists("${local._secops_reference_lists_path}/${dirname(path)}/${replace(basename(path), ".txt", ".yaml")}")
  }

  # Load reference list entries from .txt files, filtering out empty lines.
  secops_reference_lists_entries = {
    for path in local._reference_list_files :
    replace(basename(path), ".txt", "") => [
      for line in split("\n", file("${local._secops_reference_lists_path}/${path}")) : line if trimspace(line) != ""
    ]
    # Only load entries for lists that have a valid configuration.
    if lookup(local.secops_reference_lists, replace(basename(path), ".txt", ""), null) != null
  }

  # Map for human-readable types to Chronicle API types.
  reference_list_type_mapping = {
    STRING = "REFERENCE_LIST_SYNTAX_TYPE_PLAIN_TEXT_STRING"
    REGEX  = "REFERENCE_LIST_SYNTAX_TYPE_REGEX"
    CIDR   = "REFERENCE_LIST_SYNTAX_TYPE_CIDR"
  }
}

resource "google_chronicle_reference_list" "default" {
  for_each          = local.secops_reference_lists
  project           = var.secops_config.project
  location          = var.secops_config.region
  instance          = var.secops_config.customer_id
  reference_list_id = each.key
  description       = each.value.description
  dynamic "entries" {
    # Use toset to ensure entries are unique and satisfy for_each requirements.
    for_each = toset(local.secops_reference_lists_entries[each.key])
    content {
      value = entries.value
    }
  }
  syntax_type = local.reference_list_type_mapping[each.value.type]
}

resource "google_chronicle_rule" "default" {
  # Iterate over rules that have deployment configuration.
  for_each        = local.secops_rule_deployment
  project         = var.secops_config.project
  location        = var.secops_config.region
  instance        = var.secops_config.customer_id
  text            = local.secops_rules_text[each.key] # Look up the rule text from the dedicated map.
  deletion_policy = "FORCE"
  depends_on = [
    google_chronicle_reference_list.default
  ]
}

resource "google_chronicle_rule_deployment" "default" {
  for_each      = local.secops_rule_deployment
  project       = var.secops_config.project
  location      = var.secops_config.region
  instance      = var.secops_config.customer_id
  rule          = google_chronicle_rule.default[each.key].id # Reference the rule created in the previous step.
  enabled       = each.value.enabled
  alerting      = each.value.alerting
  archived      = each.value.archived
  run_frequency = each.value.run_frequency
}

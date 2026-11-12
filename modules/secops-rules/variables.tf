/**
 * Copyright 2023 Google LLC
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

variable "factories_config" {
  description = "Paths to  YAML config expected in 'rules' and 'reference_lists'. Path to folders containing rules definitions (yaral files) and reference lists content (txt files) for the corresponding _defs keys."
  type = object({
    rules                = optional(string)
    rules_defs           = optional(string, "data/rules")
    reference_lists      = optional(string)
    reference_lists_defs = optional(string, "data/reference_lists")
  })
  nullable = false
  default  = {}
}

variable "reference_lists_config" {
  description = "SecOps Reference lists configuration."
  type = map(object({
    description = string
    type        = string
  }))
  default = {}
  validation {
    condition = alltrue([
      for config in var.reference_lists_config : contains(["CIDR", "STRING", "REGEX"], config.type)
    ])
    error_message = "The 'type' attribute for each reference list must be one of: CIDR, STRING, REGEX."
  }
}

variable "rules_config" {
  description = "SecOps Detection rules configuration."
  type = map(object({
    enabled       = optional(bool, true)
    alerting      = optional(bool, false)
    archived      = optional(bool, false)
    run_frequency = optional(string)
    scope         = optional(string)
    schedule_customizations = optional(object({
      ensure_enrichment_completeness = optional(bool)
      late_arriving_data_adjustment  = optional(string)
    }))
  }))
  default = {}
  validation {
    condition = alltrue([
      for config in var.rules_config : config.run_frequency == null || contains([
        "LIVE",
        "HOURLY",
        "DAILY",
        "LIVE_CUSTOMIZABLE",
        "HOURLY_CUSTOMIZABLE",
      ], config.run_frequency)
    ])
    error_message = "The 'run_frequency' attribute for each rule must be null or one of: LIVE, HOURLY, DAILY, LIVE_CUSTOMIZABLE, HOURLY_CUSTOMIZABLE."
  }
  validation {
    condition = alltrue([
      for config in var.rules_config : config.schedule_customizations == null || contains([
        "LIVE_CUSTOMIZABLE",
        "HOURLY_CUSTOMIZABLE",
      ], coalesce(config.run_frequency, "NONE"))
    ])
    error_message = "The 'schedule_customizations' attribute is only valid when 'run_frequency' is LIVE_CUSTOMIZABLE or HOURLY_CUSTOMIZABLE."
  }
  validation {
    condition = alltrue([
      for config in var.rules_config : (
        try(config.schedule_customizations.late_arriving_data_adjustment, null) == null ||
        can(regex("^\\d+(\\.\\d{1,9})?s$", config.schedule_customizations.late_arriving_data_adjustment))
      )
    ])
    error_message = "The 'late_arriving_data_adjustment' attribute must be a valid duration in seconds ending with 's' (e.g., '300s' or '3.5s')."
  }
  validation {
    condition = alltrue([
      for config in var.rules_config : !config.archived || !config.enabled
    ])
    error_message = "Rules with 'archived = true' must also set 'enabled = false'."
  }
}

variable "secops_config" {
  description = "SecOps configuration."
  type = object({
    customer_id = string
    project     = string
    region      = string
  })
}

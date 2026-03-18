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

variable "project_id" {
  description = "The ID of the project where resources will be deployed."
  type        = string
}

variable "monitoring_config" {
  description = "Configuration for monitoring and alerting."
  type = object({
    notification_channels = optional(list(object({
      display_name = string
      type         = string
      labels       = map(string)
      enabled      = optional(bool, true)
    })), [])
  })
  default = {
    notification_channels = []
  }
}

variable "alerting_config" {
  description = "Configuration for individual alerts"
  type = object({
    secops_ingestion = optional(object({
      enabled               = optional(bool, true)
      notifications_enabled = optional(bool, false)
      threshold             = optional(number, 80)
    }), {})
    ingestion_quota_rejection = optional(object({
      enabled               = optional(bool, true)
      notifications_enabled = optional(bool, false)
    }), {})
    forwarder_buffer_usage = optional(object({
      enabled               = optional(bool, true)
      notifications_enabled = optional(bool, false)
      threshold             = optional(number, 0.01)
    }), {})
    secops_forwarder_silence = optional(object({
      enabled               = optional(bool, true)
      notifications_enabled = optional(bool, false)
      duration              = optional(string, "3600s")
    }), {})
    forwarder_log_type_silence = optional(object({
      enabled               = optional(bool, true)
      notifications_enabled = optional(bool, false)
      duration              = optional(string, "3600s")
    }), {})
    secops_normalized_events_drop = optional(object({
      enabled               = optional(bool, true)
      notifications_enabled = optional(bool, false)
      threshold             = optional(number, 50)
      duration              = optional(string, "3600s")
    }), {})
    high_latency = optional(object({
      enabled               = optional(bool, true)
      notifications_enabled = optional(bool, false)
      threshold             = optional(number, 2000)
    }), {})
    high_error_rate = optional(object({
      enabled               = optional(bool, true)
      notifications_enabled = optional(bool, false)
      threshold             = optional(number, 0.1)
    }), {})
    auth_failure = optional(object({
      enabled               = optional(bool, true)
      notifications_enabled = optional(bool, false)
      threshold             = optional(number, 5.0)
    }), {})
    secops_ingestion_quota = optional(object({
      enabled               = optional(bool, true)
      notifications_enabled = optional(bool, false)
      yearly_quota_tb       = optional(number, 1)
    }), {})
  })
  default = {}
}

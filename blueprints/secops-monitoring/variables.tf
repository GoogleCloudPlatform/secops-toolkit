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
    enabled        = optional(bool, true)
    alerts_enabled = optional(bool, false)
    notification_channels = optional(list(object({
      display_name = string
      type         = string
      labels       = map(string)
      enabled      = optional(bool, true)
    })), [])
  })
  default = {
    enabled               = true
    alerts_enabled        = false
    notification_channels = []
  }
}

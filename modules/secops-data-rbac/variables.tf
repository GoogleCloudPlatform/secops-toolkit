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

variable "labels" {
  description = "SecOps Data RBAC labels."
  type = map(object({
    description = string
    label_id    = string
    udm_query   = string
  }))
  default = {}
}

variable "scopes" {
  description = "SecOps Data RBAC scopes."
  type = map(object({
    description = string
    scope_id    = string
    allowed_data_access_labels = optional(list(object({
      data_access_label = optional(string)
      log_type          = optional(string)
      asset_namespace   = optional(string)
      ingestion_label = optional(object({
        ingestion_label_key   = string
        ingestion_label_value = optional(string)
      }))
    })), [])
    denied_data_access_labels = optional(list(object({
      data_access_label = optional(string)
      log_type          = optional(string)
      asset_namespace   = optional(string)
      ingestion_label = optional(object({
        ingestion_label_key   = string
        ingestion_label_value = optional(string)
      }))
    })), [])
  }))
  default = {}
}

variable "secops_config" {
  description = "SecOps configuration."
  type = object({
    customer_id = string
    project     = string
    region      = string
  })
}
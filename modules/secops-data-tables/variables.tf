# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

variable "data_tables_config" {
  description = "SecOps Data Tables configuration."
  type = map(object({
    description = string
    columns = list(object({
      column_type        = optional(string, "STRING")
      key_column         = optional(bool, false)
      mapped_column_path = optional(string)
      original_column    = string
    }))
    row_time_to_live = optional(string)
  }))
  default = {}
}

variable "factories_config" {
  description = "Paths to YAML config expected in 'data_tables'. Path to folder containing data tables content (csv files) for the corresponding _defs keys."
  type = object({
    data_tables      = optional(string)
    data_tables_defs = optional(string, "data_tables")
  })
  nullable = false
  default  = {}
}

variable "secops_config" {
  description = "SecOps configuration."
  type = object({
    customer_id = string
    project     = string
    region      = string
  })
}

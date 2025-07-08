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

variable "factories_config" {
  description = "Paths to  YAML config expected in 'rules' and 'reference_lists'. Path to folders containing rules definitions (yaral files) and reference lists content (txt files) for the corresponding _defs keys."
  type = object({
    #rules                = optional(string)
    rules_defs           = optional(string, "data/rules")
    #reference_lists      = optional(string)
    reference_lists_defs = optional(string, "data/reference_lists")
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
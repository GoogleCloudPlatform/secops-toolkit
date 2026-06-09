/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

variable "access_policy" {
  description = "Access policy id (used for tenant-level VPC-SC configurations)."
  type        = number
  default     = null
}

variable "billing_project" {
  description = "Billing project id. This project is used as the billing and quota project for the Terraform providers."
  type        = string
}

variable "cmek_config" {
  description = "CMEK Configuration for Google SecOps."
  type = object({
    enabled         = optional(bool, false)
    location        = optional(string, "europe")
    keyring_name    = optional(string, "secops-keyring")
    key_name        = optional(string, "secops-key")
    rotation_period = optional(string)
  })
  nullable = false
  default  = {}
}

variable "essential_contacts" {
  description = "List of essential contacts for Google Cloud project for product and platform notifications."
  type        = list(string)
  default     = []
}

variable "factories_config" {
  description = "Paths to folders that enable factory functionality."
  type = object({
    dataset = optional(string, "vpcsc")
    paths = optional(object({
      access_levels       = optional(string, "access-levels")
      defaults            = optional(string, "defaults.yaml")
      egress_policies     = optional(string, "egress-policies")
      ingress_policies    = optional(string, "ingress-policies")
      perimeters          = optional(string, "perimeters")
      restricted_services = optional(string, "restricted-services.yaml")
    }), {})
  })
  nullable = false
  default  = {}
}

variable "organization_id" {
  description = "GCP Organization ID used for VPC SC perimeters."
  type        = string
}

variable "project_create_config" {
  description = "Create project instead of using an existing one."
  type = object({
    billing_account  = string
    parent           = optional(string)
    bootstrap_folder = optional(bool, false)
  })
  default = null

  validation {
    condition = var.project_create_config == null ? true : (
      (var.project_create_config.parent != null ? 1 : 0) + (var.project_create_config.bootstrap_folder == true ? 1 : 0) <= 1
    )
    error_message = "Only one of 'parent' or 'bootstrap_folder' can be populated at the same time."
  }
}

variable "project_id" {
  description = "Project id that references existing project."
  type        = string
}

variable "vpc_sc_config" {
  description = "VPC SC Configuration."
  type = object({
    enabled      = optional(bool, false)
    scc_enabled  = optional(bool, false)
    cmek_enabled = optional(bool, false)
  })
  nullable = false
  default  = {}
}

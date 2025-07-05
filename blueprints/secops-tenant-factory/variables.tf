/**
 * Copyright 2025 Google LLC
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

variable "_tests" {
  description = "Dummy variable populated by tests pipeline."
  type        = bool
  default     = false
}

variable "billing_account" {
  description = "Billing account id for SecOps projects."
  type = string
  nullable = false
}

variable "factories_config" {
  description = "Configuration for network resource factories."
  type = object({
    data_folder           = optional(string, "data")
    dns_policy_rules_file = optional(string, "data/dns-policy-rules.yaml")
    firewall_policy_name  = optional(string, "net-default")
    tenants_folder        = optional(string, "data/tenants")
  })
  default = {
    data_folder           = "data"
    dns_policy_rules_file = "data/dns-policy-rules.yaml"
  }
  nullable = false
  validation {
    condition     = var.factories_config.data_folder != null
    error_message = "Data folder needs to be non-null."
  }
  validation {
    condition     = var.factories_config.firewall_policy_name != null
    error_message = "Firewall policy name needs to be non-null."
  }
}

variable "organization_id" {
  description = "GCP Organization ID. This is required only if tenant_nodes is configured for ingesting logs at org level."
  type        = string
  default     = null
}

variable "secops_config" {
  description = "SecOps configuration including customer management API key SA email."
  type = object({
    backstory_sa_email = string
    region             = string
    alpha_apis_region  = string
  })
  nullable = false
}

variable "tenant_folder" {
  description = "GCP folder hosting SecOps tenant projects."
  type = string
}
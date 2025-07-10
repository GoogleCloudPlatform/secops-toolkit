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

variable "gcp_logs_ingestion_config" {
  description = "Configuration for GCP logs to collect via Log Sink."
  type = object({
    AUDITD = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    BRO_JSON = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    GCP_APIGEE_X = optional(object({
      enabled              = optional(bool, false)
      override_log_filters = optional(list(string), null)
    }), {})
    GCP_CLOUDAUDIT = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    GCP_CLOUD_NAT = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    GCP_CLOUDSQL = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    GCP_DNS = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    GCP_FIREWALL = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    GCP_IDS = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    GCP_LOADBALANCING = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    KUBERNETES_NODE = optional(object({
      enabled              = optional(bool, false)
      override_log_filters = optional(list(string), null)
    }), {})
    LINUX_SYSMON = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    NIX_SYSTEM = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    WINEVTLOG = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
  })
  default = {}
}

variable "network_config" {
  description = "VPC config."
  type = object({
    functions_connector_ip_range = optional(string, "10.0.0.0/28")
    cloud_build_ip_range         = optional(string, "10.0.1.0/24")
  })
  default = {}
}

variable "organization_id" {
  description = "GCP Organization ID. This is required only if tenant_nodes is configured for ingesting logs at org level."
  type        = string
  default     = null
}

variable "project_create_config" {
  description = "Create project instead of using an existing one."
  type = object({
    billing_account = string
    parent          = optional(string)
  })
  default = null
}

variable "project_id" {
  description = "Project id that references existing project."
  type        = string
}

variable "regions" {
  description = "Region definitions."
  type = object({
    primary   = string
    secondary = string
  })
  default = {
    primary   = "europe-west8"
    secondary = "europe-west1"
  }
}

variable "secops_group_principals" {
  description = "Groups ID in IdP assigned to SecOps admins, editors, viewers roles."
  type = object({
    admins  = optional(list(string), [])
    editors = optional(list(string), [])
    viewers = optional(list(string), [])
  })
  default = {}
}

variable "secops_ingestion_config" {
  description = "SecOps Data ingestion configuration for Google Cloud Platform."
  type = object({
    ingest_scc_findings   = optional(bool, false)
    ingest_assets_data    = optional(bool, false)
    ingest_workspace_data = optional(bool, false)
    ingest_feed_type      = optional(string, "HTTPS_PUSH_GOOGLE_CLOUD_PUBSUB")
    assets_data_config = optional(object({
      GCP_BIGQUERY_CONTEXT = optional(object({
        enabled              = optional(bool, true)
        override_asset_types = optional(list(string), null)
      }), {})
      GCP_CLOUD_FUNCTIONS_CONTEXT = optional(object({
        enabled              = optional(bool, true)
        override_asset_types = optional(list(string), null)
      }), {})
      GCP_COMPUTE_CONTEXT = optional(object({
        enabled              = optional(bool, true)
        override_asset_types = optional(list(string), null)
      }), {})
      GCP_IAM_CONTEXT = optional(object({
        enabled              = optional(bool, true)
        override_asset_types = optional(list(string), null)
      }), {})
      GCP_KUBERNETES_CONTEXT = optional(object({
        enabled              = optional(bool, true)
        override_asset_types = optional(list(string), null)
      }), {})
      GCP_NETWORK_CONNECTIVITY_CONTEXT = optional(object({
        enabled              = optional(bool, true)
        override_asset_types = optional(list(string), null)
      }), {})
      GCP_RESOURCE_MANAGER_CONTEXT = optional(object({
        enabled              = optional(bool, true)
        override_asset_types = optional(list(string), null)
      }), {})
      GCP_SQL_CONTEXT = optional(object({
        enabled              = optional(bool, true)
        override_asset_types = optional(list(string), null)
      }), {})
    }), {})
  })
  default = {}
  validation {
    condition     = contains(["HTTPS_PUSH_WEBHOOK", "HTTPS_PUSH_GOOGLE_CLOUD_PUBSUB"], var.secops_ingestion_config.ingest_feed_type)
    error_message = "Allowed values for ingest_feed_type are \"HTTPS_PUSH_WEBHOOK\", \"HTTPS_PUSH_GOOGLE_CLOUD_PUBSUB\"."
  }
}

variable "secops_tenant_config" {
  description = "SecOps Tenant configuration."
  type = object({
    backstory_sa_email = optional(string)
    customer_id        = optional(string)
    tenant_id          = optional(string)
    tenant_code        = optional(string)
    tenant_subdomains  = optional(list(string), [])
    region             = string
    alpha_apis_region  = string
    retention_duration = optional(string, "ONE_YEAR")
    sso_config         = optional(string, null)
  })
  validation {
    condition = (
      (var.secops_tenant_config.customer_id != null && var.secops_tenant_config.tenant_id == null && var.secops_tenant_config.tenant_code == null && var.secops_tenant_config.backstory_sa_email == null) ||
      (var.secops_tenant_config.customer_id == null && var.secops_tenant_config.tenant_id != null && var.secops_tenant_config.tenant_code != null && var.secops_tenant_config.backstory_sa_email != null)
    )
    error_message = "Either 'customer_id' must be provided, or both 'tenant_id', 'tenant_code' and 'backstory_sa_email' must be provided, but not both."
  }
}

variable "tenant_nodes" {
  description = "GCP node IDs and configuration for SecOps tenant log sync."
  type = object({
    include_org = optional(bool, false)
    folders = optional(map(object({
      folder_id        = string
      include_children = optional(bool, true)
    })), {})
  })
  default = {}
}

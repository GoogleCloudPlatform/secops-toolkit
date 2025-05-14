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

variable "gcp_logs_ingestion_config" {
  type = object({
    GCP_CLOUDAUDIT = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    GCP_CLOUD_NAT = optional(object({
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
    GCP_CLOUDSQL = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    NIX_SYSTEM = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    LINUX_SYSMON = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    WINEVTLOG = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    BRO_JSON = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    KUBERNETES_NODE = optional(object({
      enabled              = optional(bool, false)
      override_log_filters = optional(list(string), null)
    }), {})
    AUDITD = optional(object({
      enabled              = optional(bool, true)
      override_log_filters = optional(list(string), null)
    }), {})
    GCP_APIGEE_X = optional(object({
      enabled              = optional(bool, false)
      override_log_filters = optional(list(string), null)
    }), {})
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
      GCP_SQL_CONTEXT = optional(object({
        enabled              = optional(bool, true)
        override_asset_types = optional(list(string), null)
      }), {})
      GCP_COMPUTE_CONTEXT = optional(object({
        enabled              = optional(bool, true)
        override_asset_types = optional(list(string), null)
      }), {})
      GCP_KUBERNETES_CONTEXT = optional(object({
        enabled              = optional(bool, true)
        override_asset_types = optional(list(string), null)
      }), {})
      GCP_IAM_CONTEXT = optional(object({
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
    }), {})
  })
  default = {}
  validation {
    condition     = contains(["HTTPS_PUSH_WEBHOOK", "HTTPS_PUSH_GOOGLE_CLOUD_PUBSUB"], var.secops_ingestion_config.ingest_feed_type)
    error_message = "Allowed values for ingest_feed_type are \"WEBHOOK\", \"HTTPS_PUSH_GOOGLE_CLOUD_PUBSUB\"."
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

variable "secops_iam" {
  description = "SecOps IAM configuration in {PRINCIPAL => {roles => [ROLES], scopes => [SCOPES]}} format."
  type = map(object({
    roles  = list(string)
    scopes = optional(list(string))
  }))
  default  = {}
  nullable = false
}

variable "secops_tenant_config" {
  description = "SecOps Tenant configuration."
  type = object({
    customer_id = string
    region      = string
  })
}

variable "secops_data_rbac_config" {
  description = "SecOps Data RBAC scope and labels config."
  type = object({
    labels = optional(map(object({
      description = string
      label_id    = string
      udm_query   = string
    })))
    scopes = optional(map(object({
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
    })))
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
  type = string
  default = null
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

variable "webhook_feeds_config" {
  description = "SecOps Webhook feeds config."
  type = map(object({
    display_name = optional(string)
    log_type     = string
  }))
  default  = {}
  nullable = false
}

variable "third_party_integration_config" {
  description = "SecOps Feeds configuration for Workspace logs and entities ingestion."
  type = object({
    azure_ad = optional(object({
      oauth_credentials = object({
        client_id     = string
        client_secret = string
      })
      retrieve_devices = optional(bool, true)
      retrieve_groups  = optional(bool, true)
      tenant_id        = string
    }))
    okta = optional(object({
      auth_header_key_values     = map(string)
      hostname                   = string
      manager_id_reference_field = string
    }))
    workspace = optional(object({
      customer_id    = string
      delegated_user = string
      applications = optional(list(string), ["access_transparency", "admin", "calendar", "chat", "drive", "gcp",
        "gplus", "groups", "groups_enterprise", "jamboard", "login", "meet", "mobile", "rules", "saml", "token",
        "user_accounts", "context_aware_access", "chrome", "data_studio", "keep",
      ])
    }))
  })
  default = {}
}

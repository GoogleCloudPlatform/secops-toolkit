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

variable "feeds" {
  description = "A map of Chronicle feeds to create."
  type = map(object({
    display_name    = string
    log_type        = string
    enabled         = optional(bool, true)
    asset_namespace = optional(string)
    labels          = optional(map(string))

    secret_manager_config = optional(object({
      region      = string
      secret_name = string
      version     = optional(string)
    }))

    amazon_s3_settings = optional(object({
      s3_uri                 = string
      source_deletion_option = string
      source_type            = string
      authentication = optional(object({
        region            = string
        access_key_id     = optional(string)
        secret_access_key = optional(string)
        client_id         = optional(string)
        client_secret     = optional(string)
        refresh_uri       = optional(string)
      }))
    }))

    amazon_s3_v2_settings = optional(object({
      s3_uri                 = string
      source_deletion_option = optional(string)
      max_lookback_days      = optional(number)
      authentication = object({
        access_key_secret_auth = optional(object({
          access_key_id     = string
          secret_access_key = string
        }))
        aws_iam_role_auth = optional(object({
          aws_iam_role_arn = optional(string)
          subject_id       = optional(string)
        }))
      })
    }))

    amazon_sqs_settings = optional(object({
      account_number         = optional(string)
      queue                  = optional(string)
      region                 = optional(string)
      source_deletion_option = optional(string)
      authentication = optional(object({
        additional_s3_access_key_secret_auth = optional(object({
          access_key_id     = optional(string)
          secret_access_key = optional(string)
        }))
        sqs_access_key_secret_auth = optional(object({
          access_key_id     = optional(string)
          secret_access_key = optional(string)
        }))
      }))
    }))

    amazon_sqs_v2_settings = optional(object({
      queue                  = string
      s3_uri                 = string
      source_deletion_option = optional(string)
      max_lookback_days      = optional(number)
      authentication = object({
        aws_iam_role_auth = object({
          aws_iam_role_arn = optional(string)
          subject_id       = optional(string)
        })
        sqs_v2_access_key_secret_auth = object({
          access_key_id     = optional(string)
          secret_access_key = optional(string)
        })
      })
    }))

    anomali_settings = optional(object({
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
    }))

    aws_ec2_hosts_settings = optional(object({
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
    }))

    aws_ec2_instances_settings = optional(object({
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
    }))

    aws_ec2_vpcs_settings = optional(object({
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
    }))

    aws_iam_settings = optional(object({
      api_type = optional(string)
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
    }))

    azure_ad_audit_settings = optional(object({
      auth_endpoint = optional(string)
      hostname      = optional(string)
      tenant_id     = optional(string)
      authentication = optional(object({
        client_id     = optional(string)
        client_secret = optional(string)
      }))
    }))

    azure_ad_context_settings = optional(object({
      auth_endpoint    = optional(string)
      hostname         = optional(string)
      tenant_id        = optional(string)
      retrieve_devices = optional(bool)
      retrieve_groups  = optional(bool)
      authentication = optional(object({
        client_id     = optional(string)
        client_secret = optional(string)
      }))
    }))

    azure_ad_settings = optional(object({
      auth_endpoint = optional(string)
      hostname      = optional(string)
      tenant_id     = optional(string)
      authentication = optional(object({
        client_id     = optional(string)
        client_secret = optional(string)
      }))
    }))

    azure_blob_store_settings = optional(object({
      azure_uri              = optional(string)
      source_deletion_option = optional(string)
      source_type            = optional(string)
      authentication = optional(object({
        sas_token  = optional(string)
        shared_key = optional(string)
      }))
    }))

    azure_blob_store_v2_settings = optional(object({
      azure_uri              = string
      source_deletion_option = optional(string)
      max_lookback_days      = optional(number)
      authentication = object({
        access_key = string
        sas_token  = string
        azure_v2_workload_identity_federation = object({
          client_id  = string
          subject_id = string
          tenant_id  = string
        })
      })
    }))

    azure_event_hub_settings = optional(object({
      consumer_group                  = string
      event_hub_connection_string     = string
      name                            = string
      azure_sas_token                 = optional(string)
      azure_storage_connection_string = optional(string)
      azure_storage_container         = optional(string)
    }))

    azure_mdm_intune_settings = optional(object({
      auth_endpoint = optional(string)
      hostname      = optional(string)
      tenant_id     = optional(string)
      authentication = optional(object({
        client_id     = optional(string)
        client_secret = optional(string)
      }))
    }))

    cloud_passage_settings = optional(object({
      event_types = optional(list(string))
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
    }))

    cortex_xdr_settings = optional(object({
      endpoint = optional(string)
      hostname = optional(string)
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    crowdstrike_alerts_settings = optional(object({
      hostname       = string
      ingestion_type = optional(string)
      authentication = object({
        client_id      = optional(string)
        client_secret  = optional(string)
        token_endpoint = optional(string)
      })
    }))

    crowdstrike_detects_settings = optional(object({
      hostname       = optional(string)
      ingestion_type = optional(string)
      authentication = optional(object({
        client_id      = optional(string)
        client_secret  = optional(string)
        token_endpoint = optional(string)
      }))
    }))

    dummy_log_type_settings = optional(object({
      api_endpoint = optional(string)
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    duo_auth_settings = optional(object({
      hostname = optional(string)
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
    }))

    duo_user_context_settings = optional(object({
      hostname = optional(string)
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
    }))

    fox_it_stix_settings = optional(object({
      collection       = optional(string)
      poll_service_uri = optional(string)
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
      ssl = optional(object({
        encoded_private_key = optional(string)
        ssl_certificate     = optional(string)
      }))
    }))

    gcs_settings = optional(object({
      bucket_uri             = optional(string)
      source_deletion_option = optional(string)
      source_type            = optional(string)
    }))

    gcs_v2_settings = optional(object({
      bucket_uri             = string
      source_deletion_option = optional(string)
      max_lookback_days      = optional(number)
    }))

    google_cloud_identity_device_users_settings = optional(object({
      authentication = optional(object({
        token_endpoint = optional(string)
        claims = optional(object({
          audience = optional(string)
          issuer   = optional(string)
          subject  = optional(string)
        }))
        rs_credentials = optional(object({
          private_key = optional(string)
        }))
      }))
    }))

    google_cloud_identity_devices_settings = optional(object({
      api_version = optional(string)
      authentication = optional(object({
        token_endpoint = optional(string)
        claims = optional(object({
          audience = optional(string)
          issuer   = optional(string)
          subject  = optional(string)
        }))
        rs_credentials = optional(object({
          private_key = optional(string)
        }))
      }))
    }))

    google_cloud_storage_event_driven_settings = optional(object({
      bucket_uri             = string
      pubsub_subscription    = string
      max_lookback_days      = optional(number)
      source_deletion_option = optional(string)
    }))

    http_settings = optional(object({
      uri                    = optional(string)
      source_deletion_option = optional(string)
      source_type            = optional(string)
    }))

    https_push_amazon_kinesis_firehose_settings = optional(object({
      split_delimiter = optional(string)
    }))

    https_push_google_cloud_pubsub_settings = optional(object({
      split_delimiter = optional(string)
    }))

    https_push_webhook_settings = optional(object({
      split_delimiter = optional(string)
    }))

    imperva_waf_settings = optional(object({
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    mandiant_ioc_settings = optional(object({
      start_time = optional(string)
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    microsoft_graph_alert_settings = optional(object({
      auth_endpoint = optional(string)
      hostname      = optional(string)
      tenant_id     = optional(string)
      authentication = optional(object({
        client_id     = optional(string)
        client_secret = optional(string)
      }))
    }))

    microsoft_security_center_alert_settings = optional(object({
      auth_endpoint   = optional(string)
      hostname        = optional(string)
      subscription_id = optional(string)
      tenant_id       = optional(string)
      authentication = optional(object({
        client_id     = optional(string)
        client_secret = optional(string)
      }))
    }))

    mimecast_mail_settings = optional(object({
      hostname = optional(string)
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    mimecast_mail_v2_settings = optional(object({
      auth_credentials = optional(object({
        client_id     = optional(string)
        client_secret = optional(string)
      }))
    }))

    netskope_alert_settings = optional(object({
      content_type = optional(string)
      feedname     = optional(string)
      hostname     = optional(string)
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    netskope_alert_v2_settings = optional(object({
      content_category = optional(string)
      content_types    = optional(list(string))
      hostname         = optional(string)
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    office365_settings = optional(object({
      auth_endpoint = optional(string)
      hostname      = optional(string)
      tenant_id     = optional(string)
      content_type  = optional(string)
      authentication = optional(object({
        client_id     = optional(string)
        client_secret = optional(string)
      }))
    }))

    okta_settings = optional(object({
      hostname = optional(string)
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    okta_user_context_settings = optional(object({
      hostname                   = optional(string)
      manager_id_reference_field = optional(string)
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    pan_ioc_settings = optional(object({
      feed    = optional(string)
      feed_id = optional(string)
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    pan_prisma_cloud_settings = optional(object({
      hostname = optional(string)
      authentication = optional(object({
        user     = optional(string)
        password = optional(string)
      }))
    }))

    proofpoint_mail_settings = optional(object({
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
    }))

    proofpoint_on_demand_settings = optional(object({
      cluster_id = optional(string)
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    pubsub_settings = optional(object({
      google_service_account_email = optional(string)
    }))

    qualys_scan_settings = optional(object({
      api_type = optional(string)
      hostname = optional(string)
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
    }))

    qualys_vm_settings = optional(object({
      hostname = optional(string)
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
    }))

    rapid7_insight_settings = optional(object({
      endpoint = optional(string)
      hostname = optional(string)
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    recorded_future_ioc_settings = optional(object({
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    rh_isac_ioc_settings = optional(object({
      authentication = optional(object({
        client_id      = optional(string)
        client_secret  = optional(string)
        token_endpoint = optional(string)
      }))
    }))

    salesforce_settings = optional(object({
      hostname = optional(string)
      oauth_jwt_credentials = optional(object({
        token_endpoint = optional(string)
        claims = optional(object({
          audience = optional(string)
          issuer   = optional(string)
          subject  = optional(string)
        }))
        rs_credentials = optional(object({
          private_key = optional(string)
        }))
      }))
      oauth_password_grant_auth = optional(object({
        token_endpoint = optional(string)
        client_id      = optional(string)
        client_secret  = optional(string)
        user           = optional(string)
        password       = optional(string)
      }))
    }))

    sentinelone_alert_settings = optional(object({
      hostname                = optional(string)
      initial_start_time      = optional(string)
      is_alert_api_subscribed = optional(bool)
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    service_now_cmdb_settings = optional(object({
      feedname = optional(string)
      hostname = optional(string)
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
    }))

    sftp_settings = optional(object({
      uri                    = optional(string)
      source_deletion_option = optional(string)
      source_type            = optional(string)
      authentication = optional(object({
        username               = optional(string)
        password               = optional(string)
        private_key            = optional(string)
        private_key_passphrase = optional(string)
      }))
    }))

    symantec_event_export_settings = optional(object({
      authentication = optional(object({
        token_endpoint = optional(string)
        client_id      = optional(string)
        client_secret  = optional(string)
        refresh_token  = optional(string)
      }))
    }))

    thinkst_canary_settings = optional(object({
      hostname = optional(string)
      authentication = optional(object({
        header_key_values = optional(list(object({
          key   = optional(string)
          value = optional(string)
        })))
      }))
    }))

    threat_connect_ioc_settings = optional(object({
      hostname = optional(string)
      owners   = optional(list(string))
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
    }))

    threat_connect_ioc_v3_settings = optional(object({
      hostname  = optional(string)
      owners    = optional(list(string))
      fields    = optional(list(string))
      schedule  = optional(string)
      tql_query = optional(string)
      authentication = optional(object({
        user   = optional(string)
        secret = optional(string)
      }))
    }))

    trellix_hx_alerts_settings = optional(object({
      endpoint = optional(string)
      authentication = optional(object({
        msso = optional(object({
          api_endpoint = optional(string)
          username     = optional(string)
          password     = optional(string)
        }))
        trellix_iam = optional(object({
          client_id     = optional(string)
          client_secret = optional(string)
          scope         = optional(string)
        }))
      }))
    }))

    trellix_hx_bulk_acqs_settings = optional(object({
      endpoint = string
      authentication = optional(object({
        msso = optional(object({
          api_endpoint = string
          username     = string
          password     = string
        }))
        trellix_iam = optional(object({
          client_id     = string
          client_secret = string
          scope         = string
        }))
      }))
    }))

    trellix_hx_hosts_settings = optional(object({
      endpoint = string
      authentication = optional(object({
        msso = optional(object({
          api_endpoint = string
          username     = string
          password     = string
        }))
        trellix_iam = optional(object({
          client_id     = string
          client_secret = string
          scope         = string
        }))
      }))
    }))

    webhook_settings = optional(object({
    }))

    workday_settings = optional(object({
      hostname  = optional(string)
      tenant_id = optional(string)
      authentication = optional(object({
        user           = optional(string)
        secret         = optional(string)
        token_endpoint = optional(string)
        client_id      = optional(string)
        client_secret  = optional(string)
        refresh_token  = optional(string)
      }))
    }))

    workspace_activity_settings = optional(object({
      workspace_customer_id = optional(string)
      applications          = optional(list(string))
      authentication = optional(object({
        token_endpoint = optional(string)
        claims = optional(object({
          audience = optional(string)
          issuer   = optional(string)
          subject  = optional(string)
        }))
        rs_credentials = optional(object({
          private_key = optional(string)
        }))
      }))
    }))

    workspace_alerts_settings = optional(object({
      workspace_customer_id = optional(string)
      authentication = optional(object({
        token_endpoint = optional(string)
        claims = optional(object({
          audience = optional(string)
          issuer   = optional(string)
          subject  = optional(string)
        }))
        rs_credentials = optional(object({
          private_key = optional(string)
        }))
      }))
    }))

    workspace_chrome_os_settings = optional(object({
      workspace_customer_id = optional(string)
      authentication = optional(object({
        token_endpoint = optional(string)
        claims = optional(object({
          audience = optional(string)
          issuer   = optional(string)
          subject  = optional(string)
        }))
        rs_credentials = optional(object({
          private_key = optional(string)
        }))
      }))
    }))

    workspace_groups_settings = optional(object({
      workspace_customer_id = optional(string)
      authentication = optional(object({
        token_endpoint = optional(string)
        claims = optional(object({
          audience = optional(string)
          issuer   = optional(string)
          subject  = optional(string)
        }))
        rs_credentials = optional(object({
          private_key = optional(string)
        }))
      }))
    }))

    workspace_mobile_settings = optional(object({
      workspace_customer_id = optional(string)
      authentication = optional(object({
        token_endpoint = optional(string)
        claims = optional(object({
          audience = optional(string)
          issuer   = optional(string)
          subject  = optional(string)
        }))
        rs_credentials = optional(object({
          private_key = optional(string)
        }))
      }))
    }))

    workspace_privileges_settings = optional(object({
      workspace_customer_id = optional(string)
      authentication = optional(object({
        token_endpoint = optional(string)
        claims = optional(object({
          audience = optional(string)
          issuer   = optional(string)
          subject  = optional(string)
        }))
        rs_credentials = optional(object({
          private_key = optional(string)
        }))
      }))
    }))

    workspace_users_settings = optional(object({
      workspace_customer_id = optional(string)
      projection_type       = optional(string)
      authentication = optional(object({
        token_endpoint = optional(string)
        claims = optional(object({
          audience = optional(string)
          issuer   = optional(string)
          subject  = optional(string)
        }))
        rs_credentials = optional(object({
          private_key = optional(string)
        }))
      }))
    }))
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

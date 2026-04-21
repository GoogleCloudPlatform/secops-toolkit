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

locals {
  source_type_mapping = {
    amazon_s3_settings                          = "AMAZON_S3"
    amazon_s3_v2_settings                       = "AMAZON_S3_V2"
    amazon_sqs_settings                         = "AMAZON_SQS"
    amazon_sqs_v2_settings                      = "AMAZON_SQS_V2"
    anomali_settings                            = "API"
    aws_ec2_hosts_settings                      = "API"
    aws_ec2_instances_settings                  = "API"
    aws_ec2_vpcs_settings                       = "API"
    aws_iam_settings                            = "API"
    azure_ad_audit_settings                     = "API"
    azure_ad_context_settings                   = "API"
    azure_ad_settings                           = "API"
    azure_blob_store_settings                   = "AZURE_BLOBSTORE"
    azure_blob_store_v2_settings                = "AZURE_BLOBSTORE_V2"
    azure_event_hub_settings                    = "AZURE_EVENT_HUB"
    azure_mdm_intune_settings                   = "API"
    cloud_passage_settings                      = "API"
    cortex_xdr_settings                         = "API"
    crowdstrike_alerts_settings                 = "API"
    crowdstrike_detects_settings                = "API"
    dummy_log_type_settings                     = "API"
    duo_auth_settings                           = "API"
    duo_user_context_settings                   = "API"
    fox_it_stix_settings                        = "API"
    gcs_settings                                = "GOOGLE_CLOUD_STORAGE"
    gcs_v2_settings                             = "GOOGLE_CLOUD_STORAGE_V2"
    google_cloud_identity_device_users_settings = "API"
    google_cloud_identity_devices_settings      = "API"
    google_cloud_storage_event_driven_settings  = "GOOGLE_CLOUD_STORAGE_EVENT_DRIVEN"
    http_settings                               = "HTTP"
    https_push_amazon_kinesis_firehose_settings = "HTTPS_PUSH_AMAZON_KINESIS_FIREHOSE"
    https_push_google_cloud_pubsub_settings     = "HTTPS_PUSH_GOOGLE_CLOUD_PUBSUB"
    https_push_webhook_settings                 = "HTTPS_PUSH_WEBHOOK"
    imperva_waf_settings                        = "API"
    mandiant_ioc_settings                       = "API"
    microsoft_graph_alert_settings              = "API"
    microsoft_security_center_alert_settings    = "API"
    mimecast_mail_settings                      = "API"
    mimecast_mail_v2_settings                   = "API"
    netskope_alert_settings                     = "API"
    netskope_alert_v2_settings                  = "API"
    office365_settings                          = "API"
    okta_settings                               = "API"
    okta_user_context_settings                  = "API"
    pan_ioc_settings                            = "API"
    pan_prisma_cloud_settings                   = "API"
    proofpoint_mail_settings                    = "API"
    proofpoint_on_demand_settings               = "API"
    pubsub_settings                             = "PUBSUB"
    qualys_scan_settings                        = "API"
    qualys_vm_settings                          = "API"
    rapid7_insight_settings                     = "API"
    recorded_future_ioc_settings                = "API"
    rh_isac_ioc_settings                        = "API"
    salesforce_settings                         = "API"
    sentinelone_alert_settings                  = "API"
    service_now_cmdb_settings                   = "API"
    sftp_settings                               = "SFTP"
    symantec_event_export_settings              = "API"
    thinkst_canary_settings                     = "API"
    threat_connect_ioc_settings                 = "API"
    threat_connect_ioc_v3_settings              = "API"
    trellix_hx_alerts_settings                  = "API"
    trellix_hx_bulk_acqs_settings               = "API"
    trellix_hx_hosts_settings                   = "API"
    webhook_settings                            = "WEBHOOK"
    workday_settings                            = "API"
    workspace_activity_settings                 = "API"
    workspace_alerts_settings                   = "API"
    workspace_chrome_os_settings                = "API"
    workspace_groups_settings                   = "API"
    workspace_mobile_settings                   = "API"
    workspace_privileges_settings               = "API"
    workspace_users_settings                    = "API"
  }
}

data "google_secret_manager_regional_secret_version" "secops_secrets" {
  for_each = { for k, v in var.feeds : k => v if v.secret_manager_config != null }
  secret   = each.value.secret_manager_config.secret_name
  project  = var.secops_config.project
  location = each.value.secret_manager_config.region
  version  = each.value.secret_manager_config.version
}

resource "google_chronicle_feed" "feeds" {
  provider = google-beta
  for_each = var.feeds

  project      = var.secops_config.project
  location     = var.secops_config.region
  instance     = var.secops_config.customer_id
  display_name = each.value.display_name

  details {
    log_type = "projects/${var.secops_config.project}/locations/${var.secops_config.region}/instances/${var.secops_config.customer_id}/logTypes/${each.value.log_type}"
    feed_source_type = one([
      for setting_name, source_type in local.source_type_mapping : source_type if lookup(each.value, setting_name, null) != null
    ])
    asset_namespace = each.value.asset_namespace
    labels          = each.value.labels

    dynamic "amazon_s3_settings" {
      for_each = lookup(each.value, "amazon_s3_settings", null) != null ? [each.value.amazon_s3_settings] : []
      content {
        s3_uri                 = amazon_s3_settings.value.s3_uri
        source_deletion_option = amazon_s3_settings.value.source_deletion_option
        source_type            = amazon_s3_settings.value.source_type
        dynamic "authentication" {
          for_each = lookup(amazon_s3_settings.value, "authentication", null) != null ? [amazon_s3_settings.value.authentication] : []
          content {
            region            = authentication.value.region
            access_key_id     = lookup(authentication.value, "access_key_id", null)
            secret_access_key = lookup(authentication.value, "secret_access_key", null)
            client_id         = lookup(authentication.value, "client_id", null)
            client_secret     = lookup(authentication.value, "client_secret", null)
            refresh_uri       = lookup(authentication.value, "refresh_uri", null)
          }
        }
      }
    }

    dynamic "amazon_s3_v2_settings" {
      for_each = lookup(each.value, "amazon_s3_v2_settings", null) != null ? [each.value.amazon_s3_v2_settings] : []
      content {
        s3_uri                 = amazon_s3_v2_settings.value.s3_uri
        source_deletion_option = lookup(amazon_s3_v2_settings.value, "source_deletion_option", null)
        max_lookback_days      = lookup(amazon_s3_v2_settings.value, "max_lookback_days", null)
        dynamic "authentication" {
          for_each = lookup(amazon_s3_v2_settings.value, "authentication", null) != null ? [amazon_s3_v2_settings.value.authentication] : []
          content {
            dynamic "access_key_secret_auth" {
              for_each = lookup(authentication.value, "access_key_secret_auth", null) != null ? [authentication.value.access_key_secret_auth] : []
              content {
                access_key_id     = access_key_secret_auth.value.access_key_id
                secret_access_key = access_key_secret_auth.value.secret_access_key
              }
            }
            dynamic "aws_iam_role_auth" {
              for_each = lookup(authentication.value, "aws_iam_role_auth", null) != null ? [authentication.value.aws_iam_role_auth] : []
              content {
                aws_iam_role_arn = lookup(aws_iam_role_auth.value, "aws_iam_role_arn", null)
                subject_id       = lookup(aws_iam_role_auth.value, "subject_id", null)
              }
            }
          }
        }
      }
    }

    dynamic "amazon_sqs_settings" {
      for_each = lookup(each.value, "amazon_sqs_settings", null) != null ? [each.value.amazon_sqs_settings] : []
      content {
        account_number         = lookup(amazon_sqs_settings.value, "account_number", null)
        queue                  = lookup(amazon_sqs_settings.value, "queue", null)
        region                 = lookup(amazon_sqs_settings.value, "region", null)
        source_deletion_option = lookup(amazon_sqs_settings.value, "source_deletion_option", null)
        dynamic "authentication" {
          for_each = lookup(amazon_sqs_settings.value, "authentication", null) != null ? [amazon_sqs_settings.value.authentication] : []
          content {
            dynamic "additional_s3_access_key_secret_auth" {
              for_each = lookup(authentication.value, "additional_s3_access_key_secret_auth", null) != null ? [authentication.value.additional_s3_access_key_secret_auth] : []
              content {
                access_key_id     = lookup(additional_s3_access_key_secret_auth.value, "access_key_id", null)
                secret_access_key = lookup(additional_s3_access_key_secret_auth.value, "secret_access_key", null)
              }
            }
            dynamic "sqs_access_key_secret_auth" {
              for_each = lookup(authentication.value, "sqs_access_key_secret_auth", null) != null ? [authentication.value.sqs_access_key_secret_auth] : []
              content {
                access_key_id     = lookup(sqs_access_key_secret_auth.value, "access_key_id", null)
                secret_access_key = lookup(sqs_access_key_secret_auth.value, "secret_access_key", null)
              }
            }
          }
        }
      }
    }

    dynamic "amazon_sqs_v2_settings" {
      for_each = lookup(each.value, "amazon_sqs_v2_settings", null) != null ? [each.value.amazon_sqs_v2_settings] : []
      content {
        queue                  = amazon_sqs_v2_settings.value.queue
        s3_uri                 = amazon_sqs_v2_settings.value.s3_uri
        source_deletion_option = lookup(amazon_sqs_v2_settings.value, "source_deletion_option", null)
        max_lookback_days      = lookup(amazon_sqs_v2_settings.value, "max_lookback_days", null)
        dynamic "authentication" {
          for_each = lookup(amazon_sqs_v2_settings.value, "authentication", null) != null ? [amazon_sqs_v2_settings.value.authentication] : []
          content {
            dynamic "aws_iam_role_auth" {
              for_each = lookup(authentication.value, "aws_iam_role_auth", null) != null ? [authentication.value.aws_iam_role_auth] : []
              content {
                aws_iam_role_arn = lookup(aws_iam_role_auth.value, "aws_iam_role_arn", null)
                subject_id       = lookup(aws_iam_role_auth.value, "subject_id", null)
              }
            }
            dynamic "sqs_v2_access_key_secret_auth" {
              for_each = lookup(authentication.value, "sqs_v2_access_key_secret_auth", null) != null ? [authentication.value.sqs_v2_access_key_secret_auth] : []
              content {
                access_key_id     = lookup(sqs_v2_access_key_secret_auth.value, "access_key_id", null)
                secret_access_key = lookup(sqs_v2_access_key_secret_auth.value, "secret_access_key", null)
              }
            }
          }
        }
      }
    }

    dynamic "anomali_settings" {
      for_each = lookup(each.value, "anomali_settings", null) != null ? [each.value.anomali_settings] : []
      content {
        dynamic "authentication" {
          for_each = lookup(anomali_settings.value, "authentication", null) != null ? [anomali_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
      }
    }

    dynamic "aws_ec2_hosts_settings" {
      for_each = lookup(each.value, "aws_ec2_hosts_settings", null) != null ? [each.value.aws_ec2_hosts_settings] : []
      content {
        dynamic "authentication" {
          for_each = lookup(aws_ec2_hosts_settings.value, "authentication", null) != null ? [aws_ec2_hosts_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
      }
    }

    dynamic "aws_ec2_instances_settings" {
      for_each = lookup(each.value, "aws_ec2_instances_settings", null) != null ? [each.value.aws_ec2_instances_settings] : []
      content {
        dynamic "authentication" {
          for_each = lookup(aws_ec2_instances_settings.value, "authentication", null) != null ? [aws_ec2_instances_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
      }
    }

    dynamic "aws_ec2_vpcs_settings" {
      for_each = lookup(each.value, "aws_ec2_vpcs_settings", null) != null ? [each.value.aws_ec2_vpcs_settings] : []
      content {
        dynamic "authentication" {
          for_each = lookup(aws_ec2_vpcs_settings.value, "authentication", null) != null ? [aws_ec2_vpcs_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
      }
    }

    dynamic "aws_iam_settings" {
      for_each = lookup(each.value, "aws_iam_settings", null) != null ? [each.value.aws_iam_settings] : []
      content {
        api_type = lookup(aws_iam_settings.value, "api_type", null)
        dynamic "authentication" {
          for_each = lookup(aws_iam_settings.value, "authentication", null) != null ? [aws_iam_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
      }
    }

    dynamic "azure_ad_audit_settings" {
      for_each = lookup(each.value, "azure_ad_audit_settings", null) != null ? [each.value.azure_ad_audit_settings] : []
      content {
        auth_endpoint = lookup(azure_ad_audit_settings.value, "auth_endpoint", null)
        hostname      = lookup(azure_ad_audit_settings.value, "hostname", null)
        tenant_id     = lookup(azure_ad_audit_settings.value, "tenant_id", null)
        dynamic "authentication" {
          for_each = lookup(azure_ad_audit_settings.value, "authentication", null) != null ? [azure_ad_audit_settings.value.authentication] : []
          content {
            client_id     = lookup(authentication.value, "client_id", null)
            client_secret = try(data.google_secret_manager_regional_secret_version.secops_secrets[each.key].secret_data, lookup(authentication.value, "client_secret", null))
          }
        }
      }
    }

    dynamic "azure_ad_context_settings" {
      for_each = lookup(each.value, "azure_ad_context_settings", null) != null ? [each.value.azure_ad_context_settings] : []
      content {
        auth_endpoint    = lookup(azure_ad_context_settings.value, "auth_endpoint", null)
        hostname         = lookup(azure_ad_context_settings.value, "hostname", null)
        tenant_id        = lookup(azure_ad_context_settings.value, "tenant_id", null)
        retrieve_devices = lookup(azure_ad_context_settings.value, "retrieve_devices", null)
        retrieve_groups  = lookup(azure_ad_context_settings.value, "retrieve_groups", null)
        dynamic "authentication" {
          for_each = lookup(azure_ad_context_settings.value, "authentication", null) != null ? [azure_ad_context_settings.value.authentication] : []
          content {
            client_id     = lookup(authentication.value, "client_id", null)
            client_secret = try(data.google_secret_manager_regional_secret_version.secops_secrets[each.key].secret_data, lookup(authentication.value, "client_secret", null))
          }
        }
      }
    }

    dynamic "azure_ad_settings" {
      for_each = lookup(each.value, "azure_ad_settings", null) != null ? [each.value.azure_ad_settings] : []
      content {
        auth_endpoint = lookup(azure_ad_settings.value, "auth_endpoint", null)
        hostname      = lookup(azure_ad_settings.value, "hostname", null)
        tenant_id     = lookup(azure_ad_settings.value, "tenant_id", null)
        dynamic "authentication" {
          for_each = lookup(azure_ad_settings.value, "authentication", null) != null ? [azure_ad_settings.value.authentication] : []
          content {
            client_id     = lookup(authentication.value, "client_id", null)
            client_secret = try(data.google_secret_manager_regional_secret_version.secops_secrets[each.key].secret_data, lookup(authentication.value, "client_secret", null))
          }
        }
      }
    }

    dynamic "azure_blob_store_settings" {
      for_each = lookup(each.value, "azure_blob_store_settings", null) != null ? [each.value.azure_blob_store_settings] : []
      content {
        azure_uri              = lookup(azure_blob_store_settings.value, "azure_uri", null)
        source_deletion_option = lookup(azure_blob_store_settings.value, "source_deletion_option", null)
        source_type            = lookup(azure_blob_store_settings.value, "source_type", null)
        dynamic "authentication" {
          for_each = lookup(azure_blob_store_settings.value, "authentication", null) != null ? [azure_blob_store_settings.value.authentication] : []
          content {
            sas_token  = lookup(authentication.value, "sas_token", null)
            shared_key = lookup(authentication.value, "shared_key", null)
          }
        }
      }
    }

    dynamic "azure_blob_store_v2_settings" {
      for_each = lookup(each.value, "azure_blob_store_v2_settings", null) != null ? [each.value.azure_blob_store_v2_settings] : []
      content {
        azure_uri              = azure_blob_store_v2_settings.value.azure_uri
        source_deletion_option = lookup(azure_blob_store_v2_settings.value, "source_deletion_option", null)
        max_lookback_days      = lookup(azure_blob_store_v2_settings.value, "max_lookback_days", null)
        dynamic "authentication" {
          for_each = lookup(azure_blob_store_v2_settings.value, "authentication", null) != null ? [azure_blob_store_v2_settings.value.authentication] : []
          content {
            access_key = authentication.value.access_key
            sas_token  = authentication.value.sas_token
            dynamic "azure_v2_workload_identity_federation" {
              for_each = lookup(authentication.value, "azure_v2_workload_identity_federation", null) != null ? [authentication.value.azure_v2_workload_identity_federation] : []
              content {
                client_id  = azure_v2_workload_identity_federation.value.client_id
                subject_id = azure_v2_workload_identity_federation.value.subject_id
                tenant_id  = azure_v2_workload_identity_federation.value.tenant_id
              }
            }
          }
        }
      }
    }

    dynamic "azure_event_hub_settings" {
      for_each = lookup(each.value, "azure_event_hub_settings", null) != null ? [each.value.azure_event_hub_settings] : []
      content {
        consumer_group                  = azure_event_hub_settings.value.consumer_group
        event_hub_connection_string     = azure_event_hub_settings.value.event_hub_connection_string
        name                            = azure_event_hub_settings.value.name
        azure_sas_token                 = lookup(azure_event_hub_settings.value, "azure_sas_token", null)
        azure_storage_connection_string = lookup(azure_event_hub_settings.value, "azure_storage_connection_string", null)
        azure_storage_container         = lookup(azure_event_hub_settings.value, "azure_storage_container", null)
      }
    }

    dynamic "azure_mdm_intune_settings" {
      for_each = lookup(each.value, "azure_mdm_intune_settings", null) != null ? [each.value.azure_mdm_intune_settings] : []
      content {
        auth_endpoint = lookup(azure_mdm_intune_settings.value, "auth_endpoint", null)
        hostname      = lookup(azure_mdm_intune_settings.value, "hostname", null)
        tenant_id     = lookup(azure_mdm_intune_settings.value, "tenant_id", null)
        dynamic "authentication" {
          for_each = lookup(azure_mdm_intune_settings.value, "authentication", null) != null ? [azure_mdm_intune_settings.value.authentication] : []
          content {
            client_id     = lookup(authentication.value, "client_id", null)
            client_secret = lookup(authentication.value, "client_secret", null)
          }
        }
      }
    }

    dynamic "cloud_passage_settings" {
      for_each = lookup(each.value, "cloud_passage_settings", null) != null ? [each.value.cloud_passage_settings] : []
      content {
        event_types = lookup(cloud_passage_settings.value, "event_types", null)
        dynamic "authentication" {
          for_each = lookup(cloud_passage_settings.value, "authentication", null) != null ? [cloud_passage_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
      }
    }

    dynamic "cortex_xdr_settings" {
      for_each = lookup(each.value, "cortex_xdr_settings", null) != null ? [each.value.cortex_xdr_settings] : []
      content {
        endpoint = lookup(cortex_xdr_settings.value, "endpoint", null)
        hostname = lookup(cortex_xdr_settings.value, "hostname", null)
        dynamic "authentication" {
          for_each = lookup(cortex_xdr_settings.value, "authentication", null) != null ? [cortex_xdr_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "crowdstrike_alerts_settings" {
      for_each = lookup(each.value, "crowdstrike_alerts_settings", null) != null ? [each.value.crowdstrike_alerts_settings] : []
      content {
        hostname       = crowdstrike_alerts_settings.value.hostname
        ingestion_type = lookup(crowdstrike_alerts_settings.value, "ingestion_type", null)
        dynamic "authentication" {
          for_each = lookup(crowdstrike_alerts_settings.value, "authentication", null) != null ? [crowdstrike_alerts_settings.value.authentication] : []
          content {
            client_id      = lookup(authentication.value, "client_id", null)
            client_secret  = lookup(authentication.value, "client_secret", null)
            token_endpoint = lookup(authentication.value, "token_endpoint", null)
          }
        }
      }
    }

    dynamic "crowdstrike_detects_settings" {
      for_each = lookup(each.value, "crowdstrike_detects_settings", null) != null ? [each.value.crowdstrike_detects_settings] : []
      content {
        hostname       = lookup(crowdstrike_detects_settings.value, "hostname", null)
        ingestion_type = lookup(crowdstrike_detects_settings.value, "ingestion_type", null)
        dynamic "authentication" {
          for_each = lookup(crowdstrike_detects_settings.value, "authentication", null) != null ? [crowdstrike_detects_settings.value.authentication] : []
          content {
            client_id      = lookup(authentication.value, "client_id", null)
            client_secret  = lookup(authentication.value, "client_secret", null)
            token_endpoint = lookup(authentication.value, "token_endpoint", null)
          }
        }
      }
    }

    dynamic "dummy_log_type_settings" {
      for_each = lookup(each.value, "dummy_log_type_settings", null) != null ? [each.value.dummy_log_type_settings] : []
      content {
        api_endpoint = lookup(dummy_log_type_settings.value, "api_endpoint", null)
        dynamic "authentication" {
          for_each = lookup(dummy_log_type_settings.value, "authentication", null) != null ? [dummy_log_type_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "duo_auth_settings" {
      for_each = lookup(each.value, "duo_auth_settings", null) != null ? [each.value.duo_auth_settings] : []
      content {
        hostname = lookup(duo_auth_settings.value, "hostname", null)
        dynamic "authentication" {
          for_each = lookup(duo_auth_settings.value, "authentication", null) != null ? [duo_auth_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
      }
    }

    dynamic "duo_user_context_settings" {
      for_each = lookup(each.value, "duo_user_context_settings", null) != null ? [each.value.duo_user_context_settings] : []
      content {
        hostname = lookup(duo_user_context_settings.value, "hostname", null)
        dynamic "authentication" {
          for_each = lookup(duo_user_context_settings.value, "authentication", null) != null ? [duo_user_context_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
      }
    }

    dynamic "fox_it_stix_settings" {
      for_each = lookup(each.value, "fox_it_stix_settings", null) != null ? [each.value.fox_it_stix_settings] : []
      content {
        collection       = lookup(fox_it_stix_settings.value, "collection", null)
        poll_service_uri = lookup(fox_it_stix_settings.value, "poll_service_uri", null)
        dynamic "authentication" {
          for_each = lookup(fox_it_stix_settings.value, "authentication", null) != null ? [fox_it_stix_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
        dynamic "ssl" {
          for_each = lookup(fox_it_stix_settings.value, "ssl", null) != null ? [fox_it_stix_settings.value.ssl] : []
          content {
            encoded_private_key = lookup(ssl.value, "encoded_private_key", null)
            ssl_certificate     = lookup(ssl.value, "ssl_certificate", null)
          }
        }
      }
    }

    dynamic "gcs_settings" {
      for_each = lookup(each.value, "gcs_settings", null) != null ? [each.value.gcs_settings] : []
      content {
        bucket_uri             = lookup(gcs_settings.value, "bucket_uri", null)
        source_deletion_option = lookup(gcs_settings.value, "source_deletion_option", null)
        source_type            = lookup(gcs_settings.value, "source_type", null)
      }
    }

    dynamic "gcs_v2_settings" {
      for_each = lookup(each.value, "gcs_v2_settings", null) != null ? [each.value.gcs_v2_settings] : []
      content {
        bucket_uri             = gcs_v2_settings.value.bucket_uri
        source_deletion_option = lookup(gcs_v2_settings.value, "source_deletion_option", null)
        max_lookback_days      = lookup(gcs_v2_settings.value, "max_lookback_days", null)
      }
    }

    dynamic "google_cloud_identity_device_users_settings" {
      for_each = lookup(each.value, "google_cloud_identity_device_users_settings", null) != null ? [each.value.google_cloud_identity_device_users_settings] : []
      content {
        dynamic "authentication" {
          for_each = lookup(google_cloud_identity_device_users_settings.value, "authentication", null) != null ? [google_cloud_identity_device_users_settings.value.authentication] : []
          content {
            token_endpoint = lookup(authentication.value, "token_endpoint", null)
            dynamic "claims" {
              for_each = lookup(authentication.value, "claims", null) != null ? [authentication.value.claims] : []
              content {
                audience = lookup(claims.value, "audience", null)
                issuer   = lookup(claims.value, "issuer", null)
                subject  = lookup(claims.value, "subject", null)
              }
            }
            dynamic "rs_credentials" {
              for_each = lookup(authentication.value, "rs_credentials", null) != null ? [authentication.value.rs_credentials] : []
              content {
                private_key = lookup(rs_credentials.value, "private_key", null)
              }
            }
          }
        }
      }
    }

    dynamic "google_cloud_identity_devices_settings" {
      for_each = lookup(each.value, "google_cloud_identity_devices_settings", null) != null ? [each.value.google_cloud_identity_devices_settings] : []
      content {
        api_version = lookup(google_cloud_identity_devices_settings.value, "api_version", null)
        dynamic "authentication" {
          for_each = lookup(google_cloud_identity_devices_settings.value, "authentication", null) != null ? [google_cloud_identity_devices_settings.value.authentication] : []
          content {
            token_endpoint = lookup(authentication.value, "token_endpoint", null)
            dynamic "claims" {
              for_each = lookup(authentication.value, "claims", null) != null ? [authentication.value.claims] : []
              content {
                audience = lookup(claims.value, "audience", null)
                issuer   = lookup(claims.value, "issuer", null)
                subject  = lookup(claims.value, "subject", null)
              }
            }
            dynamic "rs_credentials" {
              for_each = lookup(authentication.value, "rs_credentials", null) != null ? [authentication.value.rs_credentials] : []
              content {
                private_key = lookup(rs_credentials.value, "private_key", null)
              }
            }
          }
        }
      }
    }

    dynamic "google_cloud_storage_event_driven_settings" {
      for_each = lookup(each.value, "google_cloud_storage_event_driven_settings", null) != null ? [each.value.google_cloud_storage_event_driven_settings] : []
      content {
        bucket_uri             = google_cloud_storage_event_driven_settings.value.bucket_uri
        pubsub_subscription    = google_cloud_storage_event_driven_settings.value.pubsub_subscription
        max_lookback_days      = lookup(google_cloud_storage_event_driven_settings.value, "max_lookback_days", null)
        source_deletion_option = lookup(google_cloud_storage_event_driven_settings.value, "source_deletion_option", null)
      }
    }

    dynamic "http_settings" {
      for_each = lookup(each.value, "http_settings", null) != null ? [each.value.http_settings] : []
      content {
        uri                    = lookup(http_settings.value, "uri", null)
        source_deletion_option = lookup(http_settings.value, "source_deletion_option", null)
        source_type            = lookup(http_settings.value, "source_type", null)
      }
    }

    dynamic "https_push_amazon_kinesis_firehose_settings" {
      for_each = lookup(each.value, "https_push_amazon_kinesis_firehose_settings", null) != null ? [each.value.https_push_amazon_kinesis_firehose_settings] : []
      content {
        split_delimiter = lookup(https_push_amazon_kinesis_firehose_settings.value, "split_delimiter", null)
      }
    }

    dynamic "https_push_google_cloud_pubsub_settings" {
      for_each = lookup(each.value, "https_push_google_cloud_pubsub_settings", null) != null ? [each.value.https_push_google_cloud_pubsub_settings] : []
      content {
        split_delimiter = lookup(https_push_google_cloud_pubsub_settings.value, "split_delimiter", null)
      }
    }

    dynamic "https_push_webhook_settings" {
      for_each = lookup(each.value, "https_push_webhook_settings", null) != null ? [each.value.https_push_webhook_settings] : []
      content {
        split_delimiter = lookup(https_push_webhook_settings.value, "split_delimiter", null)
      }
    }

    dynamic "imperva_waf_settings" {
      for_each = lookup(each.value, "imperva_waf_settings", null) != null ? [each.value.imperva_waf_settings] : []
      content {
        dynamic "authentication" {
          for_each = lookup(imperva_waf_settings.value, "authentication", null) != null ? [imperva_waf_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "mandiant_ioc_settings" {
      for_each = lookup(each.value, "mandiant_ioc_settings", null) != null ? [each.value.mandiant_ioc_settings] : []
      content {
        start_time = lookup(mandiant_ioc_settings.value, "start_time", null)
        dynamic "authentication" {
          for_each = lookup(mandiant_ioc_settings.value, "authentication", null) != null ? [mandiant_ioc_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "microsoft_graph_alert_settings" {
      for_each = lookup(each.value, "microsoft_graph_alert_settings", null) != null ? [each.value.microsoft_graph_alert_settings] : []
      content {
        auth_endpoint = lookup(microsoft_graph_alert_settings.value, "auth_endpoint", null)
        hostname      = lookup(microsoft_graph_alert_settings.value, "hostname", null)
        tenant_id     = lookup(microsoft_graph_alert_settings.value, "tenant_id", null)
        dynamic "authentication" {
          for_each = lookup(microsoft_graph_alert_settings.value, "authentication", null) != null ? [microsoft_graph_alert_settings.value.authentication] : []
          content {
            client_id     = lookup(authentication.value, "client_id", null)
            client_secret = lookup(authentication.value, "client_secret", null)
          }
        }
      }
    }

    dynamic "microsoft_security_center_alert_settings" {
      for_each = lookup(each.value, "microsoft_security_center_alert_settings", null) != null ? [each.value.microsoft_security_center_alert_settings] : []
      content {
        auth_endpoint   = lookup(microsoft_security_center_alert_settings.value, "auth_endpoint", null)
        hostname        = lookup(microsoft_security_center_alert_settings.value, "hostname", null)
        subscription_id = lookup(microsoft_security_center_alert_settings.value, "subscription_id", null)
        tenant_id       = lookup(microsoft_security_center_alert_settings.value, "tenant_id", null)
        dynamic "authentication" {
          for_each = lookup(microsoft_security_center_alert_settings.value, "authentication", null) != null ? [microsoft_security_center_alert_settings.value.authentication] : []
          content {
            client_id     = lookup(authentication.value, "client_id", null)
            client_secret = lookup(authentication.value, "client_secret", null)
          }
        }
      }
    }

    dynamic "mimecast_mail_settings" {
      for_each = lookup(each.value, "mimecast_mail_settings", null) != null ? [each.value.mimecast_mail_settings] : []
      content {
        hostname = lookup(mimecast_mail_settings.value, "hostname", null)
        dynamic "authentication" {
          for_each = lookup(mimecast_mail_settings.value, "authentication", null) != null ? [mimecast_mail_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "mimecast_mail_v2_settings" {
      for_each = lookup(each.value, "mimecast_mail_v2_settings", null) != null ? [each.value.mimecast_mail_v2_settings] : []
      content {
        dynamic "auth_credentials" {
          for_each = lookup(mimecast_mail_v2_settings.value, "auth_credentials", null) != null ? [mimecast_mail_v2_settings.value.auth_credentials] : []
          content {
            client_id     = lookup(auth_credentials.value, "client_id", null)
            client_secret = lookup(auth_credentials.value, "client_secret", null)
          }
        }
      }
    }

    dynamic "netskope_alert_settings" {
      for_each = lookup(each.value, "netskope_alert_settings", null) != null ? [each.value.netskope_alert_settings] : []
      content {
        content_type = lookup(netskope_alert_settings.value, "content_type", null)
        feedname     = lookup(netskope_alert_settings.value, "feedname", null)
        hostname     = lookup(netskope_alert_settings.value, "hostname", null)
        dynamic "authentication" {
          for_each = lookup(netskope_alert_settings.value, "authentication", null) != null ? [netskope_alert_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "netskope_alert_v2_settings" {
      for_each = lookup(each.value, "netskope_alert_v2_settings", null) != null ? [each.value.netskope_alert_v2_settings] : []
      content {
        content_category = lookup(netskope_alert_v2_settings.value, "content_category", null)
        content_types    = lookup(netskope_alert_v2_settings.value, "content_types", null)
        hostname         = lookup(netskope_alert_v2_settings.value, "hostname", null)
        dynamic "authentication" {
          for_each = lookup(netskope_alert_v2_settings.value, "authentication", null) != null ? [netskope_alert_v2_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "office365_settings" {
      for_each = lookup(each.value, "office365_settings", null) != null ? [each.value.office365_settings] : []
      content {
        auth_endpoint = lookup(office365_settings.value, "auth_endpoint", null)
        hostname      = lookup(office365_settings.value, "hostname", null)
        tenant_id     = lookup(office365_settings.value, "tenant_id", null)
        content_type  = lookup(office365_settings.value, "content_type", null)
        dynamic "authentication" {
          for_each = lookup(office365_settings.value, "authentication", null) != null ? [office365_settings.value.authentication] : []
          content {
            client_id     = lookup(authentication.value, "client_id", null)
            client_secret = lookup(authentication.value, "client_secret", null)
          }
        }
      }
    }

    dynamic "okta_settings" {
      for_each = lookup(each.value, "okta_settings", null) != null ? [each.value.okta_settings] : []
      content {
        hostname = lookup(okta_settings.value, "hostname", null)
        dynamic "authentication" {
          for_each = lookup(okta_settings.value, "authentication", null) != null ? [okta_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "okta_user_context_settings" {
      for_each = lookup(each.value, "okta_user_context_settings", null) != null ? [each.value.okta_user_context_settings] : []
      content {
        hostname                   = lookup(okta_user_context_settings.value, "hostname", null)
        manager_id_reference_field = lookup(okta_user_context_settings.value, "manager_id_reference_field", null)
        dynamic "authentication" {
          for_each = lookup(okta_user_context_settings.value, "authentication", null) != null ? [okta_user_context_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "pan_ioc_settings" {
      for_each = lookup(each.value, "pan_ioc_settings", null) != null ? [each.value.pan_ioc_settings] : []
      content {
        feed    = lookup(pan_ioc_settings.value, "feed", null)
        feed_id = lookup(pan_ioc_settings.value, "feed_id", null)
        dynamic "authentication" {
          for_each = lookup(pan_ioc_settings.value, "authentication", null) != null ? [pan_ioc_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "pan_prisma_cloud_settings" {
      for_each = lookup(each.value, "pan_prisma_cloud_settings", null) != null ? [each.value.pan_prisma_cloud_settings] : []
      content {
        hostname = lookup(pan_prisma_cloud_settings.value, "hostname", null)
        dynamic "authentication" {
          for_each = lookup(pan_prisma_cloud_settings.value, "authentication", null) != null ? [pan_prisma_cloud_settings.value.authentication] : []
          content {
            user     = lookup(authentication.value, "user", null)
            password = lookup(authentication.value, "password", null)
          }
        }
      }
    }

    dynamic "proofpoint_mail_settings" {
      for_each = lookup(each.value, "proofpoint_mail_settings", null) != null ? [each.value.proofpoint_mail_settings] : []
      content {
        dynamic "authentication" {
          for_each = lookup(proofpoint_mail_settings.value, "authentication", null) != null ? [proofpoint_mail_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
      }
    }

    dynamic "proofpoint_on_demand_settings" {
      for_each = lookup(each.value, "proofpoint_on_demand_settings", null) != null ? [each.value.proofpoint_on_demand_settings] : []
      content {
        cluster_id = lookup(proofpoint_on_demand_settings.value, "cluster_id", null)
        dynamic "authentication" {
          for_each = lookup(proofpoint_on_demand_settings.value, "authentication", null) != null ? [proofpoint_on_demand_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "pubsub_settings" {
      for_each = lookup(each.value, "pubsub_settings", null) != null ? [each.value.pubsub_settings] : []
      content {
        google_service_account_email = lookup(pubsub_settings.value, "google_service_account_email", null)
      }
    }

    dynamic "qualys_scan_settings" {
      for_each = lookup(each.value, "qualys_scan_settings", null) != null ? [each.value.qualys_scan_settings] : []
      content {
        api_type = lookup(qualys_scan_settings.value, "api_type", null)
        hostname = lookup(qualys_scan_settings.value, "hostname", null)
        dynamic "authentication" {
          for_each = lookup(qualys_scan_settings.value, "authentication", null) != null ? [qualys_scan_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
      }
    }

    dynamic "qualys_vm_settings" {
      for_each = lookup(each.value, "qualys_vm_settings", null) != null ? [each.value.qualys_vm_settings] : []
      content {
        hostname = lookup(qualys_vm_settings.value, "hostname", null)
        dynamic "authentication" {
          for_each = lookup(qualys_vm_settings.value, "authentication", null) != null ? [qualys_vm_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
      }
    }

    dynamic "rapid7_insight_settings" {
      for_each = lookup(each.value, "rapid7_insight_settings", null) != null ? [each.value.rapid7_insight_settings] : []
      content {
        endpoint = lookup(rapid7_insight_settings.value, "endpoint", null)
        hostname = lookup(rapid7_insight_settings.value, "hostname", null)
        dynamic "authentication" {
          for_each = lookup(rapid7_insight_settings.value, "authentication", null) != null ? [rapid7_insight_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "recorded_future_ioc_settings" {
      for_each = lookup(each.value, "recorded_future_ioc_settings", null) != null ? [each.value.recorded_future_ioc_settings] : []
      content {
        dynamic "authentication" {
          for_each = lookup(recorded_future_ioc_settings.value, "authentication", null) != null ? [recorded_future_ioc_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "rh_isac_ioc_settings" {
      for_each = lookup(each.value, "rh_isac_ioc_settings", null) != null ? [each.value.rh_isac_ioc_settings] : []
      content {
        dynamic "authentication" {
          for_each = lookup(rh_isac_ioc_settings.value, "authentication", null) != null ? [rh_isac_ioc_settings.value.authentication] : []
          content {
            client_id      = lookup(authentication.value, "client_id", null)
            client_secret  = lookup(authentication.value, "client_secret", null)
            token_endpoint = lookup(authentication.value, "token_endpoint", null)
          }
        }
      }
    }

    dynamic "salesforce_settings" {
      for_each = lookup(each.value, "salesforce_settings", null) != null ? [each.value.salesforce_settings] : []
      content {
        hostname = lookup(salesforce_settings.value, "hostname", null)
        dynamic "oauth_jwt_credentials" {
          for_each = lookup(salesforce_settings.value, "oauth_jwt_credentials", null) != null ? [salesforce_settings.value.oauth_jwt_credentials] : []
          content {
            token_endpoint = lookup(oauth_jwt_credentials.value, "token_endpoint", null)
            dynamic "claims" {
              for_each = lookup(oauth_jwt_credentials.value, "claims", null) != null ? [oauth_jwt_credentials.value.claims] : []
              content {
                audience = lookup(claims.value, "audience", null)
                issuer   = lookup(claims.value, "issuer", null)
                subject  = lookup(claims.value, "subject", null)
              }
            }
            dynamic "rs_credentials" {
              for_each = lookup(oauth_jwt_credentials.value, "rs_credentials", null) != null ? [oauth_jwt_credentials.value.rs_credentials] : []
              content {
                private_key = lookup(rs_credentials.value, "private_key", null)
              }
            }
          }
        }
        dynamic "oauth_password_grant_auth" {
          for_each = lookup(salesforce_settings.value, "oauth_password_grant_auth", null) != null ? [salesforce_settings.value.oauth_password_grant_auth] : []
          content {
            token_endpoint = lookup(oauth_password_grant_auth.value, "token_endpoint", null)
            client_id      = lookup(oauth_password_grant_auth.value, "client_id", null)
            client_secret  = lookup(oauth_password_grant_auth.value, "client_secret", null)
            user           = lookup(oauth_password_grant_auth.value, "user", null)
            password       = lookup(oauth_password_grant_auth.value, "password", null)
          }
        }
      }
    }

    dynamic "sentinelone_alert_settings" {
      for_each = lookup(each.value, "sentinelone_alert_settings", null) != null ? [each.value.sentinelone_alert_settings] : []
      content {
        hostname                = lookup(sentinelone_alert_settings.value, "hostname", null)
        initial_start_time      = lookup(sentinelone_alert_settings.value, "initial_start_time", null)
        is_alert_api_subscribed = lookup(sentinelone_alert_settings.value, "is_alert_api_subscribed", null)
        dynamic "authentication" {
          for_each = lookup(sentinelone_alert_settings.value, "authentication", null) != null ? [sentinelone_alert_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "service_now_cmdb_settings" {
      for_each = lookup(each.value, "service_now_cmdb_settings", null) != null ? [each.value.service_now_cmdb_settings] : []
      content {
        feedname = lookup(service_now_cmdb_settings.value, "feedname", null)
        hostname = lookup(service_now_cmdb_settings.value, "hostname", null)
        dynamic "authentication" {
          for_each = lookup(service_now_cmdb_settings.value, "authentication", null) != null ? [service_now_cmdb_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
      }
    }

    dynamic "sftp_settings" {
      for_each = lookup(each.value, "sftp_settings", null) != null ? [each.value.sftp_settings] : []
      content {
        uri                    = lookup(sftp_settings.value, "uri", null)
        source_deletion_option = lookup(sftp_settings.value, "source_deletion_option", null)
        source_type            = lookup(sftp_settings.value, "source_type", null)
        dynamic "authentication" {
          for_each = lookup(sftp_settings.value, "authentication", null) != null ? [sftp_settings.value.authentication] : []
          content {
            username               = lookup(authentication.value, "username", null)
            password               = lookup(authentication.value, "password", null)
            private_key            = lookup(authentication.value, "private_key", null)
            private_key_passphrase = lookup(authentication.value, "private_key_passphrase", null)
          }
        }
      }
    }

    dynamic "symantec_event_export_settings" {
      for_each = lookup(each.value, "symantec_event_export_settings", null) != null ? [each.value.symantec_event_export_settings] : []
      content {
        dynamic "authentication" {
          for_each = lookup(symantec_event_export_settings.value, "authentication", null) != null ? [symantec_event_export_settings.value.authentication] : []
          content {
            token_endpoint = lookup(authentication.value, "token_endpoint", null)
            client_id      = lookup(authentication.value, "client_id", null)
            client_secret  = lookup(authentication.value, "client_secret", null)
            refresh_token  = lookup(authentication.value, "refresh_token", null)
          }
        }
      }
    }

    dynamic "thinkst_canary_settings" {
      for_each = lookup(each.value, "thinkst_canary_settings", null) != null ? [each.value.thinkst_canary_settings] : []
      content {
        hostname = lookup(thinkst_canary_settings.value, "hostname", null)
        dynamic "authentication" {
          for_each = lookup(thinkst_canary_settings.value, "authentication", null) != null ? [thinkst_canary_settings.value.authentication] : []
          content {
            dynamic "header_key_values" {
              for_each = lookup(authentication.value, "header_key_values", [])
              content {
                key   = lookup(header_key_values.value, "key", null)
                value = lookup(header_key_values.value, "value", null)
              }
            }
          }
        }
      }
    }

    dynamic "threat_connect_ioc_settings" {
      for_each = lookup(each.value, "threat_connect_ioc_settings", null) != null ? [each.value.threat_connect_ioc_settings] : []
      content {
        hostname = lookup(threat_connect_ioc_settings.value, "hostname", null)
        owners   = lookup(threat_connect_ioc_settings.value, "owners", null)
        dynamic "authentication" {
          for_each = lookup(threat_connect_ioc_settings.value, "authentication", null) != null ? [threat_connect_ioc_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
      }
    }

    dynamic "threat_connect_ioc_v3_settings" {
      for_each = lookup(each.value, "threat_connect_ioc_v3_settings", null) != null ? [each.value.threat_connect_ioc_v3_settings] : []
      content {
        hostname  = lookup(threat_connect_ioc_v3_settings.value, "hostname", null)
        owners    = lookup(threat_connect_ioc_v3_settings.value, "owners", null)
        fields    = lookup(threat_connect_ioc_v3_settings.value, "fields", null)
        schedule  = lookup(threat_connect_ioc_v3_settings.value, "schedule", null)
        tql_query = lookup(threat_connect_ioc_v3_settings.value, "tql_query", null)
        dynamic "authentication" {
          for_each = lookup(threat_connect_ioc_v3_settings.value, "authentication", null) != null ? [threat_connect_ioc_v3_settings.value.authentication] : []
          content {
            user   = lookup(authentication.value, "user", null)
            secret = lookup(authentication.value, "secret", null)
          }
        }
      }
    }

    dynamic "trellix_hx_alerts_settings" {
      for_each = lookup(each.value, "trellix_hx_alerts_settings", null) != null ? [each.value.trellix_hx_alerts_settings] : []
      content {
        endpoint = lookup(trellix_hx_alerts_settings.value, "endpoint", null)
        dynamic "authentication" {
          for_each = lookup(trellix_hx_alerts_settings.value, "authentication", null) != null ? [trellix_hx_alerts_settings.value.authentication] : []
          content {
            dynamic "msso" {
              for_each = lookup(authentication.value, "msso", null) != null ? [authentication.value.msso] : []
              content {
                api_endpoint = lookup(msso.value, "api_endpoint", null)
                username     = lookup(msso.value, "username", null)
                password     = lookup(msso.value, "password", null)
              }
            }
            dynamic "trellix_iam" {
              for_each = lookup(authentication.value, "trellix_iam", null) != null ? [authentication.value.trellix_iam] : []
              content {
                client_id     = lookup(trellix_iam.value, "client_id", null)
                client_secret = lookup(trellix_iam.value, "client_secret", null)
                scope         = lookup(trellix_iam.value, "scope", null)
              }
            }
          }
        }
      }
    }

    dynamic "trellix_hx_bulk_acqs_settings" {
      for_each = lookup(each.value, "trellix_hx_bulk_acqs_settings", null) != null ? [each.value.trellix_hx_bulk_acqs_settings] : []
      content {
        endpoint = trellix_hx_bulk_acqs_settings.value.endpoint
        dynamic "authentication" {
          for_each = lookup(trellix_hx_bulk_acqs_settings.value, "authentication", null) != null ? [trellix_hx_bulk_acqs_settings.value.authentication] : []
          content {
            dynamic "msso" {
              for_each = lookup(authentication.value, "msso", null) != null ? [authentication.value.msso] : []
              content {
                api_endpoint = msso.value.api_endpoint
                username     = msso.value.username
                password     = msso.value.password
              }
            }
            dynamic "trellix_iam" {
              for_each = lookup(authentication.value, "trellix_iam", null) != null ? [authentication.value.trellix_iam] : []
              content {
                client_id     = trellix_iam.value.client_id
                client_secret = trellix_iam.value.client_secret
                scope         = trellix_iam.value.scope
              }
            }
          }
        }
      }
    }

    dynamic "trellix_hx_hosts_settings" {
      for_each = lookup(each.value, "trellix_hx_hosts_settings", null) != null ? [each.value.trellix_hx_hosts_settings] : []
      content {
        endpoint = trellix_hx_hosts_settings.value.endpoint
        dynamic "authentication" {
          for_each = lookup(trellix_hx_hosts_settings.value, "authentication", null) != null ? [trellix_hx_hosts_settings.value.authentication] : []
          content {
            dynamic "msso" {
              for_each = lookup(authentication.value, "msso", null) != null ? [authentication.value.msso] : []
              content {
                api_endpoint = msso.value.api_endpoint
                username     = msso.value.username
                password     = msso.value.password
              }
            }
            dynamic "trellix_iam" {
              for_each = lookup(authentication.value, "trellix_iam", null) != null ? [authentication.value.trellix_iam] : []
              content {
                client_id     = trellix_iam.value.client_id
                client_secret = trellix_iam.value.client_secret
                scope         = trellix_iam.value.scope
              }
            }
          }
        }
      }
    }

    dynamic "webhook_settings" {
      for_each = lookup(each.value, "webhook_settings", null) != null ? [each.value.webhook_settings] : []
      content {
      }
    }

    dynamic "workday_settings" {
      for_each = lookup(each.value, "workday_settings", null) != null ? [each.value.workday_settings] : []
      content {
        hostname  = lookup(workday_settings.value, "hostname", null)
        tenant_id = lookup(workday_settings.value, "tenant_id", null)
        dynamic "authentication" {
          for_each = lookup(workday_settings.value, "authentication", null) != null ? [workday_settings.value.authentication] : []
          content {
            user           = lookup(authentication.value, "user", null)
            secret         = lookup(authentication.value, "secret", null)
            token_endpoint = lookup(authentication.value, "token_endpoint", null)
            client_id      = lookup(authentication.value, "client_id", null)
            client_secret  = lookup(authentication.value, "client_secret", null)
            refresh_token  = lookup(authentication.value, "refresh_token", null)
          }
        }
      }
    }

    dynamic "workspace_activity_settings" {
      for_each = lookup(each.value, "workspace_activity_settings", null) != null ? [each.value.workspace_activity_settings] : []
      content {
        workspace_customer_id = lookup(workspace_activity_settings.value, "workspace_customer_id", null)
        applications          = lookup(workspace_activity_settings.value, "applications", null)
        dynamic "authentication" {
          for_each = lookup(workspace_activity_settings.value, "authentication", null) != null ? [workspace_activity_settings.value.authentication] : []
          content {
            token_endpoint = lookup(authentication.value, "token_endpoint", null)
            dynamic "claims" {
              for_each = lookup(authentication.value, "claims", null) != null ? [authentication.value.claims] : []
              content {
                audience = lookup(claims.value, "audience", null)
                issuer   = lookup(claims.value, "issuer", null)
                subject  = lookup(claims.value, "subject", null)
              }
            }
            rs_credentials {
              private_key = try(data.google_secret_manager_secret_version.value.secret_data, lookup(rs_credentials.value, "private_key", null))
            }
          }
        }
      }
    }

    dynamic "workspace_alerts_settings" {
      for_each = lookup(each.value, "workspace_alerts_settings", null) != null ? [each.value.workspace_alerts_settings] : []
      content {
        workspace_customer_id = lookup(workspace_alerts_settings.value, "workspace_customer_id", null)
        dynamic "authentication" {
          for_each = lookup(workspace_alerts_settings.value, "authentication", null) != null ? [workspace_alerts_settings.value.authentication] : []
          content {
            token_endpoint = lookup(authentication.value, "token_endpoint", null)
            dynamic "claims" {
              for_each = lookup(authentication.value, "claims", null) != null ? [authentication.value.claims] : []
              content {
                audience = lookup(claims.value, "audience", null)
                issuer   = lookup(claims.value, "issuer", null)
                subject  = lookup(claims.value, "subject", null)
              }
            }
            rs_credentials {
              private_key = try(data.google_secret_manager_secret_version.value.secret_data, lookup(rs_credentials.value, "private_key", null))
            }
          }
        }
      }
    }

    dynamic "workspace_chrome_os_settings" {
      for_each = lookup(each.value, "workspace_chrome_os_settings", null) != null ? [each.value.workspace_chrome_os_settings] : []
      content {
        workspace_customer_id = lookup(workspace_chrome_os_settings.value, "workspace_customer_id", null)
        dynamic "authentication" {
          for_each = lookup(workspace_chrome_os_settings.value, "authentication", null) != null ? [workspace_chrome_os_settings.value.authentication] : []
          content {
            token_endpoint = lookup(authentication.value, "token_endpoint", null)
            dynamic "claims" {
              for_each = lookup(authentication.value, "claims", null) != null ? [authentication.value.claims] : []
              content {
                audience = lookup(claims.value, "audience", null)
                issuer   = lookup(claims.value, "issuer", null)
                subject  = lookup(claims.value, "subject", null)
              }
            }
            rs_credentials {
              private_key = try(data.google_secret_manager_secret_version.value.secret_data, lookup(rs_credentials.value, "private_key", null))
            }
          }
        }
      }
    }

    dynamic "workspace_groups_settings" {
      for_each = lookup(each.value, "workspace_groups_settings", null) != null ? [each.value.workspace_groups_settings] : []
      content {
        workspace_customer_id = lookup(workspace_groups_settings.value, "workspace_customer_id", null)
        dynamic "authentication" {
          for_each = lookup(workspace_groups_settings.value, "authentication", null) != null ? [workspace_groups_settings.value.authentication] : []
          content {
            token_endpoint = lookup(authentication.value, "token_endpoint", null)
            dynamic "claims" {
              for_each = lookup(authentication.value, "claims", null) != null ? [authentication.value.claims] : []
              content {
                audience = lookup(claims.value, "audience", null)
                issuer   = lookup(claims.value, "issuer", null)
                subject  = lookup(claims.value, "subject", null)
              }
            }
            rs_credentials {
              private_key = try(data.google_secret_manager_secret_version.value.secret_data, lookup(rs_credentials.value, "private_key", null))
            }
          }
        }
      }
    }

    dynamic "workspace_mobile_settings" {
      for_each = lookup(each.value, "workspace_mobile_settings", null) != null ? [each.value.workspace_mobile_settings] : []
      content {
        workspace_customer_id = lookup(workspace_mobile_settings.value, "workspace_customer_id", null)
        dynamic "authentication" {
          for_each = lookup(workspace_mobile_settings.value, "authentication", null) != null ? [workspace_mobile_settings.value.authentication] : []
          content {
            token_endpoint = lookup(authentication.value, "token_endpoint", null)
            dynamic "claims" {
              for_each = lookup(authentication.value, "claims", null) != null ? [authentication.value.claims] : []
              content {
                audience = lookup(claims.value, "audience", null)
                issuer   = lookup(claims.value, "issuer", null)
                subject  = lookup(claims.value, "subject", null)
              }
            }
            rs_credentials {
              private_key = try(data.google_secret_manager_secret_version.value.secret_data, lookup(rs_credentials.value, "private_key", null))
            }
          }
        }
      }
    }

    dynamic "workspace_privileges_settings" {
      for_each = lookup(each.value, "workspace_privileges_settings", null) != null ? [each.value.workspace_privileges_settings] : []
      content {
        workspace_customer_id = lookup(workspace_privileges_settings.value, "workspace_customer_id", null)
        dynamic "authentication" {
          for_each = lookup(workspace_privileges_settings.value, "authentication", null) != null ? [workspace_privileges_settings.value.authentication] : []
          content {
            token_endpoint = lookup(authentication.value, "token_endpoint", null)
            dynamic "claims" {
              for_each = lookup(authentication.value, "claims", null) != null ? [authentication.value.claims] : []
              content {
                audience = lookup(claims.value, "audience", null)
                issuer   = lookup(claims.value, "issuer", null)
                subject  = lookup(claims.value, "subject", null)
              }
            }
            rs_credentials {
              private_key = try(data.google_secret_manager_secret_version.value.secret_data, lookup(rs_credentials.value, "private_key", null))
            }
          }
        }
      }
    }

    dynamic "workspace_users_settings" {
      for_each = lookup(each.value, "workspace_users_settings", null) != null ? [each.value.workspace_users_settings] : []
      content {
        workspace_customer_id = lookup(workspace_users_settings.value, "workspace_customer_id", null)
        projection_type       = lookup(workspace_users_settings.value, "projection_type", null)
        dynamic "authentication" {
          for_each = lookup(workspace_users_settings.value, "authentication", null) != null ? [workspace_users_settings.value.authentication] : []
          content {
            token_endpoint = lookup(authentication.value, "token_endpoint", null)
            dynamic "claims" {
              for_each = lookup(authentication.value, "claims", null) != null ? [authentication.value.claims] : []
              content {
                audience = lookup(claims.value, "audience", null)
                issuer   = lookup(claims.value, "issuer", null)
                subject  = lookup(claims.value, "subject", null)
              }
            }
            rs_credentials {
              private_key = try(data.google_secret_manager_secret_version.value.secret_data, lookup(rs_credentials.value, "private_key", null))
            }
          }
        }
      }
    }
  }
}

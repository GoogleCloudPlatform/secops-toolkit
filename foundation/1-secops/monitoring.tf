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

# tfdoc:file:description Cloud Monitoring.

resource "google_monitoring_notification_channel" "email_notification" {
  for_each     = var.monitoring_config.enabled ? toset(var.monitoring_config.notification_emails) : []
  project      = module.project.project_id
  display_name = "SecOps Notification email"
  type         = "email"
  labels = {
    email_address = each.value
  }
}

resource "google_monitoring_alert_policy" "chronicle_ingestion_alert" {
  count                 = var.monitoring_config.enabled ? 1 : 0
  project               = module.project.project_id
  display_name          = "SecOps Ingestion Rate close to ingestion limit."
  combiner              = "OR"
  notification_channels = [for _, channel in google_monitoring_notification_channel.email_notification : channel.name]
  user_labels = {
    severity = "warning"
  }

  conditions {
    display_name = "SecOps ingestion is over 80% of the quota"
    condition_prometheus_query_language {
      query               = "100 * sum(rate(chronicle_googleapis_com:ingestion_log_bytes_count{monitored_resource=\"chronicle.googleapis.com/Collector\"}[10m])) / min(min_over_time(chronicle_googleapis_com:ingestion_quota_limit{monitored_resource=\"chronicle.googleapis.com/Collector\"}[10m])) > 80"
      duration            = "120s" # 2 minutes
      evaluation_interval = "60s"  # 1 minute
    }
  }

  # Documentation to include in the notification
  documentation {
    content   = "The SecOps data ingestion rate has exceeded 80% of the provisioned quota. Please investigate the data sources to prevent potential data loss."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "secops_forwarder_silence" {
  count                 = var.monitoring_config.enabled ? 1 : 0
  project               = module.project.project_id
  display_name          = "Detect Silent Google SecOps Forwarders"
  combiner              = "OR"
  notification_channels = [for _, channel in google_monitoring_notification_channel.email_notification : channel.name]
  user_labels = {
    severity = "warning"
  }

  conditions {
    display_name = "No logs received from a SecOps forwarder for 60 minutes"
    condition_absent {
      duration = "3600s" # 60 minutes
      filter   = "metric.type=\"chronicle.googleapis.com/ingestion/log/record_count\" resource.type=\"chronicle.googleapis.com/Collector\""
      aggregations {
        alignment_period     = "3600s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_MEAN"
        group_by_fields = [
          "resource.label.collector_id",
        ]
      }
      trigger {
        count = 1
      }
    }
  }
  alert_strategy {
    auto_close = "604800s" # 7 days
  }
  documentation {
    content   = "This policy triggers an alert when a Google SecOps forwarder (collector_id: $${resource.label.collector_id}) has not sent any logs for 60 minutes."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "secops_normalized_events_drop" {
  count                 = var.monitoring_config.enabled ? 1 : 0
  project               = module.project.project_id
  display_name          = "Detect drop in events normalized per raw loogs ingested in Google SecOps"
  combiner              = "OR"
  notification_channels = [for _, channel in google_monitoring_notification_channel.email_notification : channel.name]
  user_labels = {
    severity = "warning"
  }

  conditions {
    display_name = "Decrease in ration between ingested raw logs and events normalized per log type for 60 minutes"
    condition_prometheus_query_language {
      query               = "100 * abs(sum by (log_type) (chronicle_googleapis_com:ingestion_log_record_count{monitored_resource=\"chronicle.googleapis.com/Collector\"}) - sum by (log_type) (chronicle_googleapis_com:normalizer_event_record_count{monitored_resource=\"chronicle.googleapis.com/Collector\"})) / sum by (log_type) (chronicle_googleapis_com:ingestion_log_record_count{monitored_resource=\"chronicle.googleapis.com/Collector\"}) > 50"
      duration            = "3600s" # 1 hour
      evaluation_interval = "3600s" # 1 hour
    }
  }
  alert_strategy {
    auto_close = "604800s" # 7 days
  }
  documentation {
    content   = "This policy triggers an alert when a Google SecOps forwarder (log_type: $${resource.label.log_type}) has not sent any logs for 60 minutes."
    mime_type = "text/markdown"
  }
}

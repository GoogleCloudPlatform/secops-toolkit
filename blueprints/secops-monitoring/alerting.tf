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

# ------------------------------------------------------------------------------
# Alerting Policies - Ingestion
# ------------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "chronicle_ingestion_alert" {
  enabled               = var.monitoring_config.alerts_enabled
  count                 = var.monitoring_config.enabled ? 1 : 0
  project               = var.project_id
  display_name          = "SecOps Ingestion Rate close to ingestion limit."
  combiner              = "OR"
  notification_channels = [for _, channel in google_monitoring_notification_channel.channels : channel.name]
  user_labels = {
    severity = "warning"
  }

  conditions {
    display_name = "SecOps ingestion is over 80% of the quota"
    condition_prometheus_query_language {
      query               = "100 * sum(rate(chronicle_googleapis_com:ingestion_log_bytes_count{monitored_resource=\"chronicle.googleapis.com/Collector\"}[10m])) / min(min_over_time(chronicle_googleapis_com:ingestion_quota_limit{monitored_resource=\"chronicle.googleapis.com/Collector\"}[10m])) > 80"
      duration            = "600s"
      evaluation_interval = "60s"
    }
  }

  documentation {
    content   = "The SecOps data ingestion rate has exceeded 80% of the provisioned quota. Please investigate the data sources to prevent potential data loss."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "ingestion_quota_rejection" {
  enabled               = var.monitoring_config.alerts_enabled
  count                 = var.monitoring_config.enabled ? 1 : 0
  project               = var.project_id
  display_name          = "Ingestion Quota Rejection Alert Policy"
  combiner              = "OR"
  notification_channels = [for _, channel in google_monitoring_notification_channel.channels : channel.name]
  user_labels = {
    severity = "warning"
  }

  conditions {
    display_name = "Ingestion Quota Rejection"
    condition_prometheus_query_language {
      query               = "sum(rate(chronicle_googleapis_com:ingestion_log_quota_rejected_bytes_count{monitored_resource=\"chronicle.googleapis.com/Collector\"}[5m])) > 0"
      duration            = "300s"
      evaluation_interval = "60s"
    }
  }

  alert_strategy {
    auto_close = "604800s"
  }
}


# ------------------------------------------------------------------------------
# Alerting Policies - Forwarders
# ------------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "forwarder_buffer_usage" {
  enabled               = var.monitoring_config.alerts_enabled
  count                 = var.monitoring_config.enabled ? 1 : 0
  project               = var.project_id
  display_name          = "Forwarder Buffer Usage High"
  combiner              = "OR"
  notification_channels = [for _, channel in google_monitoring_notification_channel.channels : channel.name]
  user_labels = {
    severity = "warning"
  }

  conditions {
    display_name = "Forwarder mean buffer used is more than 1% over 1 hour window"
    condition_threshold {
      filter          = "resource.type = \"chronicle.googleapis.com/Collector\" AND metric.type = \"chronicle.googleapis.com/forwarder/buffer_used\" AND (metric.labels.input_type = \"pcap\" AND metric.labels.buffer_type = \"memory\")"
      duration        = "0s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.01
      aggregations {
        alignment_period     = "3600s"
        per_series_aligner   = "ALIGN_MEAN"
        cross_series_reducer = "REDUCE_MEAN"
        group_by_fields      = ["resource.label.project_id"]
      }
    }
  }
}

resource "google_monitoring_alert_policy" "secops_forwarder_silence" {
  enabled               = var.monitoring_config.alerts_enabled
  count                 = var.monitoring_config.enabled ? 1 : 0
  project               = var.project_id
  display_name          = "Detect Silent Google SecOps Forwarders"
  combiner              = "OR"
  notification_channels = [for _, channel in google_monitoring_notification_channel.channels : channel.name]
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

resource "google_monitoring_alert_policy" "forwarder_log_type_silence" {
  enabled               = var.monitoring_config.alerts_enabled
  count                 = var.monitoring_config.enabled ? 1 : 0
  project               = var.project_id
  display_name          = "Silent Chronicle Forwarder and LogType"
  combiner              = "OR"
  notification_channels = [for _, channel in google_monitoring_notification_channel.channels : channel.name]
  user_labels = {
    severity = "warning"
  }

  conditions {
    display_name = "Chronicle forwarder and logtypes silent for 1 hour"
    condition_absent {
      filter   = "resource.type = \"chronicle.googleapis.com/Collector\" AND metric.type = \"chronicle.googleapis.com/ingestion/log/record_count\""
      duration = "3600s"
      aggregations {
        alignment_period     = "3600s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_MEAN"
        group_by_fields      = ["resource.label.collector_id", "resource.label.log_type"]
      }
      trigger {
        count = 1
      }
    }
  }
}

# ------------------------------------------------------------------------------
# Alerting Policies - Normalized Events
# ------------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "secops_normalized_events_drop" {
  enabled               = var.monitoring_config.alerts_enabled
  count                 = var.monitoring_config.enabled ? 1 : 0
  project               = var.project_id
  display_name          = "Detect drop in events normalized per raw loogs ingested in Google SecOps"
  combiner              = "OR"
  notification_channels = [for _, channel in google_monitoring_notification_channel.channels : channel.name]
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

# ------------------------------------------------------------------------------
# Alerting Policies - Chronicle APIs
# ------------------------------------------------------------------------------

# Alert: High API Latency (Average > 2s for 5 minutes)
resource "google_monitoring_alert_policy" "high_latency_alert" {
  enabled               = var.monitoring_config.alerts_enabled
  project               = var.project_id
  display_name          = "Chronicle API - High Latency (>2s)"
  combiner              = "OR"
  notification_channels = [for _, channel in google_monitoring_notification_channel.channels : channel.name]
  user_labels = {
    severity = "warning"
  }

  conditions {
    display_name = "Latency is high"
    condition_threshold {
      filter     = "metric.type=\"serviceruntime.googleapis.com/api/request_latencies\" resource.type=\"consumed_api\" resource.label.service=\"chronicle.googleapis.com\""
      duration   = "300s" # 5 minutes
      comparison = "COMPARISON_GT"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_MEAN"
      }
      threshold_value = 2000 # 2000 ms = 2 seconds
    }
  }
}

# Alert: High Error Rate (5xx errors > 5% of traffic)
# Note: For simplicity, this example alerts if absolute 5xx count > 10 per second.
# Creating a true ratio alert (errors / total) requires Monitoring Query Language (MQL).
resource "google_monitoring_alert_policy" "high_error_rate_alert" {
  enabled               = var.monitoring_config.alerts_enabled
  project               = var.project_id
  display_name          = "Chronicle API - High 5xx Error Rate"
  combiner              = "OR"
  notification_channels = [for _, channel in google_monitoring_notification_channel.channels : channel.name]
  user_labels = {
    severity = "warning"
  }
  conditions {
    display_name = "High number of 5xx errors"
    condition_threshold {
      filter     = "metric.type=\"serviceruntime.googleapis.com/api/request_count\" resource.type=\"consumed_api\" resource.label.service=\"chronicle.googleapis.com\" metric.label.response_code_class=\"5xx\""
      duration   = "300s"
      comparison = "COMPARISON_GT"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }
      threshold_value = 0.1 # Alert if more than 0.1 errors per second (tune this value)
    }
  }
}

# Alert: Authentication Failures Spike
resource "google_monitoring_alert_policy" "auth_failure_alert" {
  enabled               = var.monitoring_config.alerts_enabled
  project               = var.project_id
  display_name          = "Chronicle API - High Auth Failures"
  combiner              = "OR"
  notification_channels = [for _, channel in google_monitoring_notification_channel.channels : channel.name]
  user_labels = {
    severity = "warning"
  }
  conditions {
    display_name = "High 401/403 Rate"
    condition_threshold {
      filter     = "metric.type=\"serviceruntime.googleapis.com/api/request_count\" resource.type=\"consumed_api\" resource.label.service=\"chronicle.googleapis.com\" (metric.label.response_code=\"401\" OR metric.label.response_code=\"403\")"
      duration   = "60s"
      comparison = "COMPARISON_GT"
      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
      }
      threshold_value = 5.0 # Alert if > 5 failures per second
    }
  }
}

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

# ------------------------------------------------------------------------------
# Cloud Monitoring Dashboards
# ------------------------------------------------------------------------------

resource "google_monitoring_dashboard" "secops_dashboard" {
  project        = var.project_id
  dashboard_json = <<EOF
{
  "displayName": "SecOps API & Ingestion Health",
  "gridLayout": {
    "columns": "2",
    "widgets": [
      {
        "title": "API Request Rate (RPS)",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"serviceruntime.googleapis.com/api/request_count\" resource.type=\"consumed_api\" resource.label.service=\"chronicle.googleapis.com\"",
                  "aggregation": {
                    "perSeriesAligner": "ALIGN_RATE",
                    "crossSeriesReducer": "REDUCE_SUM",
                    "alignmentPeriod": "60s",
                    "groupByFields": []
                  }
                },
                "unitOverride": "1/s"
              },
              "plotType": "LINE",
              "minAlignmentPeriod": "60s"
            }
          ],
          "timeshiftDuration": "0s",
          "yAxis": {
            "label": "y1Axis",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "API Latency (Avg vs Max)",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"serviceruntime.googleapis.com/api/request_latencies\" resource.type=\"consumed_api\" resource.label.service=\"chronicle.googleapis.com\"",
                  "aggregation": {
                    "perSeriesAligner": "ALIGN_DELTA",
                    "crossSeriesReducer": "REDUCE_MEAN",
                    "alignmentPeriod": "60s",
                    "groupByFields": []
                  }
                },
                "unitOverride": "ms"
              },
              "plotType": "LINE",
              "legendTemplate": "Average Latency"
            },
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"serviceruntime.googleapis.com/api/request_latencies\" resource.type=\"consumed_api\" resource.label.service=\"chronicle.googleapis.com\"",
                  "aggregation": {
                    "perSeriesAligner": "ALIGN_DELTA",
                    "crossSeriesReducer": "REDUCE_MAX",
                    "alignmentPeriod": "60s",
                    "groupByFields": []
                  }
                },
                "unitOverride": "ms"
              },
              "plotType": "LINE",
              "legendTemplate": "Max Latency"
            }
          ],
          "yAxis": {
            "label": "Latency (ms)",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "API Error Rate (4xx vs 5xx)",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"serviceruntime.googleapis.com/api/request_count\" resource.type=\"consumed_api\" resource.label.service=\"chronicle.googleapis.com\" metric.label.response_code_class = one_of(\"4xx\", \"5xx\")",
                  "aggregation": {
                    "perSeriesAligner": "ALIGN_RATE",
                    "crossSeriesReducer": "REDUCE_SUM",
                    "alignmentPeriod": "60s",
                    "groupByFields": ["metric.label.response_code_class"]
                  }
                }
              },
              "plotType": "STACKED_BAR",
              "minAlignmentPeriod": "60s"
            }
          ],
          "yAxis": {
            "label": "Errors / sec",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "Authentication Failures (401/403)",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"serviceruntime.googleapis.com/api/request_count\" resource.type=\"consumed_api\" resource.label.service=\"chronicle.googleapis.com\" metric.label.response_code = one_of(\"401\", \"403\")",
                  "aggregation": {
                    "perSeriesAligner": "ALIGN_RATE",
                    "crossSeriesReducer": "REDUCE_SUM",
                    "alignmentPeriod": "60s",
                    "groupByFields": ["metric.label.response_code"]
                  }
                }
              },
              "plotType": "LINE",
              "minAlignmentPeriod": "60s"
            }
          ]
        }
      },
      {
        "title": "Events per Second by Log Type",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"chronicle.googleapis.com/ingestion/log/record_count\"",
                  "aggregation": {
                    "perSeriesAligner": "ALIGN_RATE",
                    "crossSeriesReducer": "REDUCE_SUM",
                    "alignmentPeriod": "60s",
                    "groupByFields": ["resource.label.log_type"]
                  }
                }
              },
              "plotType": "LINE",
              "minAlignmentPeriod": "60s"
            }
          ],
          "yAxis": {
            "label": "Events / sec",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "Log Count by Forwarder ID",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"chronicle.googleapis.com/ingestion/log/record_count\"",
                  "aggregation": {
                    "perSeriesAligner": "ALIGN_RATE",
                    "crossSeriesReducer": "REDUCE_SUM",
                    "alignmentPeriod": "60s",
                    "groupByFields": [
                      "metric.label.forwarder_id"
                    ]
                  }
                },
                "unitOverride": "1/s"
              },
              "plotType": "LINE",
              "minAlignmentPeriod": "60s"
            }
          ],
          "yAxis": {
            "label": "Logs / sec",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "Log Count by GC Region",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"chronicle.googleapis.com/ingestion/log/record_count\"",
                  "aggregation": {
                    "perSeriesAligner": "ALIGN_RATE",
                    "crossSeriesReducer": "REDUCE_SUM",
                    "alignmentPeriod": "60s",
                    "groupByFields": [
                      "resource.label.location"
                    ]
                  }
                },
                "unitOverride": "1/s"
              },
              "plotType": "LINE",
              "minAlignmentPeriod": "60s"
            }
          ],
          "yAxis": {
            "label": "Logs / sec",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "Log Count by Project ID",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"chronicle.googleapis.com/ingestion/log/record_count\"",
                  "aggregation": {
                    "perSeriesAligner": "ALIGN_RATE",
                    "crossSeriesReducer": "REDUCE_SUM",
                    "alignmentPeriod": "60s",
                    "groupByFields": [
                      "resource.label.project_id"
                    ]
                  }
                },
                "unitOverride": "1/s"
              },
              "plotType": "LINE",
              "minAlignmentPeriod": "60s"
            }
          ],
          "yAxis": {
            "label": "Logs / sec",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "Log Count by Log Type",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"chronicle.googleapis.com/ingestion/log/record_count\"",
                  "aggregation": {
                    "perSeriesAligner": "ALIGN_RATE",
                    "crossSeriesReducer": "REDUCE_SUM",
                    "alignmentPeriod": "60s",
                    "groupByFields": [
                      "resource.label.log_type"
                    ]
                  }
                },
                "unitOverride": "1/s"
              },
              "plotType": "LINE",
              "minAlignmentPeriod": "60s"
            }
          ],
          "yAxis": {
            "label": "Logs / sec",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "Forwarder by Namespace, Collector ID, and Log Type",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"chronicle.googleapis.com/ingestion/log/record_count\"",
                  "aggregation": {
                    "perSeriesAligner": "ALIGN_RATE",
                    "crossSeriesReducer": "REDUCE_SUM",
                    "alignmentPeriod": "60s",
                    "groupByFields": [
                      "resource.label.namespace",
                      "metric.label.collector_id",
                      "resource.label.log_type"
                    ]
                  }
                },
                "unitOverride": "1/s"
              },
              "plotType": "STACKED_AREA",
              "minAlignmentPeriod": "60s"
            }
          ],
          "yAxis": {
            "label": "Logs / sec",
            "scale": "LINEAR"
          }
        }
      }
    ]
  }
}
EOF
}

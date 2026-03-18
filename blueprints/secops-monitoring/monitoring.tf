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
  "dashboardFilters": [],
  "description": "",
  "labels": {},
  "mosaicLayout": {
    "columns": 48,
    "tiles": [
      {
        "height": 6,
        "width": 48,
        "widget": {
          "title": "Data Ingestion Health ",
          "id": "",
          "text": {
            "content": "",
            "format": "MARKDOWN",
            "style": {
              "backgroundColor": "#FFFFFF",
              "fontSize": "FS_LARGE",
              "horizontalAlignment": "H_CENTER",
              "padding": "P_EXTRA_SMALL",
              "pointerLocation": "POINTER_LOCATION_UNSPECIFIED",
              "textColor": "#212121",
              "verticalAlignment": "V_TOP"
            }
          }
        }
      },
      {
        "yPos": 6,
        "height": 16,
        "width": 24,
        "widget": {
          "title": "Daily Total Ingested Log Count",
          "id": "",
          "xyChart": {
            "chartOptions": {
              "displayHorizontal": false,
              "mode": "COLOR",
              "showLegend": false
            },
            "dataSets": [
              {
                "breakdowns": [],
                "dimensions": [],
                "legendTemplate": "",
                "measures": [],
                "plotType": "STACKED_BAR",
                "sort": [],
                "targetAxis": "Y1",
                "timeSeriesQuery": {
                  "outputFullDuration": false,
                  "prometheusQuery": "sum by (\"log_type\")(increase({\"__name__\"=\"chronicle.googleapis.com/ingestion/log/record_count\",\"monitored_resource\"=\"chronicle.googleapis.com/Collector\"}[1d]))",
                  "unitOverride": ""
                }
              }
            ],
            "thresholds": [],
            "yAxis": {
              "label": "",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "yPos": 6,
        "xPos": 24,
        "height": 16,
        "width": 12,
        "widget": {
          "title": "Total Ingested Logs over selected period ",
          "id": "",
          "pieChart": {
            "chartType": "DONUT",
            "dataSets": [
              {
                "breakdowns": [],
                "dimensions": [],
                "measures": [],
                "sliceNameTemplate": "",
                "timeSeriesQuery": {
                  "outputFullDuration": true,
                  "prometheusQuery": "sum by (\"log_type\")(increase({\"__name__\"=\"chronicle.googleapis.com/ingestion/log/record_count\",\"monitored_resource\"=\"chronicle.googleapis.com/Collector\"}[$${__interval}]))\n#This promql query was automatically converted from a builder query, and it may not be fully equivalent to the builder query. Manually verify the promql query before using it and edit as needed.",
                  "unitOverride": ""
                }
              }
            ],
            "showLabels": false,
            "showTotal": false,
            "sliceAggregatedThreshold": 0
          }
        }
      },
      {
        "yPos": 6,
        "xPos": 36,
        "height": 16,
        "width": 12,
        "widget": {
          "title": "SecOps Forwarders",
          "id": "",
          "timeSeriesTable": {
            "columnSettings": [],
            "dataSets": [
              {
                "minAlignmentPeriod": "60s",
                "tableTemplate": "",
                "timeSeriesQuery": {
                  "outputFullDuration": true,
                  "timeSeriesFilter": {
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": [
                        "resource.label.\"collector_id\""
                      ],
                      "perSeriesAligner": "ALIGN_MEAN"
                    },
                    "filter": "metric.type=\"chronicle.googleapis.com/forwarder/last_heartbeat\" resource.type=\"chronicle.googleapis.com/Collector\""
                  },
                  "unitOverride": ""
                }
              }
            ],
            "displayColumnType": false,
            "metricVisualization": "NUMBER"
          }
        }
      },
      {
        "yPos": 22,
        "height": 16,
        "width": 24,
        "widget": {
          "title": "Events per Second by Log Type",
          "id": "",
          "xyChart": {
            "chartOptions": {
              "displayHorizontal": false,
              "mode": "COLOR",
              "showLegend": false
            },
            "dataSets": [
              {
                "breakdowns": [],
                "dimensions": [],
                "legendTemplate": "",
                "measures": [],
                "minAlignmentPeriod": "60s",
                "plotType": "LINE",
                "sort": [],
                "targetAxis": "Y1",
                "timeSeriesQuery": {
                  "outputFullDuration": false,
                  "timeSeriesFilter": {
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": [
                        "resource.label.\"log_type\""
                      ],
                      "perSeriesAligner": "ALIGN_RATE"
                    },
                    "filter": "metric.type=\"chronicle.googleapis.com/ingestion/log/record_count\""
                  },
                  "unitOverride": ""
                }
              }
            ],
            "thresholds": [],
            "yAxis": {
              "label": "Events / sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "yPos": 22,
        "xPos": 24,
        "height": 16,
        "width": 24,
        "widget": {
          "title": "Log Count by Forwarder ID",
          "id": "",
          "xyChart": {
            "chartOptions": {
              "displayHorizontal": false,
              "mode": "COLOR",
              "showLegend": false
            },
            "dataSets": [
              {
                "breakdowns": [],
                "dimensions": [],
                "legendTemplate": "",
                "measures": [],
                "minAlignmentPeriod": "60s",
                "plotType": "LINE",
                "sort": [],
                "targetAxis": "Y1",
                "timeSeriesQuery": {
                  "outputFullDuration": false,
                  "timeSeriesFilter": {
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": [
                        "metric.label.\"forwarder_id\""
                      ],
                      "perSeriesAligner": "ALIGN_RATE"
                    },
                    "filter": "metric.type=\"chronicle.googleapis.com/ingestion/log/record_count\""
                  },
                  "unitOverride": ""
                }
              }
            ],
            "thresholds": [],
            "yAxis": {
              "label": "Logs / sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "yPos": 38,
        "height": 16,
        "width": 24,
        "widget": {
          "title": "Log Count by GC Region",
          "id": "",
          "xyChart": {
            "chartOptions": {
              "displayHorizontal": false,
              "mode": "COLOR",
              "showLegend": false
            },
            "dataSets": [
              {
                "breakdowns": [],
                "dimensions": [],
                "legendTemplate": "",
                "measures": [],
                "minAlignmentPeriod": "60s",
                "plotType": "LINE",
                "sort": [],
                "targetAxis": "Y1",
                "timeSeriesQuery": {
                  "outputFullDuration": false,
                  "timeSeriesFilter": {
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": [
                        "resource.label.\"location\""
                      ],
                      "perSeriesAligner": "ALIGN_RATE"
                    },
                    "filter": "metric.type=\"chronicle.googleapis.com/ingestion/log/record_count\""
                  },
                  "unitOverride": ""
                }
              }
            ],
            "thresholds": [],
            "yAxis": {
              "label": "Logs / sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "yPos": 38,
        "xPos": 24,
        "height": 16,
        "width": 24,
        "widget": {
          "title": "Log Count by Project ID",
          "id": "",
          "xyChart": {
            "chartOptions": {
              "displayHorizontal": false,
              "mode": "COLOR",
              "showLegend": false
            },
            "dataSets": [
              {
                "breakdowns": [],
                "dimensions": [],
                "legendTemplate": "",
                "measures": [],
                "minAlignmentPeriod": "60s",
                "plotType": "LINE",
                "sort": [],
                "targetAxis": "Y1",
                "timeSeriesQuery": {
                  "outputFullDuration": false,
                  "timeSeriesFilter": {
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": [
                        "resource.label.\"project_id\""
                      ],
                      "perSeriesAligner": "ALIGN_RATE"
                    },
                    "filter": "metric.type=\"chronicle.googleapis.com/ingestion/log/record_count\""
                  },
                  "unitOverride": ""
                }
              }
            ],
            "thresholds": [],
            "yAxis": {
              "label": "Logs / sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "yPos": 54,
        "height": 16,
        "width": 24,
        "widget": {
          "title": "Log Count by Log Type",
          "id": "",
          "xyChart": {
            "chartOptions": {
              "displayHorizontal": false,
              "mode": "COLOR",
              "showLegend": false
            },
            "dataSets": [
              {
                "breakdowns": [],
                "dimensions": [],
                "legendTemplate": "",
                "measures": [],
                "minAlignmentPeriod": "60s",
                "plotType": "LINE",
                "sort": [],
                "targetAxis": "Y1",
                "timeSeriesQuery": {
                  "outputFullDuration": false,
                  "timeSeriesFilter": {
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": [
                        "resource.label.\"log_type\""
                      ],
                      "perSeriesAligner": "ALIGN_RATE"
                    },
                    "filter": "metric.type=\"chronicle.googleapis.com/ingestion/log/record_count\""
                  },
                  "unitOverride": ""
                }
              }
            ],
            "thresholds": [],
            "yAxis": {
              "label": "Logs / sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "yPos": 54,
        "xPos": 24,
        "height": 16,
        "width": 24,
        "widget": {
          "title": "Forwarder by Namespace, Collector ID, and Log Type",
          "id": "",
          "xyChart": {
            "chartOptions": {
              "displayHorizontal": false,
              "mode": "COLOR",
              "showLegend": false
            },
            "dataSets": [
              {
                "breakdowns": [],
                "dimensions": [],
                "legendTemplate": "",
                "measures": [],
                "minAlignmentPeriod": "60s",
                "plotType": "STACKED_AREA",
                "sort": [],
                "targetAxis": "Y1",
                "timeSeriesQuery": {
                  "outputFullDuration": false,
                  "timeSeriesFilter": {
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": [
                        "resource.label.\"namespace\"",
                        "metric.label.\"collector_id\"",
                        "resource.label.\"log_type\""
                      ],
                      "perSeriesAligner": "ALIGN_RATE"
                    },
                    "filter": "metric.type=\"chronicle.googleapis.com/ingestion/log/record_count\""
                  },
                  "unitOverride": ""
                }
              }
            ],
            "thresholds": [],
            "yAxis": {
              "label": "Logs / sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "yPos": 70,
        "height": 13,
        "width": 48,
        "widget": {
          "title": "SecOps Alerts",
          "id": "",
          "incidentList": {
            "groupBy": "ALERT",
            "monitoredResources": [],
            "policyNames": [],
            "userLabels": {}
          }
        }
      },
      {
        "yPos": 83,
        "height": 20,
        "width": 48,
        "widget": {
          "title": "SecOps Ingestion License consumption in GB",
          "xyChart": {
            "chartOptions": {
              "displayHorizontal": false,
              "mode": "COLOR"
            },
            "dataSets": [
              {
                "minAlignmentPeriod": "86400s",
                "plotType": "STACKED_BAR",
                "targetAxis": "Y1",
                "timeSeriesQuery": {
                  "prometheusQuery": "sum(increase(chronicle_googleapis_com:ingestion_log_bytes_count{monitored_resource=\"chronicle.googleapis.com/Collector\"}[1d])) / 1073741824"
                }
              }
            ],
            "thresholds": [],
            "yAxis": {
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "yPos": 103,
        "height": 6,
        "width": 48,
        "widget": {
          "title": "SecOps API",
          "id": "",
          "text": {
            "content": "",
            "format": "MARKDOWN",
            "style": {
              "backgroundColor": "#FFFFFF",
              "fontSize": "FS_LARGE",
              "horizontalAlignment": "H_CENTER",
              "padding": "P_EXTRA_SMALL",
              "pointerLocation": "POINTER_LOCATION_UNSPECIFIED",
              "textColor": "#212121",
              "verticalAlignment": "V_TOP"
            }
          }
        }
      },
      {
        "yPos": 109,
        "height": 16,
        "width": 24,
        "widget": {
          "title": "API Request Rate (RPS)",
          "id": "",
          "xyChart": {
            "chartOptions": {
              "displayHorizontal": false,
              "mode": "COLOR",
              "showLegend": false
            },
            "dataSets": [
              {
                "breakdowns": [],
                "dimensions": [],
                "legendTemplate": "",
                "measures": [],
                "minAlignmentPeriod": "60s",
                "plotType": "LINE",
                "sort": [],
                "targetAxis": "Y1",
                "timeSeriesQuery": {
                  "outputFullDuration": false,
                  "timeSeriesFilter": {
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": [],
                      "perSeriesAligner": "ALIGN_RATE"
                    },
                    "filter": "metric.type=\"serviceruntime.googleapis.com/api/request_count\" resource.type=\"consumed_api\" resource.label.\"service\"=\"chronicle.googleapis.com\""
                  },
                  "unitOverride": ""
                }
              }
            ],
            "thresholds": [],
            "timeshiftDuration": "0s",
            "yAxis": {
              "label": "y1Axis",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "yPos": 109,
        "xPos": 24,
        "height": 16,
        "width": 24,
        "widget": {
          "title": "API Error Rate (4xx vs 5xx)",
          "id": "",
          "xyChart": {
            "chartOptions": {
              "displayHorizontal": false,
              "mode": "COLOR",
              "showLegend": false
            },
            "dataSets": [
              {
                "breakdowns": [],
                "dimensions": [],
                "legendTemplate": "",
                "measures": [],
                "minAlignmentPeriod": "60s",
                "plotType": "STACKED_BAR",
                "sort": [],
                "targetAxis": "Y1",
                "timeSeriesQuery": {
                  "outputFullDuration": false,
                  "timeSeriesFilter": {
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": [
                        "metric.label.\"response_code_class\""
                      ],
                      "perSeriesAligner": "ALIGN_RATE"
                    },
                    "filter": "metric.type=\"serviceruntime.googleapis.com/api/request_count\" resource.type=\"consumed_api\" resource.label.\"service\"=\"chronicle.googleapis.com\" metric.label.\"response_code_class\"=one_of(\"4xx\",\"5xx\")"
                  },
                  "unitOverride": ""
                }
              }
            ],
            "thresholds": [],
            "yAxis": {
              "label": "Errors / sec",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "yPos": 125,
        "height": 16,
        "width": 24,
        "widget": {
          "title": "API Latency (Avg vs Max)",
          "id": "",
          "xyChart": {
            "chartOptions": {
              "displayHorizontal": false,
              "mode": "COLOR",
              "showLegend": false
            },
            "dataSets": [
              {
                "breakdowns": [],
                "dimensions": [],
                "legendTemplate": "Average Latency",
                "measures": [],
                "minAlignmentPeriod": "60s",
                "plotType": "LINE",
                "sort": [],
                "targetAxis": "Y1",
                "timeSeriesQuery": {
                  "outputFullDuration": false,
                  "timeSeriesFilter": {
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "crossSeriesReducer": "REDUCE_MEAN",
                      "groupByFields": [],
                      "perSeriesAligner": "ALIGN_DELTA"
                    },
                    "filter": "metric.type=\"serviceruntime.googleapis.com/api/request_latencies\" resource.type=\"consumed_api\" resource.label.\"service\"=\"chronicle.googleapis.com\""
                  },
                  "unitOverride": ""
                }
              },
              {
                "breakdowns": [],
                "dimensions": [],
                "legendTemplate": "Max Latency",
                "measures": [],
                "minAlignmentPeriod": "60s",
                "plotType": "LINE",
                "sort": [],
                "targetAxis": "Y1",
                "timeSeriesQuery": {
                  "outputFullDuration": false,
                  "timeSeriesFilter": {
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "crossSeriesReducer": "REDUCE_MAX",
                      "groupByFields": [],
                      "perSeriesAligner": "ALIGN_DELTA"
                    },
                    "filter": "metric.type=\"serviceruntime.googleapis.com/api/request_latencies\" resource.type=\"consumed_api\" resource.label.\"service\"=\"chronicle.googleapis.com\""
                  },
                  "unitOverride": ""
                }
              }
            ],
            "thresholds": [],
            "yAxis": {
              "label": "Latency (ms)",
              "scale": "LINEAR"
            }
          }
        }
      },
      {
        "yPos": 125,
        "xPos": 24,
        "height": 16,
        "width": 24,
        "widget": {
          "title": "Authentication Failures (401/403)",
          "id": "",
          "xyChart": {
            "chartOptions": {
              "displayHorizontal": false,
              "mode": "COLOR",
              "showLegend": false
            },
            "dataSets": [
              {
                "breakdowns": [],
                "dimensions": [],
                "legendTemplate": "",
                "measures": [],
                "minAlignmentPeriod": "60s",
                "plotType": "LINE",
                "sort": [],
                "targetAxis": "Y1",
                "timeSeriesQuery": {
                  "outputFullDuration": false,
                  "timeSeriesFilter": {
                    "aggregation": {
                      "alignmentPeriod": "60s",
                      "crossSeriesReducer": "REDUCE_SUM",
                      "groupByFields": [
                        "metric.label.\"response_code\""
                      ],
                      "perSeriesAligner": "ALIGN_RATE"
                    },
                    "filter": "metric.type=\"serviceruntime.googleapis.com/api/request_count\" resource.type=\"consumed_api\" resource.label.\"service\"=\"chronicle.googleapis.com\" metric.label.\"response_code\"=one_of(\"401\",\"403\")"
                  },
                  "unitOverride": ""
                }
              }
            ],
            "thresholds": [],
            "yAxis": {
              "label": "",
              "scale": "LINEAR"
            }
          }
        }
      }
    ]
  }
}
EOF
}

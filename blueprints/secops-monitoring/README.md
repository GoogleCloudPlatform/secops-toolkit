# Google SecOps Monitoring Blueprint

This blueprint sets up comprehensive Cloud Monitoring and Alerting capabilities for your Google SecOps instance. It provides out-of-the-box visibility into data ingestion health, forwarder status, and SecOps API performance.

## Resources Provisioned

The blueprint deploys the following resources in the specified Google Cloud Project:

### 1. Cloud Monitoring Dashboard
A centralized dashboard named **"SecOps API & Ingestion Health"** providing visualizations for:
*   **API Health:** Request rates, latency (Avg vs Max), error rates (4xx vs 5xx), and authentication failures (401/403).
*   **Ingestion Metrics:** Events per second by log type, log count by Forwarder ID, Google Cloud Region, Project ID, and Log Type.
*   **Forwarder Health:** Forwarder throughput breakdown by Namespace, Collector ID, and Log Type.

### 2. Alerting Policies
Essential alerting policies to proactively notify your team of potential issues:
*   **Ingestion Alerts:**
    *   SecOps Ingestion Rate close to ingestion limit (> 80%).
    *   Ingestion Quota Rejection (data being dropped).
*   **Forwarder Alerts:**
    *   Forwarder Buffer Usage High.
    *   Detect Silent Google SecOps Forwarders (no logs for 60 minutes).
    *   Silent Chronicle Forwarder and LogType (silent for 1 hour).
*   **Normalization Alerts:**
    *   Detect drop in events normalized per raw logs ingested.
*   **API Alerts:**
    *   Chronicle API - High Latency (> 2s for 5 mins).
    *   Chronicle API - High 5xx Error Rate.
    *   Chronicle API - High Auth Failures.

*(Note: Alerts are only provisioned if `alerts_enabled` is set to `true` in your `monitoring_config`)*.

---

## Variables

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| `project_id` | The ID of the project where resources will be deployed. | `string` | n/a | yes |
| `monitoring_config` | Configuration object for monitoring, alerts, and notification channels. | `object` | `{enabled=true, alerts_enabled=false, notification_channels=[]}` | no |

### `monitoring_config` Object Structure

*   `enabled` (optional `bool`): Whether to deploy the monitoring dashboard and alerts. Defaults to `true`.
*   `alerts_enabled` (optional `bool`): Whether to enable the alert policies. Defaults to `false`.
*   `notification_channels` (optional `list(object)`): A list of notification channels to route alerts to.

---

## Deployment Instructions

1.  **Navigate to the blueprint directory:**
    ```bash
    cd blueprints/secops-monitoring
    ```

2.  **Initialize Terraform:**
    ```bash
    terraform init
    ```

3.  **Create a `terraform.tfvars` file** with your desired configuration (see sample below).

4.  **Review the planned changes:**
    ```bash
    terraform plan
    ```

5.  **Apply the configuration:**
    ```bash
    terraform apply
    ```

### Sample `terraform.tfvars`

Here is an example module initialization with sample variables:

```hcl
project_id = "your-gcp-project-id"

monitoring_config = {
  enabled        = true
  alerts_enabled = true
  
  notification_channels = [
    {
      display_name = "SecOps Team Default Email"
      type         = "email"
      labels       = { "email_address" = "secops-team@example.com" }
      enabled      = true
    },
    {
      display_name = "PagerDuty Incident alerts"
      type         = "pagerduty"
      labels       = { "service_key" = "your-pagerduty-service-key" }
      enabled      = true
    }
  ]
}
```

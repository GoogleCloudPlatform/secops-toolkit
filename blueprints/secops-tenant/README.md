# SecOps Tenant

This blueprint allows automated configuration of a SecOps SIEM tenant leveraging Customer Management API documented [here](https://cloud.google.com/chronicle/docs/reference/customer-management-api).

Alternatively, this blueprint can optionally link an existing GCP project connected to Google SecOps for setting up GCP Logs ingestion on a per folder base rather than Organization-wise leveraing the direct GCP integration with SecOps.

This README.md will details both use cases providing samples `terraform.tfvars`.

<p align="center">
  <img src="images/diagram.png" alt="SecOPs Tenant">
</p>

<!-- BEGIN TOC -->
- [Design overview and choices](#design-overview-and-choices)
  - [Provider and Terraform variables](#provider-and-terraform-variables)
  - [Impersonating the automation service account](#impersonating-the-automation-service-account)
  - [Variable configuration](#variable-configuration)
  - [Running the blueprint](#running-the-blueprint)
- [Customizations](#customizations)
  - [SecOps Tenant provisioning](#secops-tenant-provisioning)
  - [SecOps GCP Log ingestion in Multi Tenant Organizations](#secops-gcp-log-ingestion-in-multi-tenant-organizations)
- [Files](#files)
- [Variables](#variables)
- [Outputs](#outputs)
<!-- END TOC -->

## Design overview and choices

The general idea behind this blueprint is to provision a SecOps tenant leveraging terraform resources (where available) and `restful_resource` for interacting with the new [SecOps APIs](https://cloud.google.com/chronicle/docs/reference/rest).

Some high level features of the current version of the secops-tenant blueprint are:
- Create GCP project that will be linked to SecOps SIEM (BYOP) 
- Billing setup (billing account attachment)
- API/Services enablement
- Creation of the SecOps SIEM instance for the tenant via API calls
- Basic IAM setup for the SecOps based on predefined roles, supporting groups from Cloud Identity or WIF
- Log Sink configuration (Org and folders) and integration with SIEM based on Cloud Function
- SCC Notification config and and integration with SIEM based on Cloud Function
- Cloud Function for asset inventory collection and export to SIEM

### Provider and Terraform variables

### Impersonating the automation service account

It is recommended to adopt a provider file that leverages impersonation to run with a dedicated stage's automation service account's credentials. The groups operating such a script should have the necessary IAM bindings in place to do that, so make sure the current user is a member of one of those groups.

### Variable configuration

Variables in this blueprint control this script's behaviour and customizations, and can to be set in a custom `terraform.tfvars` file (a sample `terraform.tfvars.sample` was provided for easier adoption of this automation).

The latter set is explained in the [Customization](#customizations) sections below, and the full list can be found in the [Variables](#variables) table at the bottom of this document.

### Running the blueprint

Once provider and variable values are in place and the correct user is configured, the stage can be run:

```bash
terraform init
terraform apply
```

## Customizations

This blueprint is designed with few basic integrations provided out of the box which can be customized as per the following sections.

### SecOps Tenant provisioning

This blueprint supports deployment of SecOps SIEM in a Managed Security Service Provider (MSSP) like deployment. It leverages [Customer Management APIs](https://cloud.google.com/chronicle/docs/reference/customer-management-api) and `restful_resource` for creating a new SecOps tenant associated to the Google Cloud Project provided.

Be aware that this stage assumes credentials used to run the automation to have permissions to impersonate the backstory service account with privileges to operate the Customer Management API, if that is not the case please refer to your Google SecOps representative for further information on how to achieve this configuration or leverage service account credentials to authenticate in Terraform.

Below a sample `terraform.tfvars` for provisioning a new tenant:
- `project_id`: Project id that references existing GCP project
- `project_create_config`: Create project instead of using an existing one
- `secops_tenant_config`: SecOps Tenant configuration


```hcl
project_id = "xxx-dev-secops-0"

project_create_config = {
  billing_account = "XXXXX-XXXXX-XXXXXXX"
  parent          = "folders/12321321"
}

secops_tenant_config = {
  region             = "europe"
  tenant_id          = "tenant"
  tenant_code        = "tenant"
  tenant_subdomains  = ["tenant"]
  alpha_apis_region  = "eu"
}
# tftest skip
```

### SecOps GCP Log ingestion in Multi Tenant Organizations 

This stage supports deployment of integrations needed for ingestion of Google Cloud logs, assets and Security Command Center findings on a per folder base.
Native Google Cloud Log ingestion works on a per organization base and it is not a good fit for multi-tenant GCP organization where SecOps should collect logs from a dedicated node of the GCP resource hierarchy.

Below a sample `terraform.tfvars` for integrating multi tenant log, assets and SCC findings ingestion for an existing SecOps instance:

- `project_id`: Project id that references existing GCP project
- `secops_tenant_config`: SecOps Tenant configuration


```hcl
project_id = "xxx-dev-secops-0"

secops_tenant_config = {
  customer_id        = "xxxxxxxxxxxxxxxx"
  region             = "europe"
  alpha_apis_region  = "eu"
}
# tftest skip
```

<!-- TFDOC OPTS files:1 show_extra:1 exclude:3-secops-dev-providers.tf -->
<!-- BEGIN TFDOC -->
## Files

| name | description | modules | resources |
|---|---|---|---|
| [cai.tf](./cai.tf) | None | <code>cloud-function-v2</code> · <code>iam-service-account</code> · <code>pubsub</code> | <code>google_cloud_scheduler_job</code> · <code>restful_operation</code> · <code>restful_resource</code> |
| [log-sink.tf](./log-sink.tf) | None | <code>iam-service-account</code> · <code>pubsub</code> | <code>restful_operation</code> · <code>restful_resource</code> |
| [main.tf](./main.tf) | Module-level locals and resources. | <code>iam-service-account</code> · <code>net-vpc</code> · <code>organization</code> · <code>project</code> | <code>google_apikeys_key</code> · <code>google_cloudbuild_worker_pool</code> · <code>google_vpc_access_connector</code> · <code>restful_resource</code> |
| [outputs.tf](./outputs.tf) | Module outputs. |  |  |
| [scc.tf](./scc.tf) | None | <code>cloud-function-v2</code> · <code>iam-service-account</code> | <code>google_cloud_scheduler_job</code> · <code>google_scc_notification_config</code> |
| [secops-providers.tf](./secops-providers.tf) | None |  |  |
| [secrets.tf](./secrets.tf) | None | <code>secret-manager</code> |  |
| [variables.tf](./variables.tf) | Module variables. |  |  |
| [versions.tf](./versions.tf) | Version pins. |  |  |

## Variables

| name | description | type | required | default | producer |
|---|---|:---:|:---:|:---:|:---:|
| [project_id](variables.tf#L110) | Project id that references existing project. | <code>string</code> | ✓ |  |  |
| [secops_tenant_config](variables.tf#L186) | SecOps Tenant configuration. | <code title="object&#40;&#123;&#10;  backstory_sa_email &#61; optional&#40;string&#41;&#10;  customer_id        &#61; optional&#40;string&#41;&#10;  tenant_id          &#61; optional&#40;string&#41;&#10;  tenant_code        &#61; optional&#40;string&#41;&#10;  tenant_subdomains  &#61; optional&#40;list&#40;string&#41;, &#91;&#93;&#41;&#10;  region             &#61; string&#10;  alpha_apis_region  &#61; string&#10;  retention_duration &#61; optional&#40;string, &#34;ONE_YEAR&#34;&#41;&#10;  sso_config         &#61; optional&#40;string, null&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> | ✓ |  |  |
| [_tests](variables.tf#L17) | Dummy variable populated by tests pipeline. | <code>bool</code> |  | <code>false</code> |  |
| [gcp_logs_ingestion_config](variables.tf#L23) | Configuration for GCP logs to collect via Log Sink. | <code title="object&#40;&#123;&#10;  AUDITD &#61; optional&#40;object&#40;&#123;&#10;    enabled              &#61; optional&#40;bool, true&#41;&#10;    override_log_filters &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;  BRO_JSON &#61; optional&#40;object&#40;&#123;&#10;    enabled              &#61; optional&#40;bool, true&#41;&#10;    override_log_filters &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;  GCP_APIGEE_X &#61; optional&#40;object&#40;&#123;&#10;    enabled              &#61; optional&#40;bool, false&#41;&#10;    override_log_filters &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;  GCP_CLOUDAUDIT &#61; optional&#40;object&#40;&#123;&#10;    enabled              &#61; optional&#40;bool, true&#41;&#10;    override_log_filters &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;  GCP_CLOUD_NAT &#61; optional&#40;object&#40;&#123;&#10;    enabled              &#61; optional&#40;bool, true&#41;&#10;    override_log_filters &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;  GCP_CLOUDSQL &#61; optional&#40;object&#40;&#123;&#10;    enabled              &#61; optional&#40;bool, true&#41;&#10;    override_log_filters &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;  GCP_DNS &#61; optional&#40;object&#40;&#123;&#10;    enabled              &#61; optional&#40;bool, true&#41;&#10;    override_log_filters &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;  GCP_FIREWALL &#61; optional&#40;object&#40;&#123;&#10;    enabled              &#61; optional&#40;bool, true&#41;&#10;    override_log_filters &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;  GCP_IDS &#61; optional&#40;object&#40;&#123;&#10;    enabled              &#61; optional&#40;bool, true&#41;&#10;    override_log_filters &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;  GCP_LOADBALANCING &#61; optional&#40;object&#40;&#123;&#10;    enabled              &#61; optional&#40;bool, true&#41;&#10;    override_log_filters &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;  KUBERNETES_NODE &#61; optional&#40;object&#40;&#123;&#10;    enabled              &#61; optional&#40;bool, false&#41;&#10;    override_log_filters &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;  LINUX_SYSMON &#61; optional&#40;object&#40;&#123;&#10;    enabled              &#61; optional&#40;bool, true&#41;&#10;    override_log_filters &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;  NIX_SYSTEM &#61; optional&#40;object&#40;&#123;&#10;    enabled              &#61; optional&#40;bool, true&#41;&#10;    override_log_filters &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;  WINEVTLOG &#61; optional&#40;object&#40;&#123;&#10;    enabled              &#61; optional&#40;bool, true&#41;&#10;    override_log_filters &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code>&#123;&#125;</code> |  |
| [network_config](variables.tf#L86) | VPC config. | <code title="object&#40;&#123;&#10;  functions_connector_ip_range &#61; optional&#40;string, &#34;10.0.0.0&#47;28&#34;&#41;&#10;  cloud_build_ip_range         &#61; optional&#40;string, &#34;10.0.1.0&#47;24&#34;&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code>&#123;&#125;</code> |  |
| [organization_id](variables.tf#L95) | GCP Organization ID. This is required only if tenant_nodes is configured for ingesting logs at org level. | <code>string</code> |  | <code>null</code> |  |
| [project_create_config](variables.tf#L101) | Create project instead of using an existing one. | <code title="object&#40;&#123;&#10;  billing_account &#61; string&#10;  parent          &#61; optional&#40;string&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code>null</code> |  |
| [regions](variables.tf#L115) | Region definitions. | <code title="object&#40;&#123;&#10;  primary   &#61; string&#10;  secondary &#61; string&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code title="&#123;&#10;  primary   &#61; &#34;europe-west8&#34;&#10;  secondary &#61; &#34;europe-west1&#34;&#10;&#125;">&#123;&#8230;&#125;</code> |  |
| [secops_group_principals](variables.tf#L127) | Groups ID in IdP assigned to SecOps admins, editors, viewers roles. | <code title="object&#40;&#123;&#10;  admins  &#61; optional&#40;list&#40;string&#41;, &#91;&#93;&#41;&#10;  editors &#61; optional&#40;list&#40;string&#41;, &#91;&#93;&#41;&#10;  viewers &#61; optional&#40;list&#40;string&#41;, &#91;&#93;&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code>&#123;&#125;</code> |  |
| [secops_ingestion_config](variables.tf#L137) | SecOps Data ingestion configuration for Google Cloud Platform. | <code title="object&#40;&#123;&#10;  ingest_scc_findings   &#61; optional&#40;bool, false&#41;&#10;  ingest_assets_data    &#61; optional&#40;bool, false&#41;&#10;  ingest_workspace_data &#61; optional&#40;bool, false&#41;&#10;  ingest_feed_type      &#61; optional&#40;string, &#34;HTTPS_PUSH_GOOGLE_CLOUD_PUBSUB&#34;&#41;&#10;  assets_data_config &#61; optional&#40;object&#40;&#123;&#10;    GCP_BIGQUERY_CONTEXT &#61; optional&#40;object&#40;&#123;&#10;      enabled              &#61; optional&#40;bool, true&#41;&#10;      override_asset_types &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;    &#125;&#41;, &#123;&#125;&#41;&#10;    GCP_CLOUD_FUNCTIONS_CONTEXT &#61; optional&#40;object&#40;&#123;&#10;      enabled              &#61; optional&#40;bool, true&#41;&#10;      override_asset_types &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;    &#125;&#41;, &#123;&#125;&#41;&#10;    GCP_COMPUTE_CONTEXT &#61; optional&#40;object&#40;&#123;&#10;      enabled              &#61; optional&#40;bool, true&#41;&#10;      override_asset_types &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;    &#125;&#41;, &#123;&#125;&#41;&#10;    GCP_IAM_CONTEXT &#61; optional&#40;object&#40;&#123;&#10;      enabled              &#61; optional&#40;bool, true&#41;&#10;      override_asset_types &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;    &#125;&#41;, &#123;&#125;&#41;&#10;    GCP_KUBERNETES_CONTEXT &#61; optional&#40;object&#40;&#123;&#10;      enabled              &#61; optional&#40;bool, true&#41;&#10;      override_asset_types &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;    &#125;&#41;, &#123;&#125;&#41;&#10;    GCP_NETWORK_CONNECTIVITY_CONTEXT &#61; optional&#40;object&#40;&#123;&#10;      enabled              &#61; optional&#40;bool, true&#41;&#10;      override_asset_types &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;    &#125;&#41;, &#123;&#125;&#41;&#10;    GCP_RESOURCE_MANAGER_CONTEXT &#61; optional&#40;object&#40;&#123;&#10;      enabled              &#61; optional&#40;bool, true&#41;&#10;      override_asset_types &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;    &#125;&#41;, &#123;&#125;&#41;&#10;    GCP_SQL_CONTEXT &#61; optional&#40;object&#40;&#123;&#10;      enabled              &#61; optional&#40;bool, true&#41;&#10;      override_asset_types &#61; optional&#40;list&#40;string&#41;, null&#41;&#10;    &#125;&#41;, &#123;&#125;&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code>&#123;&#125;</code> |  |
| [tenant_nodes](variables.tf#L208) | GCP node IDs and configuration for SecOps tenant log sync. | <code title="object&#40;&#123;&#10;  include_org &#61; optional&#40;bool, false&#41;&#10;  folders &#61; optional&#40;map&#40;object&#40;&#123;&#10;    folder_id        &#61; string&#10;    include_children &#61; optional&#40;bool, true&#41;&#10;  &#125;&#41;&#41;, &#123;&#125;&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code>&#123;&#125;</code> |  |

## Outputs

| name | description | sensitive | consumers |
|---|---|:---:|---|
| [project_id](outputs.tf#L15) | SecOps project id. |  |  |
<!-- END TFDOC -->

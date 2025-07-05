# SecOps Tenant Factory WIP

This blueprints implements end-to-end configuration of new projects and SecOps SIEM tenants via YAML data configurations and [secops-tenant](../secops-tenant) blueprint code.

It supports:
- project creation and management exposing the full configuration options available in the `secops-tenant' blueprint
- secops SIEM tenant provisioning leveraging Customer Management APIs with full customization of provisioning configurations
- optional per-project basic IAM grants
- optional Google Cloud Ingestion of logs, assets and Security Command Center findings at folder level (for multi-tenant organization) 

The code is meant to be executed by a high level service accounts with powerful permissions:
- folder/organization viewer permissions for the hierarchy
- project creation on the nodes (folder or org) where projects will be defined
- billing permissions to attach BA to newly created projects
- SA should be assigned permissions to impersonate Backstory Service Account for Customer Management API

<!-- BEGIN TOC -->
* [SecOps Tenant Factory WIP](#secops-tenant-factory-wip)
    * [Running the blueprint](#running-the-blueprint)
  * [Customizations](#customizations)
  * [Files](#files)
  * [Variables](#variables)
<!--END TOC -->

### Running the blueprint

> Before running this blueprint it is mandatory to remove the file [secops-providers.tf](../secops-tenant/secops-providers.tf) file from the [secops-tenant](../secops-tenant) folder and uncomment the `configurations` section in the [versions.tf](../secops-tenant/versions.tf).  

Once provider and variable values are in place and the correct user is configured, the blueprint can be run:

```bash
terraform init
terraform apply
```

## Customizations

Please find below sample `terraform.tfvars` variables for running this automation.

```terraform
billing_account = "XXXXXXXXXX"

secops_config = {
  backstory_sa_email = "gitlab@bruzz-prod-secops-0.iam.gserviceaccount.com"
  region            = "europe"
  alpha_apis_region = "eu"
}

tenant_folder = "folders/123456789"
```

As per the sample file available in the `data` folder please find below a sample YAML file for tenant definition to use with the factory pattern.

```yaml
secops_ingestion_config:
  ingest_scc_findings: false
  ingest_assets_data: false
  ingest_workspace_data: false
secops_tenant_config:
  tenant_id: "tenant-1"
  tenant_code: "tenant-1"
  tenant_subdomains:
    - "tenant-1-europe"
  master_tenant: false
project_id: "prod-cs-tenant-1"
organization_id: "XXXXXXXXXXX"
tenant_nodes:
  include_org: false
  folders:
#    tenant:
#      folder_id: "folders/765907462668"
#      include_children: true
secops_group_principals:
  admins:
    - "gcp-security-admins@example.com"
  editors:
  viewers:
```

<!-- TFDOC OPTS files:1 show_extra:1 exclude:3-secops-dev-providers.tf -->
<!-- BEGIN TFDOC -->
## Files

| name | description | modules |
|---|---|---|
| [main.tf](./main.tf) | Module-level locals and resources. | <code>secops-tenant</code> |
| [outputs.tf](./outputs.tf) | Module outputs. |  |
| [secops-providers.tf](./secops-providers.tf) | None |  |
| [variables.tf](./variables.tf) | Module variables. |  |
| [versions.tf](./versions.tf) | Version pins. |  |

## Variables

| name | description | type | required | default | producer |
|---|---|:---:|:---:|:---:|:---:|
| [billing_account](variables.tf#L23) | Billing account id for SecOps projects. | <code>string</code> | ✓ |  |  |
| [secops_config](variables.tf#L58) | SecOps configuration including customer management API key SA email. | <code title="object&#40;&#123;&#10;  backstory_sa_email &#61; string&#10;  region             &#61; string&#10;  alpha_apis_region  &#61; string&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> | ✓ |  |  |
| [tenant_folder](variables.tf#L68) | GCP folder hosting SecOps tenant projects. | <code>string</code> | ✓ |  |  |
| [_tests](variables.tf#L17) | Dummy variable populated by tests pipeline. | <code>bool</code> |  | <code>false</code> |  |
| [factories_config](variables.tf#L29) | Configuration for network resource factories. | <code title="object&#40;&#123;&#10;  data_folder           &#61; optional&#40;string, &#34;data&#34;&#41;&#10;  dns_policy_rules_file &#61; optional&#40;string, &#34;data&#47;dns-policy-rules.yaml&#34;&#41;&#10;  firewall_policy_name  &#61; optional&#40;string, &#34;net-default&#34;&#41;&#10;  tenants_folder        &#61; optional&#40;string, &#34;data&#47;tenants&#34;&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code title="&#123;&#10;  data_folder           &#61; &#34;data&#34;&#10;  dns_policy_rules_file &#61; &#34;data&#47;dns-policy-rules.yaml&#34;&#10;&#125;">&#123;&#8230;&#125;</code> |  |
| [organization_id](variables.tf#L52) | GCP Organization ID. This is required only if tenant_nodes is configured for ingesting logs at org level. | <code>string</code> |  | <code>null</code> |  |
<!-- END TFDOC -->

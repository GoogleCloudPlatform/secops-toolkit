# SecOps Toolkit Foundation - Stage 0 - Project Bootstrap Setup

This stage is responsible for bootstrapping the Google SecOps GCP project within an existing GCP Organization. 

It supports multiple deployment scenarios:
- **Organization-level** or **Folder-level** project creation.
- **Folder-level** project creation with a dedicated folder for SecOps resources.
- **Reusing an existing project** without creating a new one.

This stage enables the necessary Chronicle APIs and supports configuring VPC Service Controls (VPC-SC) for SecOps. It leverages the [Cloud Foundation Fabric modules](https://github.com/GoogleCloudPlatform/cloud-foundation-fabric) to ensure best practices.

![Google SecOps Hierarchy Diagram](hierarchy_diagram.png)

## Prerequisites

Before applying this configuration, you must configure the `billing_project` variable. This variable specifies the project used as the billing and quota project for the Terraform providers. It is required for properly applying VPC Service Controls configurations and managing API quotas.

## Required roles (Least Privileges)

To apply this configuration with the principle of least privileges, you need the following roles:

- `roles/resourcemanager.projectCreator` on the Organization or Folder where you will create the project (only if the project needs to be created and does not exist yet).
- `roles/billing.user` on the Billing Account you wish to link.
- `roles/serviceusage.serviceUsageAdmin` on the project (to enable Chronicle and other APIs).
- `roles/accesscontextmanager.policyAdmin` at the Organization level (if VPC Service Controls configurations are enabled).

## Example `terraform.tfvars`

You can use the provided `terraform.tfvars.sample` as a starting point. Below is an example based on the sample available in this folder:

```hcl
billing_project = "tmp-xxxx"
project_id      = "xxxx-dev-secops-0"
organization_id = "xxxxxxxxx"
essential_contacts = ["test@example.com"]

vpc_sc_config = {
  enabled = true
}
```

## Deploy the stage

```shell
cp terraform.tfvars.sample terraform.tfvars

# Edit terraform.tfvars to match your environment.

terraform init
terraform apply
```

If the apply concludes successfully you should see the newly created GCP project in your Google Cloud Console as well as the VPC Service Control perimeter in case this was enabled.

## Use existing projects

The `project_create_config` variable allows you to configure whether to create a new project or reuse an existing one, providing flexibility depending on your environment. Additionally, if you are creating a new project, you can set the `bootstrap_folder = true` parameter inside `project_create_config` to automatically create a "SecOps" folder directly underneath your Organization, and place the new project inside it. Note that `parent` and `bootstrap_folder` are mutually exclusive.

## Customer-Managed Encryption Keys (CMEK)

This project supports optionally provisioning a [Customer-Managed Encryption Key (CMEK) for Google SecOps](https://docs.cloud.google.com/chronicle/docs/secops/cmek_for_secops) using the Cloud Foundation Fabric [`kms` module](https://github.com/GoogleCloudPlatform/cloud-foundation-fabric/tree/master/modules/kms). 

To enable and configure CMEK, use the `cmek_config` variable. When enabled, a KMS keyring and key will be created in the specified location. During SecOps provisioing it is required for the Google SecOps service agent to be granted the `roles/cloudkms.cryptoKeyEncrypterDecrypter` role, this is done in the GUI during the onboarding process.

Example configuration in `terraform.tfvars`:
```hcl
cmek_config = {
  enabled         = true
  location        = "europe-west1"
  keyring_name    = "secops-keyring"
  key_name        = "secops-key"
  rotation_period = "7776000s" # 90 days
}
```

## Customizing VPC Service Controls (VPC-SC)

This project leverages the Cloud Foundation Fabric [`vpc-sc` module](https://github.com/GoogleCloudPlatform/cloud-foundation-fabric/tree/master/modules/vpc-sc) to manage VPC Service Controls. 

Default rules and configurations are available in the `vpcsc/` folder. You can easily extend the access levels configuration by creating or modifying YAML files in the `vpcsc/access-levels/` directory.

### Extending Access Levels

You can restrict access to SecOps APIs based on geographic location, specific user identities, or a list of IP addresses. Here is how you can configure them:

- **By IP Address (`ips.yaml`)**: Define a list of allowed subnets.
  ```yaml
  conditions:
    - ip_subnetworks:
        - 93.45.67.54/32
  ```

- **By Geography (`geo.yaml`)**: Restrict access to specific countries using region codes (e.g., `IT` for Italy).
  ```yaml
  conditions:
    - regions:
        - IT
  ```

- **By User/Identity (`users.yaml`)**: Allow specific members or service accounts.
  ```yaml
  conditions:
    - members:
        - user:admin@example.com
        - serviceAccount:my-sa@my-project.iam.gserviceaccount.com
  ```

These files act as definitions for the VPC-SC factory to automatically generate the appropriate Access Context Manager rules.
<!-- BEGIN TFDOC -->
## Variables

| name | description | type | required | default |
|---|---|:---:|:---:|:---:|
| [billing_project](variables.tf#L23) | Billing project id. This project is used as the billing and quota project for the Terraform providers. | <code>string</code> | ✓ |  |
| [organization_id](variables.tf#L64) | GCP Organization ID used for VPC SC perimeters. | <code>string</code> | ✓ |  |
| [project_id](variables.tf#L86) | Project id that references existing project. | <code>string</code> | ✓ |  |
| [access_policy](variables.tf#L17) | Access policy id (used for tenant-level VPC-SC configurations). | <code>number</code> |  | <code>null</code> |
| [cmek_config](variables.tf#L28) | CMEK Configuration for Google SecOps. | <code title="object&#40;&#123;&#10;  enabled         &#61; optional&#40;bool, false&#41;&#10;  location        &#61; optional&#40;string, &#34;europe&#34;&#41;&#10;  keyring_name    &#61; optional&#40;string, &#34;secops-keyring&#34;&#41;&#10;  key_name        &#61; optional&#40;string, &#34;secops-key&#34;&#41;&#10;  rotation_period &#61; optional&#40;string&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code>&#123;&#125;</code> |
| [essential_contacts](variables.tf#L41) | List of essential contacts for Google Cloud project for product and platform notifications. | <code>list&#40;string&#41;</code> |  | <code>&#91;&#93;</code> |
| [factories_config](variables.tf#L47) | Paths to folders that enable factory functionality. | <code title="object&#40;&#123;&#10;  dataset &#61; optional&#40;string, &#34;vpcsc&#34;&#41;&#10;  paths &#61; optional&#40;object&#40;&#123;&#10;    access_levels       &#61; optional&#40;string, &#34;access-levels&#34;&#41;&#10;    defaults            &#61; optional&#40;string, &#34;defaults.yaml&#34;&#41;&#10;    egress_policies     &#61; optional&#40;string, &#34;egress-policies&#34;&#41;&#10;    ingress_policies    &#61; optional&#40;string, &#34;ingress-policies&#34;&#41;&#10;    perimeters          &#61; optional&#40;string, &#34;perimeters&#34;&#41;&#10;    restricted_services &#61; optional&#40;string, &#34;restricted-services.yaml&#34;&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code>&#123;&#125;</code> |
| [project_create_config](variables.tf#L69) | Create project instead of using an existing one. | <code title="object&#40;&#123;&#10;  billing_account  &#61; string&#10;  parent           &#61; optional&#40;string&#41;&#10;  bootstrap_folder &#61; optional&#40;bool, false&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code>null</code> |
| [vpc_sc_config](variables.tf#L91) | VPC SC Configuration. | <code title="object&#40;&#123;&#10;  enabled      &#61; optional&#40;bool, false&#41;&#10;  scc_enabled  &#61; optional&#40;bool, false&#41;&#10;  cmek_enabled &#61; optional&#40;bool, false&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code>&#123;&#125;</code> |

## Outputs

| name | description | sensitive |
|---|---|:---:|
| [vpc_sc_perimeter_default](outputs.tf#L26) | Raw default perimeter resource. | ✓ |
<!-- END TFDOC -->

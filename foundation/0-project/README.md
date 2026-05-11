# Cloud Run - Single / Project Setup

This stage is part of the `Cloud Run - Single` factory.
It is responsible for setting up the Google Cloud project, activating the APIs and granting the roles you need to deploy and manage the resources that enable the AI use case.

It leverages the Cloud Foundation Fabric [`project-factory`](https://github.com/GoogleCloudPlatform/cloud-foundation-fabric/tree/master/modules/project-factory).

You can refer to the [YAML project configuration](data/projects/project.yaml) for more details about enabled APIs and roles assigned in the project.

## Required roles

To execute this stage, you need these roles:

- `roles/resourcemanager.projectCreator` on the organization or folder where you will create the project.
- `roles/billing.user` on the billing account you wish to use.

Alternatively, you can use the more permissive `roles/owner` on the organization or folder.

## Deploy the stage

```shell
cp terraform.tfvars.sample terraform.tfvars

# Replace prefix, billing account and parent.

terraform init
terraform apply
```

You should now see the `providers.tf` and `terraform.auto.tfvars` files in the [1-apps folder](../1-apps/README.md). Enter the [1-apps folder](../1-apps/README.md) to proceed with the deployment.

## Use existing projects

The `project_config` variable allows to configure for different scenarios regarding project creation and management, as described in the [main README](../../README.md).
<!-- BEGIN TFDOC -->
## Variables

| name | description | type | required | default |
|---|---|:---:|:---:|:---:|
| [organization_id](variables.tf#L31) | GCP Organization ID used for VPC SC perimeters. | <code>string</code> | ✓ |  |
| [project_id](variables.tf#L26) | Project id that references existing project. | <code>string</code> | ✓ |  |
| [access_policy](variables.tf#L36) | Access policy id (used for tenant-level VPC-SC configurations). | <code>number</code> |  | <code>null</code> |
| [factories_config](variables.tf#L42) | Paths to folders that enable factory functionality. | <code title="object&#40;&#123;&#10;  dataset &#61; optional&#40;string, &#34;vpcsc&#34;&#41;&#10;  paths &#61; optional&#40;object&#40;&#123;&#10;    access_levels       &#61; optional&#40;string, &#34;access-levels&#34;&#41;&#10;    defaults            &#61; optional&#40;string, &#34;defaults.yaml&#34;&#41;&#10;    egress_policies     &#61; optional&#40;string, &#34;egress-policies&#34;&#41;&#10;    ingress_policies    &#61; optional&#40;string, &#34;ingress-policies&#34;&#41;&#10;    perimeters          &#61; optional&#40;string, &#34;perimeters&#34;&#41;&#10;    restricted_services &#61; optional&#40;string, &#34;restricted-services.yaml&#34;&#41;&#10;  &#125;&#41;, &#123;&#125;&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code>&#123;&#125;</code> |
| [project_create_config](variables.tf#L17) | Create project instead of using an existing one. | <code title="object&#40;&#123;&#10;  billing_account &#61; string&#10;  parent          &#61; optional&#40;string&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code>null</code> |
| [vpc_sc_config](variables.tf#L59) | VPC SC Configuration. | <code title="object&#40;&#123;&#10;  enabled      &#61; optional&#40;bool, false&#41;&#10;  scc_enabled  &#61; optional&#40;bool, false&#41;&#10;  cmek_enabled &#61; optional&#40;bool, false&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code>&#123;&#125;</code> |

## Outputs

| name | description | sensitive |
|---|---|:---:|
| [vpc_sc_perimeter_default](outputs.tf#L26) | Raw default perimeter resource. | ✓ |
<!-- END TFDOC -->

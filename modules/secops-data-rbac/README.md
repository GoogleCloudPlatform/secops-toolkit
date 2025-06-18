# SecOps Data RBAC

This module allows configuration of [Data RBAC](https://cloud.google.com/chronicle/docs/detection/view-all-rules) in Google SecOps.

- Data RBAC labels and scopes defintion and combinations supported via corresponding variables.

<!-- BEGIN TOC -->
- [Examples](#examples)
  - [Sample SecOps Data RBAC configuration](#sample-secops-data-rbac-configuration)
- [Variables](#variables)
<!-- END TOC -->

## Examples

### Sample SecOps Data RBAC configuration

This is a sample usage of the secops-data-rbac module for configuring a Data RBAC scope with label.

```hcl
module "secops-data-rbac" {
  source        = "./fabric/modules/secops-data-rbac"
  secops_config = var.secops_config
  labels = {
    google = {
      description = "Google logs"
      label_id    = "google"
      udm_query   = "principal.hostname=\"google.com\""
    }
  }
  scopes = {
    google = {
      description = "Google logs"
      scope_id    = "gscope"
      allowed_data_access_labels = [{
        data_access_label = "google"
      }]
    }
  }
}
# tftest modules=1 resources=2 inventory=basic.yaml
```
<!-- BEGIN TFDOC -->
## Variables

| name | description | type | required | default |
|---|---|:---:|:---:|:---:|
| [secops_config](variables.tf#L54) | SecOps configuration. | <code title="object&#40;&#123;&#10;  customer_id &#61; string&#10;  project     &#61; string&#10;  region      &#61; string&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> | ✓ |  |
| [labels](variables.tf#L17) | SecOps Data RBAC labels. | <code title="map&#40;object&#40;&#123;&#10;  description &#61; string&#10;  label_id    &#61; string&#10;  udm_query   &#61; string&#10;&#125;&#41;&#41;">map&#40;object&#40;&#123;&#8230;&#125;&#41;&#41;</code> |  | <code>&#123;&#125;</code> |
| [scopes](variables.tf#L27) | SecOps Data RBAC scopes. | <code title="map&#40;object&#40;&#123;&#10;  description &#61; string&#10;  scope_id    &#61; string&#10;  allowed_data_access_labels &#61; optional&#40;list&#40;object&#40;&#123;&#10;    data_access_label &#61; optional&#40;string&#41;&#10;    log_type          &#61; optional&#40;string&#41;&#10;    asset_namespace   &#61; optional&#40;string&#41;&#10;    ingestion_label &#61; optional&#40;object&#40;&#123;&#10;      ingestion_label_key   &#61; string&#10;      ingestion_label_value &#61; optional&#40;string&#41;&#10;    &#125;&#41;&#41;&#10;  &#125;&#41;&#41;, &#91;&#93;&#41;&#10;  denied_data_access_labels &#61; optional&#40;list&#40;object&#40;&#123;&#10;    data_access_label &#61; optional&#40;string&#41;&#10;    log_type          &#61; optional&#40;string&#41;&#10;    asset_namespace   &#61; optional&#40;string&#41;&#10;    ingestion_label &#61; optional&#40;object&#40;&#123;&#10;      ingestion_label_key   &#61; string&#10;      ingestion_label_value &#61; optional&#40;string&#41;&#10;    &#125;&#41;&#41;&#10;  &#125;&#41;&#41;, &#91;&#93;&#41;&#10;&#125;&#41;&#41;">map&#40;object&#40;&#123;&#8230;&#125;&#41;&#41;</code> |  | <code>&#123;&#125;</code> |
<!-- END TFDOC -->

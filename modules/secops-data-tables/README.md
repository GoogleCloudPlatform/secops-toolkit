# SecOps Data Tables Module

This module manages Google SecOps (Chronicle) Data Tables and their content.

- data table definitions and content are managed as files in data folder as per the `factories_config` variable and sample code
- data table deployments can leverage both `data_tables_config` and YAML file still specified in the `factories_config` variable.

<p align="center">
  <img src="images/diagram.png" alt="SecOPs Data Tables module">
</p>

<!-- BEGIN TOC -->
- [Examples](#examples)
  - [Sample SecOps Data Table deployment](#sample-secops-data-table-deployment)
  - [SecOps Data Table Factory](#secops-data-table-factory)
- [Variables](#variables)
<!-- END TOC -->

## Examples

### Sample SecOps Data Tables deployment

This is a sample usage of the `secops-data-tables` module for deploying a data table named `sample_data_table_domains`. The definition of the data table is available in the corresponding file in the `data` folder. Deployment configuration for the data table is passed as an input to the module using the `data_tables_config` variable.

```hcl
module "secops" {
  source        = "./secops-toolkit/modules/secops-data-tables"
  secops_config = var.secops_config
  data_tables_config = {
    "sample_data_table_domains" = {
      description = "Sample data table"
      columns = [
        {
          column_type : "STRING"
          key_column : null
          mapped_column_path : null
          original_column : "rank"
        },
        {
          column_type : "STRING"
          key_column : null
          mapped_column_path : null
          original_column : "domain"
        }
      ]
    }
  }
  factories_config = {
    data_tables_defs = "./data_tables"
  }
}
# tftest modules=1 resources=4 files=data_table_content inventory=basic.yaml
```

```
rank,domain
1,google.com
2,www.google.com
# tftest-file id=data_table_content path=data_tables/sample_data_table_domains.csv ,_
```

### SecOps Data Tables Factory

The module includes a secops data tables factory (see [Resource Factories](https://github.com/GoogleCloudPlatform/cloud-foundation-fabric/tree/master/blueprints/factories)) for the configuration of data tables leveraging YAML configuration files. Each configuration file for data tables contains more than one data table with a structure that reflects the `data_tables_config` variable. Again data table definition is available in the corresponding yaral and txt files in the data folder.

```hcl
module "secops" {
  source        = "./secops-toolkit/modules/secops-data-tables"
  secops_config = var.secops_config
  factories_config = {
    data_tables_defs = "data_tables"
    data_tables      = "secops_data_tables.yaml"
  }
}
# tftest modules=1 resources=4 files=factory_data_table_content,factory_data_table_definition inventory=factory.yaml
```

```
rank,domain
1,google.com
2,www.google.com
# tftest-file id=factory_data_table_content path=data_tables/sample_data_table_domains.csv ,_
```

```yaml
sample_data_table_domains:
  columns:
    - column_type: "STRING"
      key_column: null
      mapped_column_path: null
      original_column: "rank"
    - column_type: "STRING"
      key_column: null
      mapped_column_path: null
      original_column: "domain"
  description: "Sample Data Table for domains"
# tftest-file id=factory_data_table_definition path=secops_data_tables.yaml
```

<!-- BEGIN TFDOC -->
## Variables

| name | description | type | required | default |
|---|---|:---:|:---:|:---:|
| [secops_config](variables.tf#L61) | SecOps configuration. | <code title="object&#40;&#123;&#10;  customer_id &#61; string&#10;  project     &#61; string&#10;  region      &#61; string&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> | ✓ |  |
| [factories_config](variables.tf#L17) | Paths to  YAML config expected in 'rules' and 'reference_lists'. Path to folders containing rules definitions (yaral files) and reference lists content (txt files) for the corresponding _defs keys. | <code title="object&#40;&#123;&#10;  rules                &#61; optional&#40;string&#41;&#10;  rules_defs           &#61; optional&#40;string, &#34;data&#47;rules&#34;&#41;&#10;  reference_lists      &#61; optional&#40;string&#41;&#10;  reference_lists_defs &#61; optional&#40;string, &#34;data&#47;reference_lists&#34;&#41;&#10;&#125;&#41;">object&#40;&#123;&#8230;&#125;&#41;</code> |  | <code>&#123;&#125;</code> |
| [reference_lists_config](variables.tf#L29) | SecOps Reference lists configuration. | <code title="map&#40;object&#40;&#123;&#10;  description &#61; string&#10;  type        &#61; string&#10;&#125;&#41;&#41;">map&#40;object&#40;&#123;&#8230;&#125;&#41;&#41;</code> |  | <code>&#123;&#125;</code> |
| [rules_config](variables.tf#L44) | SecOps Detection rules configuration. | <code title="map&#40;object&#40;&#123;&#10;  enabled  &#61; optional&#40;bool, true&#41;&#10;  alerting &#61; optional&#40;bool, false&#41;&#10;  archived &#61; optional&#40;bool, false&#41;&#10;  run_frequency : optional&#40;string&#41;&#10;&#125;&#41;&#41;">map&#40;object&#40;&#123;&#8230;&#125;&#41;&#41;</code> |  | <code>&#123;&#125;</code> |
<!-- END TFDOC -->
# SecOps Tenant Factory WIP

This blueprint allows automated configuration of SecOps instance at both infrastructure and application level.

The following diagram illustrates the high-level design of SecOps instance configuration in both GCP and SecOps instance, which can be adapted to specific requirements via variables.

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
    - [Data RBAC](#data-rbac)
    - [SecOps rules and reference list management](#secops-rules-and-reference-list-management)
    - [Google Workspace integration](#google-workspace-integration)
- [Files](#files)
- [Variables](#variables)
- [Outputs](#outputs)
<!-- END TOC -->

## Design overview and choices
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/logo.png">
    <img src="./assets/logo.png" alt="SecOps Toolkit">
  </picture>
</p>

# SecOps Toolkit

This repository provides a comprehensive collection of Terraform blueprints, modules, and CICD pipelines designed to automate the implementation of custom integrations, agents, and configurations for Google Cloud SecOps (formerly Chronicle). It aims to provide modular and scalable solutions for various SecOps automation needs.

## Blueprints

This section details the available Terraform blueprints for deploying and managing Google Cloud SecOps components and integrations.

### BindPlane OP Management container running on cos-based GCE instance

<a href="./blueprints/bindplane-gce/" title="BindPlane OP Management console on GCE"><img src="./blueprints/bindplane-gce/images/diagram.png" align="left" width="280px"></a> This [blueprint](./blueprints/bindplane-gke/) is a simple script for running BindPlane OP Management Console container on Google Compute Engine instance with COS.

<br clear="left">

### BindPlane OP Management on GKE

<a href="./blueprints/bindplane-gke/" title="BindPlane OP Management console on GKE"><img src="./blueprints/bindplane-gke/images/diagram.png" align="left" width="280px"></a> This [blueprint](./blueprints/bindplane-gke/) is a modular and scalable solution for deployment of the BindPlane OP Management Console within a Google Kubernetes Engine (GKE) environment.

<br clear="left">

### SecOps Anonymization Pipeline

<a href="./blueprints/secops-anonymization-pipeline/" title="SecOps Anonymization Pipeline"><img src="./blueprints/secops-anonymization-pipeline/images/diagram.png" align="left" width="280px"></a> This [blueprint](./blueprints/secops-gke-forwarder/) is a comprehensive and adaptable solution for constructing a SecOps pipeline for exporting raw data from a SecOps tenant, optionally anonymize this data and then import data back in a different SecOps tenant.

<br clear="left">

### SecOps GKE Forwarder

<a href="./blueprints/secops-gke-forwarder/" title="SecOps GKE Forwarder"><img src="./blueprints/secops-gke-forwarder/images/diagram.png" align="left" width="280px"></a> This [blueprint](./blueprints/secops-gke-forwarder/) is a modular and scalable solution for setting up a SecOps forwarder on Google Kubernetes Engine (GKE). This forwarder is designed to handle multi-tenant data ingestion, ensuring secure and efficient log forwarding to your SecOps SIEM instances.

<br clear="left">

### SecOps Tenant

<a href="./blueprints/secops-tenant/" title="SecOps Tenant"><img src="./blueprints/secops-tenant/images/diagram.png" align="left" width="280px"></a> This [blueprint](./blueprints/secops-tenant/) allows automated configuration of a SecOps instance at both infrastructure and application level with out-of-the-box Feeds integration, automated deployment of SecOps rules and reference lists, as well as Data RBAC scopes.

<br clear="left">

## Modules

This folder contains a suite of Terraform modules for Google SecOps automation. These modules are designed to be composed together and can be forked and modified where the use of third-party code and sources is not allowed.

Modules aim to stay close to the low-level provider resources they encapsulate and share a similar interface that combines management of one resource or set of resources, and their corresponding IAM bindings.

## Pipelines

This repository provides a collection of sample repositories for automating Google Cloud SecOps configuration through CICD pipelines.

### Detection As Code

<a href="./pipelines/detection-as-code/" title="Detection As Code pipeline"><img src="./pipelines/detection-as-code/images/diagram.png" align="left" width="280px"></a> This [sample repository](./pipelines/detection-as-code/) contains ready-to-use code for automated deployment of detection rules and reference lists in Google SecOps via CICD (currently with sample pipelines for GitLab and GitHub).

<br clear="left">
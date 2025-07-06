# SecOps blueprints

This repository provides a collection of Terraform blueprints designed to automate the implementation of custom integrations, agents and configurations for Google Cloud SecOps (aka Chronicle).

## BindPlane OP Management container running on cos-based GCE instance

<a href="./bindplane-gce/" title="BindPlane OP Management console on GCE"><img src="./bindplane-gce/images/diagram.png" align="left" width="300px"></a> <p style="margin-left: 340px">This [blueprint](./bindplane-gke/) is a simple script for running BindPlane OP Management Console container on Google Compute Engine instance with COS.</p>

<br clear="left">

## BindPlane OP Management on GKE

<a href="./bindplane-gke/" title="BindPlane OP Management console on GKE"><img src="./bindplane-gke/images/diagram.png" align="left" width="300px"></a> <p style="margin-left: 340px">This [blueprint](./bindplane-gke/) is a modular and scalable solution for deployment of the BindPlane OP Management Console within a Google Kubernetes Engine (GKE) environment.</p>

<br clear="left">

## SecOps Anonymization Pipeline

<a href="./secops-anonymization-pipeline/" title="SecOps Anonymization Pipeline"><img src="./secops-anonymization-pipeline/images/diagram.png" align="left" width="300px"></a> <p style="margin-left: 340px">This [blueprint](./secops-gke-forwarder/) is a comprehensive and adaptable solution for constructing a SecOps pipeline for exporting raw data from a SecOps tenant, optionally anonymize this data and then import data back in a different SecOps tenant.</p>

<br clear="left">

## SecOps GKE Forwarder

<a href="./secops-gke-forwarder/" title="SecOps GKE Forwarder"><img src="./secops-gke-forwarder/images/diagram.png" align="left" width="300px"></a> <p style="margin-left: 340px">This [blueprint](./secops-gke-forwarder/) is a modular and scalable solution for setting up a SecOps forwarder on Google Kubernetes Engine (GKE). This forwarder is designed to handle multi-tenant data ingestion, ensuring secure and efficient log forwarding to your SecOps SIEM instances.</p>

<br clear="left">

## SecOps Tenant

<a href="./secops-tenant/" title="SecOps Tenant"><img src="./secops-tenant/images/diagram.png" align="left" width="300px"></a> <p style="margin-left: 340px">This [blueprint](./secops-tenant/) allows automated configuration of SecOps instance at both infrastructure and application level with out of the box Feeds integration, automated deployment of SecOps rules and reference lists as well as Data RBAC scopes.</p>

<br clear="left">

## SecOps Tenant Factory

<a href="./secops-tenant-factory/" title="SecOps Tenant Factory"><img src="./secops-tenant-factory/images/diagram.png" align="left" width="300px"></a> <p style="margin-left: 340px">This [blueprint](./secops-tenant-factory/) implements end-to-end configuration of new projects and SecOps SIEM tenants via YAML data configurations and [secops-tenant](./secops-tenant) blueprint code. </p>

<br clear="left">

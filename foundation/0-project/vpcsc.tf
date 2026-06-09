/**
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

locals {
  # fail if we have no valid defaults
  _defaults           = yamldecode(file(local.paths.defaults))
  restricted_services = yamldecode(file(local.paths.restricted_services))
  # extend context with our own data
  ctx = {
    resource_sets = {
      secops_project = ["projects/${module.project.number}"]
    }
    identity_sets = {
      secops_ingress_identities = var.vpc_sc_config.scc_enabled ? [
        "service-org-${var.organization_id}@gcp-sa-chronicle-soar.iam.gserviceaccount.com",
        "service-org-${var.organization_id}@security-center-api.iam.gserviceaccount.com",
        "service-org-${var.organization_id}@gcp-sa-csc-hpsa.iam.gserviceaccount.com",
        "service-org-${var.organization_id}@gcp-sa-asm-hpsa.iam.gserviceaccount.com"
      ] : []
      secops_egress_identities = var.vpc_sc_config.scc_enabled ? [
        "serviceAccount: service-org-${var.organization_id}@gcp-sa-chronicle-soar.iam.gserviceaccount.com",
        "serviceAccount: service-org-${var.organization_id}@security-center-api.iam.gserviceaccount.com"
      ] : []
      secops_cmek_identities = var.vpc_sc_config.cmek_enabled ? [
        "serviceAccount: service-org-${var.organization_id}@gcp-sa-secretmanager.iam.gserviceaccount.com"
      ] : []
    }
    service_sets = {
      restricted_services = local.restricted_services
    }
  }
  paths = {
    for k, v in var.factories_config.paths : k => try(pathexpand(
      startswith(v, "/") || startswith(v, ".")
      ? v :
      "${var.factories_config.dataset}/${v}"
    ), null)
  }
}

module "vpc-sc" {
  for_each      = var.vpc_sc_config.enabled ? { secops = {} } : {}
  source        = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/vpc-sc"
  access_policy = var.access_policy
  access_policy_create = var.access_policy != null ? null : {
    parent = "organizations/${var.organization_id}"
    title  = "secops"
    scopes = ["projects/${module.project.number}"]
  }
  context          = local.ctx
  factories_config = local.paths
}

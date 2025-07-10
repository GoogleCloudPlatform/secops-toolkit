/**
 * Copyright 2025 Google LLC
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
  _factory_data = {
    for f in try(fileset(local._factory_path, "**/*.yaml"), []) :
    trimsuffix(basename(f), ".yaml") => yamldecode(file("${local._factory_path}/${f}"))
  }
  _factory_path = try(pathexpand(var.factories_config.tenants_folder), null)
  tenants = {
    for k, v in local._factory_data :
    (try(v.name, k)) => {
      secops_group_principals = try(v.secops_group_principals, {})
      secops_ingestion_config = try(v.secops_ingestion_config, {})
      secops_tenant_config = can(v.secops_tenant_config) ? {
        tenant_id         = try(v.secops_tenant_config.tenant_id, null)
        tenant_code       = try(v.secops_tenant_config.tenant_code, null)
        tenant_subdomains = try(v.secops_tenant_config.tenant_subdomains, null)
        master_tenant     = try(v.secops_tenant_config.master_tenant, false)
      } : null
      project_id      = try(v.project_id, true)
      project_create  = try(v.project_create, true)
      organization_id = try(v.organization_id, var.organization_id)
      tenant_nodes = {
        include_org = try(v.tenant_nodes.include_org, false)
        folders     = coalesce(v.tenant_nodes.folders, {})
      }
    }
  }
}

module "tenants" {
  for_each                = local.tenants
  source                  = "../secops-tenant"
  secops_group_principals = each.value.secops_group_principals
  secops_ingestion_config = each.value.secops_ingestion_config
  secops_tenant_config = merge(each.value.secops_tenant_config, {
    backstory_sa_email = var.secops_config.backstory_sa_email
    region             = var.secops_config.region
    alpha_apis_region  = var.secops_config.alpha_apis_region
  })
  project_id = each.value.project_id
  project_create_config = each.value.project_create ? {
    parent          = var.tenant_folder
    billing_account = var.billing_account
  } : null
  organization_id = each.value.organization_id
  tenant_nodes    = each.value.tenant_nodes
  providers = {
    restful.feeds    = restful.secops-api
    restful.customer = restful.secops-customer-api
  }
}

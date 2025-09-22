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

module "secops-tenant-secrets" {
  count      = local.bootstrap_secops_tenant ? 1 : 0
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/secret-manager"
  project_id = module.project.project_id
  secrets = { for k in local.secops_sa_types : k =>
    {
      locations = [var.regions.primary]
      latest = {
        enabled = true,
        data    = base64decode(local.secops_service_accounts[k])
      }
    }
  }
}

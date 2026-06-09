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

module "kms" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/kms"
  count      = var.cmek_config.enabled ? 1 : 0
  project_id = module.project.project_id
  keyring = {
    location = var.cmek_config.location
    name     = var.cmek_config.keyring_name
  }
  keys = {
    (var.cmek_config.key_name) = {
      rotation_period = var.cmek_config.rotation_period
      iam = {
        "roles/cloudkms.cryptoKeyEncrypterDecrypter" = [
          "serviceAccount:service-org-${var.organization_id}@gcp-sa-chronicle.iam.gserviceaccount.com"
        ]
      }
    }
  }
  depends_on = [module.project]
}
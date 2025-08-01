/**
 * Copyright 2024 Google LLC
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

data "google_client_config" "default" {
  count = var._tests ? 0 : 1
}

provider "restful" {
  base_url = "https://${var.secops_tenant_config.region}-chronicle.googleapis.com/v1alpha/"
  security = {
    http = {
      token = {
        token = var._tests ? "" : data.google_client_config.default[0].access_token
      }
    }
  }
}

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

# default provider do not use this
provider "restful" {
  base_url = "https://${var.secops_config.alpha_apis_region}-chronicle.googleapis.com/v1alpha/projects/xxxxxxxxxx"
}

data "google_client_config" "default" {
  count = var._tests ? 0 : 1
}

provider "restful" {
  base_url = "https://${var.secops_config.region}-chronicle.googleapis.com/v1alpha/"
  alias    = "feeds"
  security = {
    http = {
      token = {
        token = var._tests ? "" : data.google_client_config.default[0].access_token
      }
    }
  }
}

provider "restful" {
  base_url = "https://${var.secops_config.region == "us" ? "" : concat(var.secops_config.alpha_apis_region,"-")}backstory.googleapis.com/v1/partner/customer"
  alias    = "customer"
  security = {
    http = {
      token = {
        token = var._tests ? "" : data.google_client_config.default[0].access_token
      }
    }
  }
}

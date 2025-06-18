# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

secops_config = {
  region            = "europe"
  alpha_apis_region = "eu"
  source_tenant = {
    gcp_project = "SOURCE_PROJECT_ID"
    customer_id = "xxx-xxxxxx-xxxxx"
  }
  target_tenant = {
    gcp_project  = "TARGET_PROJECT_ID"
    customer_id  = "xxx-xxxxxx-xxxxx"
    forwarder_id = "xxxxxxxxx"
  }
}
skip_anonymization = false
prefix             = "pre"
project_id         = "gcp-project-id"
project_create_config = {
  billing_account = "12345-ABCDE-12345"
}
regions = {
  primary   = "europe-west1"
  secondary = "europe-west1"
}
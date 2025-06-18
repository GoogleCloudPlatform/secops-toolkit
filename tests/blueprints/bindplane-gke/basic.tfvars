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

project_id = "test"
project_create = {
  billing_account_id = "12345-ABCDEF-12345"
  parent             = "folders/2345678901"
}
bindplane_secrets = {
  user            = "admin"
  password        = "sample"
  sessions_secret = "xxxxxx-xxxxxxx-xxxxxx"
  license         = "XXXXXXXXXXXXXXXXXXXXXX"
}
dns_config = {
  bootstrap_private_zone = true
  domain                 = "example.com"
  hostname               = "bindplane"
}
network_config = {
  network_self_link   = "https://www.googleapis.com/compute/v1/projects/prod-net-landing-0/global/networks/prod-landing-0"
  subnet_self_link    = "https://www.googleapis.com/compute/v1/projects/prod-net-landing-0/regions/europe-west1/subnetworks/gke"
  ip_range_gke_master = "192.168.0.0/28"
}
region = "europe-west8"
prefix = "tmp"

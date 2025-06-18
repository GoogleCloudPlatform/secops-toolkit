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
project_create_config = {
  billing_account = "12345-ABCDEF-12345"
  parent          = "folders/2345678901"
}
region = "europe-west8"
network_config = {
  host_project        = "prod-net-landing-0"
  network_self_link   = "https://www.googleapis.com/compute/v1/projects/prod-net-landing-0/global/networks/prod-landing-0"
  subnet_self_link    = "https://www.googleapis.com/compute/v1/projects/prod-net-landing-0/regions/europe-west1/subnetworks/gke"
  ip_range_gke_master = "192.168.0.0/28"
}
prefix = "tmp"
tenants = {
  tenant-1 = {
    chronicle_forwarder_image = "cf_production_stable"
    chronicle_region          = "europe"
    tenant_id                 = "tenant-1"
    namespace                 = "ten-1"
    forwarder_config = {
      config_file_content = <<EOF
      output:
  url: malachiteingestion-pa.googleapis.com:443
  identity:
    identity:
    collector_id: COLLECTOR_ID \
    customer_id: CUSTOMER_ID \

collectors:
  - syslog:
      common:
        enabled: true
        data_type: "WINDOWS_DHCP"
        data_hint:
        batch_n_seconds: 10
        batch_n_bytes: 1048576
      tcp_address: 0.0.0.0:10514
      udp_address: 0.0.0.0:10514
      connection_timeout_sec: 60
      tcp_buffer_size: 524288
  - syslog:
      common:
        enabled: true
        data_type: "WINDOWS_DNS"
        data_hint:
        batch_n_seconds: 10
        batch_n_bytes: 1048576
      tcp_address: 0.0.0.0:10515
      connection_timeout_sec: 60
      tcp_buffer_size: 524288
EOF
    }
  }
  tenant-2 = {
    chronicle_forwarder_image = "cf_production_stable"
    chronicle_region          = "europe"
    tenant_id                 = "tenant-2"
    namespace                 = "tenant-2"
    forwarder_config = {
      secret_key   = <<EOF
      {
"type": "service_account",
"project_id": "xxxx",
"private_key_id": "xxxxxxxxxxxxxx",
"private_key": "-----BEGIN PRIVATE KEY-----\nsdcCDSCsLxhfQIOwdvzCn5wcwJ7xVA=\n-----END PRIVATE KEY-----\n",
"client_email": "sample@sample.iam.gserviceaccount.com",
"client_id": "ASDCVSACSA",
"auth_uri": "https://accounts.google.com/o/oauth2/auth",
"token_uri": "https://oauth2.googleapis.com/token",
"auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
"client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/sample.iam.gserviceaccount.com",
"universe_domain": "googleapis.com"
}
EOF
      customer_id  = "XXXXXXX-XXXX-XXXX-XXXX-XXXXXX"
      collector_id = "XXXXXXX-XXXX-XXXX-XXXX-XXXXXX"
    }
  }
}
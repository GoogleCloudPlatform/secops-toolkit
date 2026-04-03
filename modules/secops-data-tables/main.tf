# Copyright 2026 Google LLC
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

locals {
  data_tables = try(yamldecode(file(var.factories_config.data_tables)), var.data_tables_config)

  # Map of table_id to CSV content
  data_tables_csv = {
    for k, v in local.data_tables : k => csvdecode(file("${var.factories_config.data_tables_defs}/${k}.csv"))
    if fileexists("${var.factories_config.data_tables_defs}/${k}.csv")
  }

  # Flattened rows for for_each
  flattened_rows = flatten([
    for table_id, rows in local.data_tables_csv : [
      for i, row in rows : {
        key      = "${table_id}_${i}"
        table_id = table_id
        ttl      = try(local.data_tables[table_id].row_time_to_live, null)
        values = [
          for col in local.data_tables[table_id].columns : row[col.original_column]
        ]
      }
    ]
  ])
}

resource "google_chronicle_data_table" "default" {
  provider      = google-beta
  for_each      = local.data_tables
  project       = var.secops_config.project
  location      = var.secops_config.region
  instance      = var.secops_config.customer_id
  data_table_id = each.key
  description   = each.value.description

  dynamic "column_info" {
    for_each = each.value.columns
    content {
      column_index       = column_info.key
      original_column    = column_info.value.original_column
      column_type        = try(column_info.value.column_type, "STRING")
      key_column         = try(column_info.value.key_column, false)
      mapped_column_path = try(column_info.value.mapped_column_path, null)
    }
  }
}

resource "google_chronicle_data_table_row" "default" {
  provider         = google-beta
  for_each         = { for r in local.flattened_rows : r.key => r }
  project          = var.secops_config.project
  location         = var.secops_config.region
  instance         = var.secops_config.customer_id
  data_table_id    = each.value.table_id
  values           = each.value.values
  row_time_to_live = each.value.ttl

  depends_on = [google_chronicle_data_table.default]
  lifecycle {
    ignore_changes = [
      values
    ]
  }
}

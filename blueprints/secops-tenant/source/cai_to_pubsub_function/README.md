## GCP Cloud Asset Inventory to Chronicle SIEM via a GCP PubSub Topic
**This script is for fetching asset inventory data from one or more GCP nodes (
organization, folder etc.) and push them in one or more PubSub topics according
to the configuration passed as body of teh HTTP request.**

**HTTP Body for request:**
<br>Below details need to be provided in the Body section of Cloud Scheduler to
allow the ingestion script for data collection.<br>NOTE: The details need to be
provided in the JSON format only.</br>

| Variable                | Description                                                                                                                                                                                                                                                                                                                 | Required | Default | Secret |
|-------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|---------|--------|
| NODES                   | List of the organization, folder, or project the assets belong to. Format: "organizations/[organization-number]" (such as "organizations/123"), "projects/[project-id]" (such as "projects/my-project-id"), "projects/[project-number]" (such as "projects/12345"), or "folders/[folder-number]" (such as "folders/12345"). | Yes      | -       | No     |
| CONTENT_TYPE            | For the integration with Chronicle SecOps this should always be "RESOURCE"                                                                                                                                                                                                                                                  | Yes      | -       | No     |
| PAGE_SIZE               | Default is 100, minimum is 1, and maximum is 1000.                                                                                                                                                                                                                                                                          | Yes      | -       | No     |
| CHRONICLE_ASSETS_CONFIG | JSON configuration object as per the following sample                                                                                                                                                                                                                                                                       | Yes      | -       | No     |

```hcl
CHORNICLE_ASSETS_CONFIG = {
    GCP_BIGQUERY_CONTEXT = {
        asset_types = ["bigquery.googleapis.com/Dataset","bigquery.googleapis.com/Model","bigquery.googleapis.com/Table"]
        pubsub_topic_id = "chronicle_gcp_bigquery_context"
    }
    ...
}
```

### Documentation

* [The GCP CAI Asset List Method](https://cloud.google.com/asset-inventory/docs/reference/rest/v1/assets/list)
* [The GCP CAI Quota Limits](https://cloud.google.com/asset-inventory/docs/quota)

### Date Created
07/04/2022

### AUTHORS
cmmartin@
bruzzechesse@

### TODO
* Implement batch sending of messages to PubSub
* Implement GCP Logging rather than Print
* Improve return codes throughout main function
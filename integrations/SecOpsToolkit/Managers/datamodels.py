from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import uuid
import warnings
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import consts
import utils
from EnvironmentCommon import EnvironmentHandle
from SiemplifyConnectorsDataModel import AlertInfo
from SiemplifyUtils import convert_string_to_unix_time
from TIPCommon.transformation import add_prefix_to_dict, dict_to_flat
from exceptions import DetectionParsingError

if TYPE_CHECKING:
    from typing import Self

    from TIPCommon.types import SingleJson


IP_ADDRESS_ENTITY_TYPE = "IP_ADDRESS"


class IOC:
    class Source:
        def __init__(
            self,
            raw_data,
            category=None,
            intRawConfidenceScore=None,
            normalizedConfidenceScore=None,
            rawSeverity=None,
            source=None,
            **kwargs,
        ):
            self.raw_data = raw_data
            self.category = category
            self.int_raw_confidence_score = intRawConfidenceScore
            self.normalized_confidence_score = (
                str(normalizedConfidenceScore).lower()
                if normalizedConfidenceScore
                else None
            )
            self.raw_severity = str(rawSeverity).lower() if rawSeverity else None
            self.source = source

    def __init__(
        self,
        raw_data,
        categories=None,
        domain_name=None,
        sources=None,
        uri=None,
        fallback_severity=None,
        **_,
    ):
        self.raw_data = raw_data
        self.flat_raw_data = dict_to_flat(self.raw_data)
        self.domain_name = domain_name
        self.first_seen_time = raw_data.get(
            "firstSeenTime",
            raw_data.get("firstSeenTimestamp")
        )
        self.ioc_ingest_time = raw_data.get(
            "iocIngestTime",
            raw_data.get("iocIngestTimestamp")
        )
        self.last_seen_time = raw_data.get(
            "lastSeenTime",
            raw_data.get("lastSeenTimestamp")
        )
        self.sources = sources or []
        self.categories = categories or []
        self.uri = uri
        self.id = utils.generate_hash(f"{self.domain_name}{self.last_seen_time}")
        self.fallback_severity = fallback_severity
        self.highest_siemplify_severity = (
            self.get_highest_siemplify_severity
            or consts.SIEMPLIFY_SEVERITIES.get(self.fallback_severity.lower())
            if self.fallback_severity
            else None
        )

        try:
            self.first_seen_time_ms = convert_string_to_unix_time(self.first_seen_time)
        except Exception:
            self.first_seen_time_ms = 1

        try:
            self.ioc_ingest_time_ms = convert_string_to_unix_time(self.ioc_ingest_time)
        except Exception:
            self.ioc_ingest_time_ms = 1

        try:
            self.last_seen_time_ms = convert_string_to_unix_time(self.last_seen_time)
        except Exception:
            self.last_seen_time_ms = 1

    @property
    def artifact(self) -> SingleJson:
        """Old format artifact."""
        _json = self.raw_data.get("artifact", self.raw_data.get("artifactIndicator"))
        if "domain" in _json:
            _json["domainName"] = _json.pop("domain")

        return _json

    def as_json(self):
        """Format IOC details as a JSON object."""
        _json = copy.deepcopy(self.raw_data)
        _json["artifact"] = self.artifact
        _json["iocIngestTime"] = self.ioc_ingest_time
        _json["firstSeenTime"] = self.first_seen_time
        _json["lastSeenTime"] = self.last_seen_time
        return _json

    def as_csv(self):
        return {
            "Domain": self.domain_name,
            "Category": (
                self.categories[0] if self.categories else
                self.sources[0].category if self.sources else ""
            ),
            "Source": self.sources[0].source if self.sources else "",
            "Confidence": (
                self.sources[0].normalized_confidence_score if self.sources else ""
            ),
            "Severity": self.sources[0].raw_severity if self.sources else "",
            "IoC Ingest Time": self.ioc_ingest_time,
            "IoC First Seen Time": self.first_seen_time,
            "IoC Last Seen Time": self.last_seen_time,
            "URI": self.uri[0] if self.uri else "",
        }

    @property
    def hash_id(self):
        temp_data = deepcopy(self.raw_data)
        temp_data.pop("uri", None)
        return hashlib.md5(
            json.dumps(temp_data, sort_keys=True).encode("utf8")
        ).hexdigest()

    @property
    def siemplify_severity(self):
        return consts.SIEMPLIFY_SEVERITIES.get(
            str(self.sources[0].raw_severity).lower() if self.sources else "info", -1
        )

    @property
    def unified_siemplify_severity(self):
        severity_value = next(
            (
                source.raw_severity
                for source in self.sources
                if source.raw_severity and source.raw_severity != consts.NOT_ASSIGNED
            ),
            None,
        )

        return (
            consts.SIEMPLIFY_SEVERITIES.get(severity_value.lower())
            if severity_value
            else None
        )

    @property
    def get_highest_siemplify_severity(self):
        return max(
            [
                consts.SIEMPLIFY_SEVERITIES.get(source.raw_severity)
                for source in self.sources
                if source.raw_severity and source.raw_severity != consts.NOT_ASSIGNED
            ],
            default=None,
        )

    @property
    def average_confidence_score(self):
        confidence_scores = [
            int(source.int_raw_confidence_score)
            for source in self.sources
            if source.int_raw_confidence_score
        ]

        return (
            sum(confidence_scores) / len(confidence_scores)
            if confidence_scores
            else None
        )

    @property
    def average_normalized_confidence_score(self):
        normalized_confidence_scores = [
            consts.SIEMPLIFY_SEVERITIES.get(source.normalized_confidence_score)
            for source in self.sources
            if source.normalized_confidence_score is not None
            and source.normalized_confidence_score != consts.NOT_ASSIGNED
        ]

        return (
            sum(normalized_confidence_scores) / len(normalized_confidence_scores)
            if normalized_confidence_scores
            else None
        )

    def as_alert_info(self, environment_common):
        """
        Create an AlertInfo out of the current finding
        :param environment_common: {EnvironmentHandle} The environment common object for fetching the environment
        :return: {AlertInfo} The created AlertInfo object
        """
        alert_info = AlertInfo()
        alert_info.environment = environment_common.get_environment(
            dict_to_flat(self.raw_data)
        )
        alert_info.ticket_id = str(uuid.uuid4())
        alert_info.display_id = str(uuid.uuid4())
        alert_info.name = f"IOC Domain Match: {self.domain_name}"
        alert_info.description = f"IOC Domain Match: : {self.domain_name}"
        alert_info.device_vendor = consts.VENDOR
        alert_info.device_product = (
            self.sources[0].source if self.sources else consts.PRODUCT
        )
        alert_info.priority = self.siemplify_severity
        alert_info.rule_generator = "IOC Domain Match"
        alert_info.start_time = self.first_seen_time_ms
        alert_info.end_time = self.last_seen_time_ms
        alert_info.events = self.events

        return alert_info

    def as_unified_alert_info(
        self, alert_info, environment_common, device_product_field
    ):
        """
        Prepare AlertInfo for unified connector
        :param alert_info: {AlertInfo} AlertInfo object
        :param environment_common: {EnvironmentHandle} environment common object for fetching the environment
        :param device_product_field: {str} key to use for device product extraction
        :return: {AlertInfo} created AlertInfo object
        """
        alert_info.environment = environment_common.get_environment(self.flat_raw_data)
        alert_info.ticket_id = self.id
        alert_info.display_id = str(uuid.uuid4())
        alert_info.name = "IOC Match"
        alert_info.description = self.get_description()
        alert_info.device_vendor = consts.UNIFIED_CONNECTOR_DEVICE_VENDOR
        alert_info.priority = (
            self.unified_siemplify_severity
            or consts.SIEMPLIFY_SEVERITIES.get(self.fallback_severity.lower())
        )
        alert_info.rule_generator = "IOC Match"
        alert_info.start_time = self.last_seen_time_ms
        alert_info.end_time = self.last_seen_time_ms
        alert_info.events = self.unified_events
        alert_info.extensions = {
            "alert_type": consts.ALERT_TYPE_NAMES.get(consts.ALERT_TYPES.get("ioc"))
        }
        alert_info.device_product = (
            next(
                (
                    event.get(device_product_field)
                    for event in alert_info.events
                    if event.get(device_product_field)
                ),
                None,
            )
            or consts.UNIFIED_CONNECTOR_DEVICE_PRODUCT
        )

        return alert_info

    @property
    def events(self):
        temp_data = deepcopy(self.raw_data)
        temp_data.pop("sources", None)

        events = []
        for source in self.sources:
            source_data = deepcopy(source.raw_data)
            source_data.update(temp_data)
            events.append(dict_to_flat(source_data))

        return events

    @property
    def unified_events(self):
        event = deepcopy(self.flat_raw_data)
        event["alert_type"] = consts.ALERT_TYPE_NAMES.get(consts.ALERT_TYPES.get("ioc"))
        event["event_type"] = (
            f"{consts.ALERT_TYPE_NAMES.get(consts.ALERT_TYPES.get('ioc'))}_Event"
        )
        return [event]

    def get_description(self):
        return utils.convert_list_to_comma_string(
            [source.category or "" for source in self.sources]
        )


class IOCDetail:
    class Source:
        class Address:
            def __init__(
                self, raw_data, port=None, domain=None, ipAddress=None, **kwargs
            ):
                self.raw_data = raw_data
                self.port = port
                self.domain = domain
                self.ip_address = ipAddress

        def __init__(
            self,
            raw_data,
            source_url=None,
            category=None,
            first_active_time=None,
            last_active_time=None,
            str_raw_confidence_score=None,
            addresses=None,
            raw_severity=None,
        ):
            self.raw_data = raw_data
            self.source_url = source_url
            self.category = category
            self.str_raw_confidence_score = (
                str(str_raw_confidence_score).lower()
                if str_raw_confidence_score else None
            )
            self.numeric_raw_confidence_score = (
                consts.CONFIDENCE_TO_INT_MAPPING.get(
                    str(str_raw_confidence_score).lower(), 0
                )
                if str_raw_confidence_score
                else None
            )
            self.raw_severity = str(raw_severity).lower() if raw_severity else None
            self.numeric_raw_severity = consts.IOC_SEVERITIES.get(self.raw_severity, 0)
            self.addresses = addresses
            self.first_active_time = first_active_time
            self.last_active_time = last_active_time
            self.source = source_url

            try:
                self.first_active_time_ms = convert_string_to_unix_time(
                    self.first_active_time
                )
            except Exception:
                self.first_active_time_ms = 1

            try:
                self.last_active_time_ms = convert_string_to_unix_time(
                    self.last_active_time
                )
            except Exception:
                self.last_active_time_ms = 1

        def to_json(self):
            """Format Source as a JSON object."""
            if "sourceName" in self.raw_data:
                return self.raw_data

            return {
                "category": self.category,
                "firstActiveTime": self.first_active_time,
                "lastActiveTime": self.last_active_time,
                "addresses": [ad.raw_data for ad in self.addresses],
                "rawSeverity": self.raw_severity,
                "confidenceScore": {
                    "strRawConfidenceScore": self.str_raw_confidence_score
                },
            }

        def as_enrichment(self):
            return dict_to_flat(self.raw_data)

        def to_table(self, for_domain=False):
            try:
                confidence = IOCDetail.avg_confidnce_to_ui(
                    int(self.str_raw_confidence_score)
                    if self.str_raw_confidence_score
                    else None
                )
            except:
                confidence = (
                    self.str_raw_confidence_score.title()
                    if self.str_raw_confidence_score
                    else "N/A"
                )

            table_data = {
                "Source": self.source or "N/A",
                "Severity": self.raw_severity.title() if self.raw_severity else None,
                "Category": self.category,
                "Confidence": confidence,
            }
            if not for_domain:
                table_data["Related Domains"] = utils.convert_list_to_comma_string(
                    [address.domain for address in self.addresses]
                )

            return {
                key: value for key, value in table_data.items() if value is not None
            }

    def __init__(
        self,
        raw_data,
        sources=None,
        uri=None,
        **_,
    ):
        self.raw_data = raw_data
        self.sources = sources
        self.uri = uri
        self.first_active_time = (
            sorted(
                sources,
                key=lambda source: (
                    source.first_active_time is None,
                    source.first_active_time,
                ),
            )[0].first_active_time
            if sources
            else None
        )
        self.last_active_time = (
            sorted(
                sources,
                key=lambda source: (
                    source.last_active_time is not None,
                    source.last_active_time,
                ),
                reverse=True,
            )[0].last_active_time
            if sources
            else None
        )

    def to_json(self):
        """Format IOC Detail as a JSON object."""
        if "sources" in self.raw_data:
            return self.raw_data

        return {
            "sources": [sd.to_json() for sd in self.sources],
            **self.raw_data
        }

    def as_enrichment(self, prefix, for_domain=False):
        if not self.sources:
            return {}

        source_addresses = []
        for source in self.sources:
            source_addresses.extend(source.addresses)

        source_categories = [
            source.category for source in self.sources if source.category
        ]
        source_sources = [source.source for source in self.sources if source.source]
        address_domains = [
            address.domain for address in source_addresses if address.domain
        ]

        data = {
            "severity": consts.INT_TO_SEVERITY_MAPPING.get(
                self.highest_source_severity[1]
            ),
            "average_confidence": self.average_source_confidence,
            "categories": utils.convert_list_to_comma_string(source_categories),
            "sources": utils.convert_list_to_comma_string(source_sources),
            "first_seen": self.first_active_time,
            "last_seen": self.last_active_time,
            "report_link": self.uri[0] if self.uri else None,
        }

        if not for_domain:
            data["related_domains"] = utils.convert_list_to_comma_string(
                address_domains
            )

        clean_enrichment_data = {k: v for k, v in data.items() if v}
        return add_prefix_to_dict(dict_to_flat(clean_enrichment_data), prefix)

    def to_table(self, for_domain=False):
        return [source.to_table(for_domain=for_domain) for source in self.sources]

    def to_insight(self, for_domain=False):
        severity_color_mapper = {
            "N/A": None,
            "Info": None,
            "Low": "#ffcc00",
            "Medium": "#ff9900",
            "High": "#ff0000",
        }

        str_highest_severity = consts.INT_TO_SEVERITY_MAPPING.get(
            self.highest_source_severity[1]
        )

        insight_content = f"<h1><strong>Severity: "
        insight_content += (
            f'<span style="color: {severity_color_mapper.get(str_highest_severity)};">'
            if severity_color_mapper.get(str_highest_severity)
            else ""
        )
        insight_content += f'{str_highest_severity or "N/A"}</span><br /></strong></h1>'
        insight_content += (
            f'<p><strong><strong>First Active Time: {self.first_active_time or "N/A"}<br />Last Active Time: '
            f'{self.last_active_time or "N/A"}</strong></strong></p><br />'
        )

        for source in self.sources:
            insight_content += (
                f'<h3><strong>Source: {source.source or "N/A"}<br /></strong></h3>'
            )
            insight_content += f"<p><strong><span >Severity:<strong>"
            insight_content += (
                f'<span style="color: {severity_color_mapper.get(source.raw_severity.title())};"> '
                if severity_color_mapper.get(source.raw_severity.title())
                else ""
            )
            insight_content += f'{source.raw_severity.title() or "N/A"}</span><br />'

            try:
                confidence_score = int(source.str_raw_confidence_score)
                confidence_score = IOCDetail.avg_confidnce_to_ui(confidence_score)
            except:
                confidence_score = (
                    source.str_raw_confidence_score.title()
                    if source.str_raw_confidence_score
                    else "N/A"
                )

            insight_content += (
                f"<span>Confidence: "
                f"{confidence_score}<br />"
                f"Category: {source.category}<br />"
            )
            if not for_domain:
                insight_content += (
                    f"Related Domains: "
                    f'{utils.convert_list_to_comma_string([address.domain for address in source.addresses]) or "N/A"}'
                    f"</span></strong></span></strong></p><br />"
                )

        url = self.uri[0] if self.uri else "N/A"
        insight_content += (
            f'<p><strong><span"><strong><span>'
            f"<br />Additional information is available here: <a href={url}>{url}</a></span>"
            f"</strong></span></strong></p><p><span>&nbsp;</span></p>"
        )

        return insight_content

    @property
    def highest_source_severity(self):
        if not self.sources:
            return "n/a", 0

        sorted_sources = sorted(
            self.sources, key=lambda source: source.numeric_raw_severity
        )
        return sorted_sources[-1].raw_severity, sorted_sources[-1].numeric_raw_severity

    @property
    def is_full_data(self) -> bool:
        return self.sources and not self.uri

    @property
    def average_source_confidence(self):
        if not self.sources:
            return "N/A"

        numerical_confidences = []
        for source in self.sources:
            try:
                if source.str_raw_confidence_score:
                    numerical_confidences.append(int(source.str_raw_confidence_score))
            except:
                if source.numeric_raw_confidence_score:
                    numerical_confidences.append(source.numeric_raw_confidence_score)

        if not numerical_confidences:
            return "N/A"

        avg_confidence = sum(numerical_confidences) / len(numerical_confidences)
        return IOCDetail.avg_confidnce_to_ui(int(avg_confidence))

    @staticmethod
    def avg_confidnce_to_ui(avg_confidence):
        if avg_confidence in range(1, 46):
            return "Low"
        elif avg_confidence in range(46, 76):
            return "Medium"
        elif avg_confidence in range(76, 101):
            return "High"
        else:
            return "N/A"

class Asset:
    def __init__(
        self,
        raw_data,
        hostname=None,
        ip_address=None,
        first_seen_artifact_time=None,
        last_seen_artifact_time=None,
        **kwargs,
    ):
        self.raw_data = raw_data
        self.hostname = hostname
        self.ip_address = ip_address
        self.first_seen_artifact_time = first_seen_artifact_time
        self.last_seen_artifact_time = last_seen_artifact_time

        try:
            self.first_seen_artifact_time_ms = convert_string_to_unix_time(
                self.first_seen_artifact_time
            )
        except Exception:
            self.first_seen_time_ms = 1

        try:
            self.last_seen_artifact_time_ms = convert_string_to_unix_time(
                self.last_seen_artifact_time
            )
        except Exception:
            self.ioc_ingest_time_ms = 1

    def as_json(self):
        return self.raw_data

    def as_csv(self):
        return {
            "Hostname": self.hostname,
            "IP Address": self.ip_address,
            "First Seen Artifact": self.first_seen_artifact_time,
            "Last Seen Artifact": self.last_seen_artifact_time,
        }


class Event:
    def __init__(self, raw_data, event_type, product_name, timestamp):
        self.raw_data = raw_data
        self.event_type = event_type
        self.product_name = product_name
        self.timestamp = timestamp

    @property
    def get_urls_list(self):
        urls = [self.raw_data.get("target", {}).get("url")]

        return [u for u in urls if u]

    @property
    def get_hashes_list(self):
        hashes = [
            self.raw_data.get("target", {}).get("file", {}).get("md5"),
            self.raw_data.get("target", {}).get("file", {}).get("sha1"),
            self.raw_data.get("target", {}).get("file", {}).get("sha256"),
        ]

        return [h for h in hashes if h]

    @property
    def get_ips_list(self):
        ips = []

        ips.extend(self.raw_data.get("target", {}).get("ip", []))
        ips.extend(self.raw_data.get("target", {}).get("asset", {}).get("ip", []))
        ips.extend(self.raw_data.get("src", {}).get("ip", []))
        ips.extend(self.raw_data.get("src", {}).get("asset", {}).get("ip", []))
        ips.extend(self.raw_data.get("principal", {}).get("ip", []))
        ips.extend(self.raw_data.get("principal", {}).get("asset", {}).get("ip", []))

        return ips

    @property
    def get_hostnames_list(self):
        hostnames = [
            self.raw_data.get("target", {}).get("hostname"),
            self.raw_data.get("target", {}).get("asset", {}).get("hostname"),
            self.raw_data.get("principal", {}).get("asset", {}).get("hostname"),
            self.raw_data.get("principal", {}).get("hostname"),
            self.raw_data.get("src", {}).get("hostname"),
        ]

        return [h for h in hostnames if h]

    @property
    def get_str_processes_list(self):
        processes = [
            self.raw_data.get("target", {})
            .get("process", {})
            .get("file", {})
            .get("full_path"),
            self.raw_data.get("target", {})
            .get("parent_process", {})
            .get("file", {})
            .get("full_path"),
        ]

        return [p for p in processes if p]

    @property
    def get_int_processes_list(self):
        processes = [
            self.raw_data.get("target", {}).get("process", {}).get("pid"),
            self.raw_data.get("target", {}).get("process", {}).get("parent_pid"),
            self.raw_data.get("target", {}).get("parent_process", {}).get("pid"),
        ]

        return [p for p in processes if p]

    @property
    def get_subjects_list(self):
        subjects = [self.raw_data.get("network", {}).get("email", {}).get("subject")]

        return [s for s in subjects if s]

    @property
    def get_emails_list(self):
        emails = []
        emails.extend(self.raw_data.get("network", {}).get("email", {}).get("to", []))
        emails.extend(self.raw_data.get("network", {}).get("email", {}).get("cc", []))
        emails.extend(self.raw_data.get("network", {}).get("email", {}).get("bcc", []))
        emails.extend([self.raw_data.get("network", {}).get("email", {}).get("from")])

        return [e for e in emails if e]

    @property
    def get_users_list(self):
        users = [
            self.raw_data.get("principal", {}).get("user", {}).get("user_display_name"),
            self.raw_data.get("src", {}).get("user", {}).get("user_display_name"),
            self.raw_data.get("target", {}).get("user", {}).get("user_display_name"),
        ]

        return [u for u in users if u]

    @property
    def get_all_entities(self):
        return (
            self.get_users_list
            + self.get_emails_list
            + self.get_subjects_list
            + self.get_str_processes_list
            + self.get_int_processes_list
            + self.get_hostnames_list
            + self.get_ips_list
            + self.get_hashes_list
            + self.get_urls_list
        )


class Alert:
    class AlertInfo:
        def __init__(
            self,
            raw_data,
            name=None,
            sourceProduct=None,
            severity=None,
            timestamp=None,
            rawLog=None,
            uri=None,
            alert_type=None,
            fallback_severity=None,
            **kwargs,
        ):
            self.raw_data = raw_data
            self._flat_raw_data = None
            self.name = name
            self.source_product = sourceProduct
            self.severity = str(severity).lower() if severity else None
            self.timestamp = timestamp
            self.raw_log = rawLog
            self.uri = uri
            self.id = utils.generate_hash(json.dumps(self.raw_data))
            self.product_name = (
                self.raw_data.get("udmEvent", {}).get("metadata", {}).get("productName")
            )
            self.product_event_type = (
                self.raw_data.get("udmEvent", {})
                .get("metadata", {})
                .get("productEventType")
            )
            self.alert_type = alert_type
            self.alert_main_type = consts.EXTERNAL_ALERT_TYPE
            self.fallback_severity = fallback_severity
            self.unified_siemplify_severity = (
                self.get_unified_siemplify_severity
                or consts.SIEMPLIFY_SEVERITIES.get(self.fallback_severity.lower())
                if self.fallback_severity
                else None
            )

            try:
                self.timestamp_ms = convert_string_to_unix_time(self.timestamp)
            except Exception:
                self.timestamp_ms = 1

        @property
        def flat_raw_data(self):
            """Lazily compute flattened raw data with udmEvent renamed to event."""
            if self._flat_raw_data is None:
                self._flat_raw_data = dict_to_flat(
                    utils.rename_dict_key(self.raw_data, "udmEvent", "event")
                )
            return self._flat_raw_data

        @property
        def siemplify_severity(self):
            return consts.SIEMPLIFY_SEVERITIES.get(self.severity, -1)

        @property
        def get_unified_siemplify_severity(self):
            return (
                consts.SIEMPLIFY_SEVERITIES.get(self.raw_data.get("severity").lower())
                if self.raw_data.get("severity")
                and self.raw_data.get("severity") != consts.NOT_ASSIGNED
                else None
            )

        def as_alert_info(
            self, hostname, events, environment_common, start_time=None, end_time=None
        ):
            """
            Create an AlertInfo out of the current finding
            :param hostname: {str} The hostname of the asset to which this alert info belongs
            :param events: {list} List of the events of the alert info
            :param environment_common: {EnvironmentHandle} The environment common object for fetching the environment
            :param start_time: {int} The start time of the AlertInfo (optional).
            :param end_time: {int} The end time of the AlertInfo (optional).
            :return: {AlertInfo} The created AlertInfo object
            """
            alert_info = AlertInfo()
            alert_info.environment = environment_common.get_environment(
                dict_to_flat(self.raw_data)
            )
            alert_info.ticket_id = str(uuid.uuid4())
            alert_info.display_id = str(uuid.uuid4())
            alert_info.name = f"{self.name} for {hostname}"
            alert_info.description = f"{self.name} for {hostname}"
            alert_info.device_vendor = consts.VENDOR
            alert_info.device_product = f"{self.source_product} for Google Chronicle"
            alert_info.priority = self.siemplify_severity
            alert_info.rule_generator = "Asset"
            alert_info.start_time = start_time or self.timestamp_ms
            alert_info.end_time = end_time or self.timestamp_ms
            alert_info.events = events
            return alert_info

        def as_unified_alert_info(
            self, alert_info, environment_common, device_product_field
        ):
            """
            Prepare AlertInfo for unified connector
            :param alert_info: {AlertInfo} AlertInfo object
            :param environment_common: {EnvironmentHandle} environment common object for fetching the environment
            :param device_product_field: {str} key to use for device product extraction
            :return: {AlertInfo} created AlertInfo object
            """
            alert_info.environment = environment_common.get_environment(
                self.flat_raw_data
            )
            alert_info.ticket_id = self.id
            alert_info.display_id = str(uuid.uuid4())
            alert_info.name = self.name
            alert_info.description = self.get_description()
            alert_info.device_vendor = consts.UNIFIED_CONNECTOR_DEVICE_VENDOR
            alert_info.priority = self.unified_siemplify_severity
            alert_info.rule_generator = f"EXTERNAL Alert: {self.name}"
            alert_info.start_time = self.timestamp_ms
            alert_info.end_time = self.timestamp_ms
            alert_info.events = self.unified_events
            alert_info.extensions = {
                "alert_type": consts.ALERT_TYPE_NAMES.get(
                    consts.ALERT_TYPES.get("external")
                ),
                "alert_name": self.name,
                "product_name": self.product_name,
            }
            alert_info.device_product = (
                next(
                    (
                        event.get(device_product_field)
                        for event in alert_info.events
                        if event.get(device_product_field)
                    ),
                    None,
                )
                or consts.UNIFIED_CONNECTOR_DEVICE_PRODUCT
            )

            return alert_info

        def as_event(self):
            return dict_to_flat(self.raw_data)

        @property
        def unified_events(self):
            """Process unified events.

            Returns:
                list: A list of dictionaries containing processed unified events.
            """
            raw_alert_data = deepcopy(self.raw_data)
            emails = (
                raw_alert_data.get("udmEvent", {}).get("network", {}).get("email", {})
            )

            if emails.get("to") or emails.get("cc") or emails.get("bcc"):
                emails["to"] = list(
                    set(
                        emails.get("to", [])
                        + emails.get("cc", [])
                        + emails.get("bcc", [])
                    )
                )
                emails.pop("cc", None)
                emails.pop("bcc", None)

            additional_info = {
                "alert_type": consts.ALERT_TYPE_NAMES.get(
                    consts.ALERT_TYPES.get("external")
                ),
                "event_type": raw_alert_data.get("udmEvent", {})
                .get("metadata", {})
                .get("eventType"),
                "event_category": utils.get_prefix_from_string(
                    raw_alert_data.get("udmEvent", {})
                    .get("metadata", {})
                    .get("eventType")
                ),
            }

            events = utils.separate_data_per_multiple_values_keys(
                utils.rename_dict_key(raw_alert_data, "udmEvent", "event"),
                consts.EXTERNAL_MULTIPLE_VALUES_NESTED_KEYS,
                additional_info,
            )

            return [dict_to_flat(event) for event in events]

        def get_description(self):
            return utils.convert_list_to_comma_string(
                [
                    item.get("description", "")
                    for item in self.raw_data.get("udmEvent", {}).get(
                        "securityResult", []
                    )
                ]
            )

        @property
        def hash_id(self):
            temp_data = deepcopy(self.raw_data)
            temp_data.pop("uri", None)
            return hashlib.md5(
                json.dumps(temp_data, sort_keys=True).encode("utf8")
            ).hexdigest()

        @property
        def get_unique_product_name(self):
            return self.product_name

        @property
        def get_product_names_list(self):
            return [self.product_name]

        @property
        def get_urls_list(self):
            urls = [self.raw_data.get("udmEvent", {}).get("target", {}).get("url")]
            return [u for u in urls if u]

        @property
        def get_hashes_list(self):
            hashes = [
                self.raw_data.get("udmEvent", {})
                .get("target", {})
                .get("file", {})
                .get("md5"),
                self.raw_data.get("udmEvent", {})
                .get("target", {})
                .get("file", {})
                .get("sha1"),
                self.raw_data.get("udmEvent", {})
                .get("target", {})
                .get("file", {})
                .get("sha256"),
            ]
            return [h for h in hashes if h]

        @property
        def get_ips_list(self):
            ips = (
                self.raw_data.get("udmEvent", {}).get("target", {}).get("ip", [])
                + self.raw_data.get("udmEvent", {})
                .get("target", {})
                .get("asset", {})
                .get("ip", [])
                + self.raw_data.get("udmEvent", {}).get("src", {}).get("ip", [])
                + self.raw_data.get("udmEvent", {})
                .get("src", {})
                .get("asset", {})
                .get("ip", [])
                + self.raw_data.get("udmEvent", {}).get("principal", {}).get("ip", [])
                + self.raw_data.get("udmEvent", {})
                .get("principal", {})
                .get("asset", {})
                .get("ip", [])
            )

            return list(set(ips))

        @property
        def get_hostnames_list(self):
            hostnames = list(
                {
                    self.raw_data.get("udmEvent", {}).get("target", {}).get("hostname"),
                    self.raw_data.get("udmEvent", {})
                    .get("target", {})
                    .get("asset", {})
                    .get("hostname"),
                    self.raw_data.get("udmEvent", {})
                    .get("principal", {})
                    .get("hostname"),
                    self.raw_data.get("udmEvent", {})
                    .get("principal", {})
                    .get("asset", {})
                    .get("hostname"),
                    self.raw_data.get("udmEvent", {}).get("src", {}).get("hostname"),
                }
            )
            return [h for h in hostnames if h]

        @property
        def get_processes_list(self):
            processes = list(
                {
                    self.raw_data.get("udmEvent", {})
                    .get("target", {})
                    .get("process", {})
                    .get("file", {})
                    .get("full_path"),
                    self.raw_data.get("udmEvent", {})
                    .get("target", {})
                    .get("parent_process", {})
                    .get("file", {})
                    .get("full_path"),
                }
            )
            return [p for p in processes if p]

        @property
        def get_subjects_list(self):
            subject = (
                self.raw_data.get("udmEvent", {})
                .get("network", {})
                .get("email", {})
                .get("subject")
            )
            subjects = subject if isinstance(subject, list) else [subject]
            return [s for s in subjects if s]

        @property
        def get_emails_list(self):
            emails = (
                self.raw_data.get("udmEvent", {})
                .get("network", {})
                .get("email", {})
                .get("to", [])
                + self.raw_data.get("udmEvent", {})
                .get("network", {})
                .get("email", {})
                .get("cc", [])
                + self.raw_data.get("udmEvent", {})
                .get("network", {})
                .get("email", {})
                .get("bcc", [])
                + [
                    self.raw_data.get("udmEvent", {})
                    .get("network", {})
                    .get("email", {})
                    .get("from")
                ]
                + self.raw_data.get("udmEvent", {})
                .get("principal", {})
                .get("user", {})
                .get("emailAddresses", [])
                + self.raw_data.get("udmEvent", {})
                .get("src", {})
                .get("user", {})
                .get("emailAddresses", [])
                + self.raw_data.get("udmEvent", {})
                .get("target", {})
                .get("user", {})
                .get("emailAddresses", [])
            )

            return list(set([e for e in emails if e]))

        @property
        def get_users_list(self):
            users = list(
                {
                    self.raw_data.get("udmEvent", {})
                    .get("principal", {})
                    .get("user", {})
                    .get("user_display_name"),
                    self.raw_data.get("udmEvent", {})
                    .get("src", {})
                    .get("user", {})
                    .get("user_display_name"),
                    self.raw_data.get("udmEvent", {})
                    .get("target", {})
                    .get("user", {})
                    .get("user_display_name"),
                    self.raw_data.get("udmEvent", {})
                    .get("principal", {})
                    .get("user", {})
                    .get("userid"),
                    self.raw_data.get("udmEvent", {})
                    .get("src", {})
                    .get("user", {})
                    .get("userid"),
                    self.raw_data.get("udmEvent", {})
                    .get("target", {})
                    .get("user", {})
                    .get("userid"),
                }
            )
            return [u for u in users if u]

        @property
        def get_all_entities(self):
            entities = (
                self.get_users_list
                + self.get_emails_list
                + self.get_subjects_list
                + self.get_processes_list
                + self.get_hostnames_list
                + self.get_ips_list
                + self.get_hashes_list
                + self.get_urls_list
            )
            return [e.lower() for e in entities]

    def __init__(
        self,
        raw_data,
        hostname=None,
        ip_address=None,
        mac=None,
        alert_infos=None,
        **kwargs,
    ):
        self.raw_data = raw_data
        self.hostname = hostname
        self.ip_address = ip_address
        self.mac = mac
        self.alert_infos = alert_infos or []

    @property
    def hash_id(self):
        # Use the hash ids of the alert infos to create a unique info dict for the alert itself
        # and MD5 the json form of the dict
        temp_data = {
            "hostname": self.hostname,
            "alert_info_ids": [alert_info.hash_id for alert_info in self.alert_infos],
        }
        return hashlib.md5(
            json.dumps(temp_data, sort_keys=True).encode("utf8")
        ).hexdigest()

    @property
    def asset(self):
        return self.hostname or self.ip_address or self.mac

    @property
    def start_time(self):
        if not self.alert_infos:
            return 0

        sorted_alert_infos = sorted(
            self.alert_infos, key=lambda alert_info: alert_info.timestamp_ms
        )
        return sorted_alert_infos[0].timestamp_ms

    @property
    def end_time(self):
        if not self.alert_infos:
            return 0

        sorted_alert_infos = sorted(
            self.alert_infos, key=lambda alert_info: alert_info.timestamp_ms
        )
        return sorted_alert_infos[-1].timestamp_ms


class Detection:
    def __init__(
        self,
        raw_data: SingleJson,
        identifier: str,
        rule_id: str,
        alert_state: str,
        name: str,
        created_time: str,
        start_time: str,
        end_time: str,
        detections: list,
        collection_elements: list,
        rule_type: str,
        url_back_to_product: str,
        rule_labels: list[SingleJson],
        risk_score: int,
        data_access_scope: str,
        fallback_severity: str | None = None,
        outcomes: Outcomes = None,
        detection_depth: str | None = None,
    ):
        self.raw_data = raw_data
        self.uuid = str(uuid.uuid4())
        self._flat_raw_data = None
        self.id = identifier
        self.rule_id = rule_id
        self.alert_state = alert_state
        self.name = name
        self.created_time = created_time
        self.timestamp = convert_string_to_unix_time(created_time)
        self.start_time = start_time
        self.end_time = end_time
        self.detections = detections
        self.collection_elements = collection_elements
        self.fallback_severity = fallback_severity
        self.siemplify_severity = self.get_siemplify_severity or (
            consts.SIEMPLIFY_SEVERITIES.get(self.fallback_severity.lower())
            if self.fallback_severity
            else None
        )
        self.alert_main_type = consts.RULE_ALERT_TYPE
        self.rule_type = rule_type
        self.parsed_url_back_to_product = urlparse(url_back_to_product)
        self.risk_score = risk_score
        self.data_access_scope = data_access_scope
        self.rule_labels = rule_labels or []
        self.outcomes = outcomes or Outcomes([])
        self.detection_depth = detection_depth

    @property
    def flat_raw_data(self):
        """Lazily compute flattened raw data."""
        if self._flat_raw_data is None:
            self._flat_raw_data = dict_to_flat(self.raw_data)
        return self._flat_raw_data

    def __hash__(self) -> int:
        return hash(self.id)

    def as_unified_alert_info(
        self,
        alert_info: AlertInfo,
        environment_common: EnvironmentHandle,
        device_product_field: str,
    ) -> AlertInfo:
        """Generates unified alert information based on the current alert instance.

        Args:
            alert_info: The alert information object to be populated.
            environment_common: An object providing environment-related functionality.
            device_product_field: The field name for the device product information.

        Returns:
            AlertInfo: The populated alert information object.
        """
        alert_info.ticket_id = self.id
        alert_info.display_id = (
            f"{consts.RULE_ALERT_PREFIX}_{self.id}__{self.rule_type}"
        )
        alert_info.name = self.name
        alert_info.description = self.get_description()
        alert_info.device_vendor = consts.UNIFIED_CONNECTOR_DEVICE_VENDOR
        alert_info.priority = self.siemplify_severity
        alert_info.rule_generator = self.name
        alert_info.start_time = convert_string_to_unix_time(self.start_time)
        alert_info.end_time = convert_string_to_unix_time(self.end_time)
        alert_info.events = self.get_unified_events()
        alert_info.environment = environment_common.get_environment(
            alert_info.events[0] if alert_info.events else {}
        )
        alert_info.alert_metadata = {
            "DetectionDepth": self.detection_depth
        }
        alert_info.extensions = {
            "alert_type": (
                consts.RA_PRODUCT_NAME if self.get_risk_score_threshold()
                else consts.ALERT_TYPE_NAMES.get(
                    consts.ALERT_TYPES.get("rule")
                )
            ),
            "rule_id": self.rule_id,
            "product_name": self.get_product_name,
            "chronicle_alert_type": self.rule_type,
            "ui_base_link": self.parsed_url_back_to_product.scheme
            + "://"
            + self.parsed_url_back_to_product.netloc,
            "RiskScore": self.risk_score,
            "WindowStartTime": self.start_time,
            "WindowEndTime": self.end_time,
            "Severity": self.get_rule_severity(),
        }
        device_product_from_events = next(
            (
                event.get(device_product_field)
                for event in alert_info.events
                if event.get(device_product_field)
            ),
            None,
        )

        if device_product_field == consts.SCC_ENTERPRISE_PRODUCT_NAME:
            alert_info.device_product = consts.SCC_ENTERPRISE_PRODUCT_NAME
        elif self.get_risk_score_threshold():
            alert_info.device_product = consts.RA_PRODUCT_NAME
        elif device_product_from_events:
            alert_info.device_product = device_product_from_events
        else:
            alert_info.device_product = consts.UNIFIED_CONNECTOR_DEVICE_PRODUCT

        try:
            alert_info.source_system_url = (
                self.parsed_url_back_to_product.scheme
                + "://"
                + self.parsed_url_back_to_product.netloc
            )
            alert_info.source_rule_identifier = self.rule_id
            alert_info.siem_alert_id = self.id
            alert_info.data_access_scope = self.data_access_scope
            alert_info.alert_update_supported = self.outcomes.is_alert_update_supported
            alert_info.updated_fields = (
                self.outcomes.to_updated_fields()
                if self.outcomes.is_alert_update_supported else {}
            )
        except:
            warnings.warn(
                "One or more detection fields could not be mapped to SOAR alert fields"
            )

        return alert_info

    def get_risk_score_threshold(self):
        """Checks if risk score threshold is set for detection.

        Returns:
            str: If exists, the field value
        """
        for detection in self.detections:
            rule_labels = detection.get("ruleLabels", [{}])
            for rule_label in rule_labels:
                if rule_label.get("key") == "risk_score_threshold":
                    threshold = rule_label.get("value")
                    if threshold.casefold() != "false":
                        return threshold

        return ""

    def get_description(self):
        for detection in self.detections:
            rule_labels = detection.get("ruleLabels", [{}])
            for rule_label in rule_labels:
                if rule_label.get("key") == "description":
                    return rule_label.get("value")

        return ""

    def to_json(self):
        return self.raw_data

    @property
    def rule_class(self):
        return (
            "curated"
            if self.rule_id and utils.is_curated_rule_id(self.rule_id)
            else "custom"
        )

    @property
    def get_product_name(self):
        product_names = []

        for collection_element in self.collection_elements:
            for reference in collection_element.get("references", []):
                product_names.append(
                    reference.get("event", {}).get("metadata", {}).get("productName")
                )

        return (
            utils.convert_list_to_comma_string(
                [product_name for product_name in product_names if product_name]
            )
            or ""
        )

    @property
    def get_unique_product_name(self):
        product_names = set()

        for collection_element in self.collection_elements:
            for reference in collection_element.get("references", []):
                product_names.add(
                    reference.get("event", {}).get("metadata", {}).get("productName")
                )

        return (
            utils.convert_list_to_comma_string(
                [product_name for product_name in product_names if product_name]
            )
            or ""
        )

    @property
    def get_product_names_list(self):
        product_names = []

        for collection_element in self.collection_elements:
            for reference in collection_element.get("references", []):
                product_names.append(
                    reference.get("event", {}).get("metadata", {}).get("productName")
                )

        return product_names

    @property
    def get_siemplify_severity(self):
        # severity for GCTI type of alert
        sorted_detections = sorted(
            self.detections,
            key=lambda item: consts.GCTI_ALERT_SEVERITY_MAPPING.get(
                item.get("severity", ""), 0
            ),
            reverse=True,
        )

        if sorted_detections and sorted_detections[0].get("severity"):
            return consts.GCTI_ALERT_SEVERITY_MAPPING.get(
                sorted_detections[0].get("severity")
            )

        # severity for RULE type of alert
        severity_key = ""

        for detection in self.detections:
            rule_labels = detection.get("ruleLabels", [{}])
            for rule_label in rule_labels:
                if rule_label.get("key") == "severity":
                    severity_key = rule_label.get("value")
                    break
            try:
                severity_key = severity_key.lower()
            except:
                severity_key = None

        return consts.SIEMPLIFY_SEVERITIES.get(severity_key, None)

    def get_rule_severity(self):
        severities = [
            rule_label.get("value")
            for rule_label in self.rule_labels
            if rule_label.get("key", "").lower() == "severity"
        ]
        return severities[0] if severities and severities[0] else self.fallback_severity

    def get_unified_events(self):
        """Retrieves unified events from the given data.

        Returns:
            list:
                A list of unified events, where each event
                is represented as a dictionary.
        """

        alert_data_without_events = deepcopy(self.raw_data)
        references = []
        events = []
        related_detection_ids = []

        if alert_data_without_events.get("collectionElements"):
            del alert_data_without_events["collectionElements"]

        for collection_element in self.collection_elements:
            references.extend(collection_element.get("references", []))

        for reference in references:
            if "id" in reference and "stringId" in reference["id"]:
                related_detection_ids.append(reference["id"]["stringId"])
                continue

            event_raw_data = {**reference, **alert_data_without_events}
            emails = event_raw_data.get("event", {}).get("network", {}).get("email", {})

            if emails.get("to") or emails.get("cc") or emails.get("bcc"):
                emails["to"] = list(
                    dict.fromkeys(
                        emails.get("to", [])
                        + emails.get("cc", [])
                        + emails.get("bcc", [])
                    )
                )
                emails.pop("cc", None)
                emails.pop("bcc", None)

            additional_info = {
                "alert_type": (
                    consts.RA_PRODUCT_NAME if self.get_risk_score_threshold()
                    else consts.ALERT_TYPE_NAMES.get(
                        consts.ALERT_TYPES.get("rule")
                    )
                ),
                "event_type": event_raw_data.get("event", {}).get("metadata", {}).get("eventType") or
                              event_raw_data.get("entity", {}).get("metadata", {}).get("entityType"),
                "event_category": utils.get_prefix_from_string(
                    event_raw_data.get("event", {})
                    .get("metadata", {})
                    .get("eventType", "")
                )
                or utils.get_prefix_from_string(
                    event_raw_data.get("entity", {})
                    .get("metadata", {})
                    .get("entityType", "")
                ),
            }

            events.extend(
                utils.separate_data_per_multiple_values_keys(
                    event_raw_data,
                    consts.RULE_MULTIPLE_VALUES_NESTED_KEYS,
                    additional_info,
                )
            )
            if additional_info.get("event_type", "") == IP_ADDRESS_ENTITY_TYPE:
                ip_addresses = (
                    event_raw_data.get("entity", {}).get("entity", {}).get("ip", [])
                )
                for event in events:
                    event["event_aggr_target_ip"] = ", ".join(ip_addresses)

        if related_detection_ids:
            for event in events:
                event["relatedDetectionIds"] = ",".join(related_detection_ids)

        return [utils.fix_key_value_pair(dict_to_flat(event)) for event in events]

    @property
    def get_urls_list(self):
        urls = []

        for collection_element in self.collection_elements:
            for reference in collection_element.get("references", []):
                urls.append(reference.get("event", {}).get("target", {}).get("url"))

        return [u for u in urls if u]

    @property
    def get_hashes_list(self):
        hashes = []

        for collection_element in self.collection_elements:
            for reference in collection_element.get("references", []):
                hashes.append(
                    reference.get("event", {})
                    .get("target", {})
                    .get("file", {})
                    .get("md5")
                )
                hashes.append(
                    reference.get("event", {})
                    .get("target", {})
                    .get("file", {})
                    .get("sha1")
                )
                hashes.append(
                    reference.get("event", {})
                    .get("target", {})
                    .get("file", {})
                    .get("sha256")
                )

        return [h for h in hashes if h]

    @property
    def get_ips_list(self):
        ips = []

        for collection_element in self.collection_elements:
            for reference in collection_element.get("references", []):
                ips.extend(reference.get("event", {}).get("target", {}).get("ip", []))
                ips.extend(
                    reference.get("event", {})
                    .get("target", {})
                    .get("asset", {})
                    .get("ip", [])
                )
                ips.extend(reference.get("event", {}).get("src", {}).get("ip", []))
                ips.extend(
                    reference.get("event", {})
                    .get("src", {})
                    .get("asset", {})
                    .get("ip", [])
                )
                ips.extend(
                    reference.get("event", {}).get("principal", {}).get("ip", [])
                )
                ips.extend(
                    reference.get("event", {})
                    .get("principal", {})
                    .get("asset", {})
                    .get("ip", [])
                )

        return ips

    @property
    def get_hostnames_list(self):
        hostnames = []

        for collection_element in self.collection_elements:
            for reference in collection_element.get("references", []):
                hostnames.append(
                    reference.get("event", {}).get("target", {}).get("hostname")
                )
                hostnames.append(
                    reference.get("event", {})
                    .get("target", {})
                    .get("asset", {})
                    .get("hostname")
                )
                hostnames.append(
                    reference.get("event", {})
                    .get("principal", {})
                    .get("asset", {})
                    .get("hostname")
                )
                hostnames.append(
                    reference.get("event", {}).get("principal", {}).get("hostname")
                )
                hostnames.append(
                    reference.get("event", {}).get("src", {}).get("hostname")
                )

        return [h for h in hostnames if h]

    @property
    def get_processes_list(self):
        processes = []

        for collection_element in self.collection_elements:
            for reference in collection_element.get("references", []):
                processes.append(
                    reference.get("event", {})
                    .get("target", {})
                    .get("process", {})
                    .get("file", {})
                    .get("full_path")
                )
                processes.append(
                    reference.get("event", {})
                    .get("target", {})
                    .get("parent_process", {})
                    .get("file", {})
                    .get("full_path")
                )

        return [p for p in processes if p]

    @property
    def get_subjects_list(self):
        subjects = []

        for collection_element in self.collection_elements:
            for reference in collection_element.get("references", []):
                subject = (
                    reference.get("event", {})
                    .get("network", {})
                    .get("email", {})
                    .get("subject")
                )
                if isinstance(subject, list):
                    subjects.extend(subject)
                else:
                    subjects.append(subject)

        return [s for s in subjects if s]

    @property
    def get_emails_list(self):
        emails = []

        for collection_element in self.collection_elements:
            for reference in collection_element.get("references", []):
                emails.extend(
                    reference.get("event", {})
                    .get("network", {})
                    .get("email", {})
                    .get("to", [])
                )
                emails.extend(
                    reference.get("event", {})
                    .get("network", {})
                    .get("email", {})
                    .get("cc", [])
                )
                emails.extend(
                    reference.get("event", {})
                    .get("network", {})
                    .get("email", {})
                    .get("bcc", [])
                )
                emails.extend(
                    [
                        reference.get("event", {})
                        .get("network", {})
                        .get("email", {})
                        .get("from")
                    ]
                )
                emails.extend(
                    reference.get("event", {})
                    .get("principal", {})
                    .get("user", {})
                    .get("emailAddresses", [])
                )
                emails.extend(
                    reference.get("event", {})
                    .get("src", {})
                    .get("user", {})
                    .get("emailAddresses", [])
                )
                emails.extend(
                    reference.get("event", {})
                    .get("target", {})
                    .get("user", {})
                    .get("emailAddresses", [])
                )

        return [e for e in emails if e]

    @property
    def get_users_list(self):
        users = []

        for collection_element in self.collection_elements:
            for reference in collection_element.get("references", []):
                users.append(
                    reference.get("event", {})
                    .get("principal", {})
                    .get("user", {})
                    .get("user_display_name")
                )
                users.append(
                    reference.get("event", {})
                    .get("src", {})
                    .get("user", {})
                    .get("user_display_name")
                )
                users.append(
                    reference.get("event", {})
                    .get("target", {})
                    .get("user", {})
                    .get("user_display_name")
                )
                users.append(
                    reference.get("event", {})
                    .get("principal", {})
                    .get("user", {})
                    .get("userid")
                )
                users.append(
                    reference.get("event", {})
                    .get("src", {})
                    .get("user", {})
                    .get("userid")
                )
                users.append(
                    reference.get("event", {})
                    .get("target", {})
                    .get("user", {})
                    .get("userid")
                )

        return [u for u in users if u]

    @property
    def get_all_entities(self):
        entities = (
            self.get_users_list
            + self.get_emails_list
            + self.get_subjects_list
            + self.get_processes_list
            + self.get_hostnames_list
            + self.get_ips_list
            + self.get_hashes_list
            + self.get_urls_list
        )
        return [e.lower() for e in entities]

    @property
    def is_alert_update_supported(self):
        return self.outcomes.is_alert_update_supported


@dataclasses.dataclass(frozen=True)
class DetectionOutcome:
    raw_data: dict
    key: str
    value: str

    @classmethod
    def build_outcome_obj(cls, raw_outcome: dict) -> DetectionOutcome:
        """Creates a `DetectionOutcome` object from raw json outcome"""
        if not isinstance(raw_outcome, dict):
            raise DetectionParsingError(
                "Cannot build Detection Outcome object from unfamiliar data type: "
                f"{type(raw_outcome)}."
            )
        key = raw_outcome.get("key")
        value = raw_outcome.get("value")
        key = key if isinstance(key, str) else json.dumps(key, ensure_ascii=False)
        value = value if isinstance(value, str) else json.dumps(
            value, ensure_ascii=False)
        return cls(
            raw_data=raw_outcome,
            key=key,
            value=value
        )


@dataclasses.dataclass(slots=True)
class Outcomes:
    _outcomes: list[DetectionOutcome]
    _is_alert_update_supported: bool | None = None
    _n: int = 0

    @property
    def is_alert_update_supported(self) -> bool:
        """True if the alert support updates, False otherwise"""
        if self._is_alert_update_supported is None:
            self._is_alert_update_supported = False
            for outcome in self:
                if outcome.key == consts.OUTCOME_UPDATED_DETECTION_KEY:
                    self._is_alert_update_supported = outcome.value.lower() == "true"
                    break


        return self._is_alert_update_supported

    def keys(self):
        return [outcome.key for outcome in self._outcomes]

    def values(self):
        return [outcome.value for outcome in self._outcomes]

    def __getitem__(self, index):
        return self._outcomes[index]

    def __setitem__(self, index, value):
        self._outcomes[index] = value

    def __iter__(self):
        self._n = 0
        return self

    def __next__(self):
        if self._n >= len(self._outcomes):
            raise StopIteration()
        self._n += 1
        return self._outcomes[self._n - 1]

    def __len__(self):
        return len(self._outcomes)

    @classmethod
    def build_outcomes(cls, raw_outcomes: list[dict]):
        """Create an `Outcomes` object for all raw json outcomes provided"""
        if not isinstance(raw_outcomes, list):
            raise DetectionParsingError(
                "Cannot parse Detection's Outcomes!"
            )

        return cls(
            [DetectionOutcome.build_outcome_obj(outcome) for outcome in raw_outcomes]
        )

    def to_updated_fields(self):
        return {
            outcome.key: outcome.value for outcome in self
            if outcome.key != consts.OUTCOME_UPDATED_DETECTION_KEY
        }


class ChronicleCase:
    def __init__(
        self,
        raw_data,
        id=None,
        external_id=None,
        priority=None,
        status=None,
        environment=None,
        stage=None,
        has_failed=False,
        tracking_time=None,
        display_name=None,
    ):
        self.raw_data = raw_data
        self.id = id
        self.external_id = external_id if external_id != "None" else ""
        self.priority = priority
        self.status = status
        self.environment = environment
        self.stage = stage
        self.has_failed = has_failed
        self.tracking_time = tracking_time
        self.display_name = display_name


class ChronicleAlert:
    def __init__(
        self,
        raw_data,
        id=None,
        siem_alert_id=None,
        ticket_id=None,
        creation_time=None,
        priority=None,
        status=None,
        environment=None,
        comment=None,
        has_failed=False,
        tracking_time=None,
        reason=None,
        root_cause=None,
        case_id=None,
        group_id=None,
        usefulness=None,
    ):
        self.raw_data = raw_data
        self.id = id
        self.siem_alert_id = siem_alert_id
        self.ticket_id = ticket_id
        self.creation_time = creation_time
        self.priority = priority
        self.status = status
        self.environment = environment
        self.comment = comment
        self.has_failed = has_failed
        self.tracking_time = tracking_time
        self.reason = reason
        self.root_cause = root_cause
        self.case_id = case_id
        self.group_id = group_id
        self.usefulness = usefulness


class CaseMetadata:
    def __init__(self, raw_data, id=None, tracking_time=None):
        self.raw_data = raw_data
        self.id = id
        self.tracking_time = tracking_time


class AlertMetadata:
    def __init__(self, raw_data, group_id=None, tracking_time=None):
        self.raw_data = raw_data
        self.group_id = group_id
        self.tracking_time = tracking_time


class CaseData:
    def __init__(
            self,
            raw_data: list[SingleJson],
            getdata: list[RefDataObject]
    ) -> None:
        self.raw_data = raw_data
        self.getdata = getdata

    def get_data(self):
        return self.getdata

    def to_json(self):
        return [ref.to_json() for ref in self.getdata]


class RefDataObject:
    def __init__(
            self,
            raw_data: SingleJson,
            name: str,
            description: str,
    ):
        self.raw_data = raw_data
        self.name = name
        self.description = description
        self.content_type = raw_data.get("contentType", raw_data.get("syntaxType", ""))

    def to_csv(self):
        list_data = {
            "Name": self.name,
            "Description": self.description,
            "Type": self.content_type,
        }
        return list_data

    def to_json(self):
        """Convert to JSON object."""
        _json = copy.deepcopy(self.raw_data)
        _json.update({"description": self.description})
        if "entries" in _json:
            _json["lines"] = [
                value
                for e in _json.get("entries", [])
                if (value := e.get("value")) is not None
            ]
        if "createTime" not in _json:
            _json["createTime"] = _json.get("revisionCreateTime")

        return _json


class ActionDetails:
    def __init__(self, raw_data: dict):
        self.raw_data = raw_data

    def to_json(self):
        return self.raw_data


class Rule:
    def __init__(self, raw_data: dict):
        self.raw_data = raw_data

    @property
    def rule_id(self) -> str:
        return self.raw_data.get("ruleId") or self.raw_data.get("name").split("/")[-1]

    @property
    def version_id(self) -> str:
        return (
            self.raw_data.get("versionId")
            or f"{self.rule_id}@{self.raw_data['revisionId']}"
        )

    @property
    def rule_name(self) -> str:
        return self.raw_data.get("ruleName") or self.raw_data.get("displayName")

    @property
    def rule_text(self) -> str:
        return self.raw_data.get("ruleText") or self.raw_data.get("text")

    @property
    def rule_type(self) -> str:
        return self.raw_data.get("ruleType") or self.raw_data.get("type")

    @property
    def metadata(self) -> SingleJson:
        """Metadata Rule property."""
        meta_data = self.raw_data.get("metadata", {})
        if  meta_data.get("author") is None:
            meta_data["author"] = self.raw_data.get("author")
        if meta_data.get("description") is None:
            meta_data["description"] = self.raw_data.get("description")
        if meta_data.get("severity") is None:
            meta_data["severity"] = self.raw_data.get("severity", {}).get("displayName")
        return meta_data

    @property
    def version_create_time(self) -> str:
        return (
            self.raw_data.get("versionCreateTime")
            or self.raw_data.get("revisionCreateTime")
        )

    def to_json(self):
        """Convert to JSON object."""
        _json = copy.deepcopy(self.raw_data)
        _json.update({
            "ruleId": self.rule_id,
            "versionId": self.version_id,
            "ruleName": self.rule_name,
            "metadata": self.metadata,
            "ruleText": self.rule_text,
            "ruleType": self.rule_type,
            "versionCreateTime": self.version_create_time,
        })
        return _json


@dataclass(slots=True)
class CuratedRule:
    """
    Data model for a Curated Rule.
    """
    raw_data: SingleJson

    def to_json(self) -> SingleJson:
        """
        Serializes the object to its raw JSON representation.
        """
        return self.raw_data


class SiemEvent:
    """Chronicle SIEM DTO represents a SOAR event. Used
    for creating the event in Chronicle."""

    def __init__(
        self,
        raw_data,
        event_id,
        start_time,
        end_time,
        event_time,
        receipt_time,
        manager_receipt_time,
        event_message,
        event_description,
        source_user,
        source_host,
        source_domain,
        source_ip_address,
        source_mac_address,
        source_user_id,
        source_process_pid,
        source_dns_domain,
        source_nt_domain,
        destination_user,
        destination_domain,
        destination_host,
        destination_dns_domain,
        destination_nt_domain,
        destination_port,
        destination_ip_address,
        destination_process_pid,
        destination_uri,
        destination_mac_address,
        generic_entity,
        phone_number,
        email_subject,
        cve,
        threat_actor,
        threat_campaign,
        threat_signature,
        category_outcome,
        deployment,
        transport_protocol,
        application_protocol,
        process_pid,
        parent_process_pid,
        rule_generator,
        file,
        file_hash,
        file_type,
        vendor,
        product,
        usb,
    ):
        self.raw_data = raw_data
        self.event_id = event_id
        self.start_time = start_time
        self.end_time = end_time
        self.event_time = event_time
        self.receipt_time = receipt_time
        self.manager_receipt_time = manager_receipt_time
        self.event_message = event_message
        self.event_description = event_description
        self.source_user = source_user
        self.source_host = source_host
        self.source_domain = source_domain
        self.source_ip_address = source_ip_address
        self.source_mac_address = source_mac_address
        self.source_user_id = source_user_id
        self.source_process_pid = source_process_pid
        self.source_dns_domain = source_dns_domain
        self.source_nt_domain = source_nt_domain
        self.destination_user = destination_user
        self.destination_domain = destination_domain
        self.destination_host = destination_host
        self.destination_dns_domain = destination_dns_domain
        self.destination_nt_domain = destination_nt_domain
        self.destination_port = destination_port
        self.destination_ip_address = destination_ip_address
        self.destination_process_pid = destination_process_pid
        self.destination_uri = destination_uri
        self.destination_mac_address = destination_mac_address
        self.generic_entity = generic_entity
        self.phone_number = phone_number
        self.email_subject = email_subject
        self.cve = cve
        self.threat_actor = threat_actor
        self.threat_campaign = threat_campaign
        self.threat_signature = threat_signature
        self.category_outcome = category_outcome
        self.deployment = deployment
        self.transport_protocol = transport_protocol
        self.application_protocol = application_protocol
        self.process_pid = process_pid
        self.parent_process_pid = parent_process_pid
        self.rule_generator = rule_generator
        self.file = file
        self.file_hash = file_hash
        self.file_type = file_type
        self.vendor = vendor
        self.product = product
        self.usb = usb


class SiemAlert:
    """Chronicle SIEM DTO represents a new SOAR alert. Used
    for creating the new alert in Chronicle."""

    def __init__(
        self,
        raw_data,
        soar_alert_id,
        start_time,
        end_time,
        detection_time,
        source_system_uri,
        vendor,
        source_system,
        product,
        original_ticket_id,
        events,
        description,
        summary,
        alert_group_id,
        soar_create_time,
        environment,
        has_failed=False,
        error_message=None,
        siem_alert_id=None,
    ):
        self.raw_data = raw_data
        self.soar_alert_id = soar_alert_id
        self.start_time = start_time
        self.end_time = end_time
        self.detection_time = detection_time
        self.source_system_uri = source_system_uri
        self.vendor = vendor
        self.source_system = source_system
        self.product = product
        self.original_ticket_id = original_ticket_id
        self.events = events
        self.description = description
        self.summary = summary
        self.alert_group_id = alert_group_id
        self.soar_create_time = soar_create_time
        self.environment = environment
        self.has_failed = has_failed
        self.error_message = error_message
        self.siem_alert_id = siem_alert_id


class NewAlertSyncResult:
    """SOAR DTO represents synchronization result of a new alert
    with Chronicle SIEM.
    """

    def __init__(
        self,
        alert_group_identifier,
        environment,
        creation_time,
        created_in_siem,
        siem_alert_id=None,
        message=None,
        updated_in_soar=None,
    ):
        self.alert_group_identifier = alert_group_identifier
        self.environment = environment
        self.creation_time = creation_time
        self.created_in_siem = created_in_siem
        self.siem_alert_id = siem_alert_id
        self.message = message
        self.updated_in_soar = updated_in_soar


class MultipartResponsePart:
    def __init__(self, body, headers, status_code, encoding="utf-8"):
        self._body = body
        self._headers = headers
        self._status_code = status_code
        self._encoding = encoding

    @property
    def content(self) -> bytes:
        return self._body

    @property
    def text(self) -> str:
        return self._body.decode(self._encoding)

    @property
    def headers(self) -> dict:
        return self._headers

    @property
    def status_code(self) -> int:
        return self._status_code

    @property
    def encoding(self) -> str:
        return self._encoding

    def json(self):
        return json.loads(self._body)


class UdmQueryEvent:
    def __init__(self, raw_data):
        self.raw_data = raw_data

    def to_json(self):
        return self.raw_data


class ReferenceList:
    """Defines the structure for a ReferenceList"""

    def __init__(
        self,
        raw_data: dict,
        name: str,
        description: str,
        lines: list[str],
    ) -> None:
        self.raw_data = raw_data
        self.name = name
        self.description = description
        self.create_time = (
            raw_data.get("createTime", raw_data.get("revisionCreateTime", ""))
        )
        self.lines = lines
        self.content_type = raw_data.get("contentType", raw_data.get("syntaxType", ""))

    def to_json(self):
        """Convert to JSON object."""
        _json = copy.deepcopy(self.raw_data)
        _json.update({
            "description": self.description,
            "createTime": self.create_time,
            "lines": self.lines
        })
        return _json


class RetrohuntObject:
    """Defines the structure for a Retrohunt"""

    def __init__(self, raw_data: dict) -> None:
        self.raw_data = raw_data

    def to_json(self) -> SingleJson:
        """Convert Retrohunt object to JSON object"""
        data = copy.deepcopy(self.raw_data)
        metadata = self.raw_data.get("metadata", {})
        execution_interval = metadata.get("executionInterval", {})
        extracted_retrohunt_dict = utils.extract_dict_from_resource_string(
            metadata.get("retrohunt", "")
        )

        data.update({
            "retrohuntId": extracted_retrohunt_dict.get("retrohunts"),
            "ruleId": extracted_retrohunt_dict.get("rules", "").split("@")[0],
            "versionId": extracted_retrohunt_dict.get("rules"),
            "eventStartTime": execution_interval.get("startTime"),
            "eventEndTime": execution_interval.get("endTime"),
        })

        return data


@dataclasses.dataclass(slots=True)
class DataTableModel:
    """
    A base dataclass for common attributes and methods,
    like storing raw JSON data and converting back to JSON.
    """
    raw_data: SingleJson

    def to_json(self) -> SingleJson:
        """
        Converts the object back to its original raw JSON dictionary.
        """
        return self.raw_data


@dataclasses.dataclass(slots=True)
class DataTableColumnInfo(DataTableModel):
    """
    Represents a single column's metadata from a Chronicle Data Table.
    """
    original_column_name: str | None = None

    @classmethod
    def from_json(cls, json_data: SingleJson) -> DataTableColumnInfo:
        return cls(
            raw_data=json_data, original_column_name=json_data.get("originalColumn")
        )


@dataclasses.dataclass(slots=True)
class DataTableInfo(DataTableModel):
    """
    Represents the detailed structure of a Chronicle Data Table.
    """

    name: str | None = None
    column_info: list[DataTableColumnInfo] = dataclasses.field(default_factory=list)

    @classmethod
    def from_json(cls, json_data: SingleJson) -> DataTableInfo:
        return cls(
            raw_data=json_data,
            name=json_data.get("name"),
            column_info=[
                DataTableColumnInfo.from_json(col_info)
                for col_info in json_data.get("columnInfo", [])
            ],
        )

    @property
    def ordered_column_names(self) -> list[str]:
        """
        Returns a list of original column names in the order they appear.
        """
        return [
            col.original_column_name
            for col in self.column_info
            if col.original_column_name is not None
        ]


@dataclasses.dataclass(slots=True)
class AddedDataTableRow(DataTableModel):
    """
    Represents a single row that was successfully added to a Chronicle Data Table.
    """
    name: str | None = None
    values: list[str] = dataclasses.field(default_factory=list)

    @classmethod
    def from_json(cls, json_data: SingleJson) -> AddedDataTableRow:
        return cls(
            raw_data=json_data,
            name=json_data.get("name"),
            values=json_data.get("values", []),
        )


@dataclasses.dataclass(slots=True)
class RemovedDataTableRow(DataTableModel):
    name: str | None = None
    values: SingleJson = dataclasses.field(default_factory=dict)
    create_time: str = ""
    update_time: str = ""

    @classmethod
    def from_json(cls, json_data: SingleJson) -> RemovedDataTableRow:
        return cls(
            raw_data=json_data,
            name=json_data.get("name"),
            values=json_data.get("values", {}),
            create_time=json_data.get("createTime", ""),
            update_time=json_data.get("updateTime", "")
        )


@dataclasses.dataclass(slots=True)
class DataTableDetails(DataTableModel):
    name: str | None = None
    display_name: str | None = None
    description: str | None = None
    column_info: list[DataTableColumnInfo] = dataclasses.field(default_factory=list)
    rows: list[RemovedDataTableRow] = dataclasses.field(default_factory=list)

    @classmethod
    def from_json(cls, json_data: SingleJson) -> DataTableDetails:
        """ Create a DataTableDetails instance from a JSON object."""
        column_info = [
            DataTableColumnInfo.from_json(col_info)
            for col_info in json_data.get("columnInfo", [])
        ]
        data_table_rows = json_data.get("rows", json_data.get("dataTableRows", []))
        rows = [RemovedDataTableRow.from_json(row_data) for row_data in data_table_rows]
        if not isinstance(rows, list):
            rows = []
        return cls(
            raw_data=json_data,
            name=json_data.get("name"),
            display_name=json_data.get("displayName", ""),
            description=json_data.get("description", ""),
            column_info=column_info,
            rows = rows
        )

    def to_json(self) -> SingleJson:
        """Converts the DataTableDetails object to a JSON-compatible dictionary."""
        json_output = self.raw_data.copy()
        if self.rows:
            json_output["rows"] = [row.to_json() for row in self.rows]
        return json_output

    @property
    def ordered_column_names(self) -> list[str]:
        """
        Returns a list of original column names in the order they appear.
        """
        return [
            col.original_column_name
            for col in self.column_info
            if col.original_column_name is not None
        ]


class GeminiResponse:
    def __init__(self, raw_data: SingleJson) -> None:
        self.raw_data = raw_data

    def to_json(self) -> SingleJson:
        """Convert GeminiResponse object to JSON object"""
        data = copy.deepcopy(self.raw_data)
        if not isinstance(data, dict):
            return data
        if "responses" in data and isinstance(data["responses"], list):
            for response in data["responses"]:
                if "blocks" in response and isinstance(response["blocks"], list):
                    for block in response["blocks"]:
                        if "debugInfo" in block:
                            block.pop("debugInfo", None)
                response.setdefault("references", None)
                response.setdefault("groundings", None)
                response.setdefault("suggestedActions", None)

        return data


@dataclasses.dataclass(slots=True)
class EntitySummary:
    """
    Represents a summary of an entity from summarizeEntitiesFromQuery.
    """
    raw_data: SingleJson
    name: str
    namespace: str | None
    metadata: SingleJson | None

    @classmethod
    def from_json(cls, json_data: SingleJson) -> "EntitySummary":
        """
        Builds an EntitySummary object from raw JSON data.
        """
        return cls(
            raw_data=json_data,
            name=json_data.get("name", ""),
            namespace=json_data.get("entity", {}).get("namespace"),
            metadata=json_data.get("metadata")
        )

    def to_json(self) -> SingleJson:
        return self.raw_data


@dataclasses.dataclass(slots=True)
class DetailedEntitySummary:
    """
    Represents a comprehensive summary of an entity from summarizeEntity.
    """
    raw_data: SingleJson
    name: str | None
    metadata: SingleJson | None
    entity_details: SingleJson | None
    metric: SingleJson | None
    alert_counts: list[SingleJson] | None
    timeline: SingleJson | None
    prevalence_result: SingleJson | None

    @classmethod
    def from_json(
        cls,
        combined_api_data: SingleJson,
        initial_summary_info: SingleJson | None = None,
    ) -> "DetailedEntitySummary":
        """Builds a DetailedEntitySummary object from combined API response data.

        Args:
            combined_api_data: The raw JSON response from the API containing the
                detailed entity summary.
            initial_summary_info: An optional dictionary containing initial
                summary information like name and metadata.

        Returns:
            An instance of the DetailedEntitySummary class.
        """
        data = combined_api_data.copy()
        entity_details = data.get("entity")

        if isinstance(data.get("entities"), list) and data.get("entities"):
            entity_details = data.pop("entities")[0]
            for k, v in entity_details.items():
                data.setdefault(k, v)

        if initial_summary_info:
            data["name"] = initial_summary_info.get("name")
            data["metadata"] = initial_summary_info.get("metadata")

        return cls(
            raw_data=combined_api_data,
            name=data.get("name"),
            metadata=data.get("metadata"),
            entity_details=entity_details,
            metric=data.get("metric"),
            alert_counts=data.get("alertCounts"),
            timeline=data.get("timeline"),
            prevalence_result=data.get("prevalenceResult")
        )

    def to_json(self) -> SingleJson:
        """Converts the DetailedEntitySummary object back to a JSON dictionary.

        This is useful for creating a clean representation for output.
        """
        output = {
            "entity": self.entity_details,
            "metric": self.metric,
            "alertCounts": self.alert_counts,
            "timeline": self.timeline,
            "prevalenceResult": self.prevalence_result,
            "name": self.name,
            "metadata": self.metadata,
        }

        return {k: v for k, v in output.items() if v}


@dataclasses.dataclass(slots=True)
class RelatedEntitiesResponse:
    """
    Represents the response from findRelatedEntities.
    """
    raw_data: SingleJson
    related_entities: list[SingleJson]

    @classmethod
    def from_json(cls, json_data: SingleJson) -> "RelatedEntitiesResponse":

        return cls(
            raw_data=json_data,
            related_entities=json_data.get("relatedEntities", [])
        )

    def to_json(self) -> SingleJson:

        return self.raw_data


@dataclasses.dataclass(slots=True)
class Watchlist:
    raw_data: SingleJson
    watchlist_id: str
    display_name: str
    multiplying_factor: int
    entity_population_mechanism: SingleJson
    entity_count: SingleJson
    create_time: str
    update_time: str
    user_preferences: SingleJson

    @classmethod
    def from_json(cls, json_data: SingleJson) -> Self:
        return cls(
            raw_data=json_data,
            watchlist_id=json_data["name"].split("/")[-1],
            display_name=json_data.get("displayName"),
            multiplying_factor=json_data.get("multiplyingFactor", 1),
            entity_population_mechanism=json_data.get("entityPopulationMechanism"),
            entity_count=json_data.get("entityCount"),
            create_time=json_data.get("createTime"),
            update_time=json_data.get("updateTime"),
            user_preferences=json_data.get("watchlistUserPreferences"),
        )

    def to_json(self) -> SingleJson:
        return self.raw_data


@dataclasses.dataclass(slots=True)
class WatchlistEntity:
    name: str
    entity: SingleJson

    @classmethod
    def from_json(cls, data: SingleJson) -> Self:
        return cls(
            name=data["name"],
            entity=data["entity"]
        )

    def to_json(self) -> SingleJson:
        return self.entity


@dataclasses.dataclass(slots=True)
class RawLog:
    raw_data: SingleJson
    event_id: str
    log_bytes_b64: str

    @classmethod
    def from_json(cls, json_data: SingleJson) -> Self:
        return cls(
            raw_data=json_data,
            event_id=json_data.get("eventId", ""),
            log_bytes_b64=json_data.get("logBytes", "")
        )

    def to_json(self) -> SingleJson:
        return self.raw_data

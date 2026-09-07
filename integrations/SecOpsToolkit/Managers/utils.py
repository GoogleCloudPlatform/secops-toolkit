from __future__ import annotations

from typing import Any, Optional

import base64
import copy
import datetime
import hashlib
from io import BytesIO
import json
import operator
import re
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from dateutil.relativedelta import relativedelta

import consts
import exceptions
from SiemplifyAction import SiemplifyAction
from SiemplifyDataModel import SecurityEventInfo
from SiemplifyUtils import (
    convert_datetime_to_unix_time,
    convert_string_to_datetime,
    convert_string_to_unix_time,
    convert_unixtime_to_datetime,
    unix_now,
    utc_now,
)
from TIPCommon.base.interfaces import ScriptLogger
from TIPCommon.filters import filter_old_alerts
from TIPCommon.smp_io import read_content, write_content
from TIPCommon.transformation import dict_to_flat
from TIPCommon.types import ChronicleSOAR, SingleJson
from TIPCommon.utils import get_function_arg_names, is_empty_string_or_none
from exceptions import GoogleChronicleValidationError, InvalidTimeException

# Move to TIPCommon
UNIX_FORMAT = 1
DATETIME_FORMAT = 2
VALID_EMAIL_REGEXP = "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
TIMESTAMP_KEY = "timestamp"
NUM_OF_MILLI_IN_SEC = 1000


OPERATOR_FUNCTIONS = {
    "=": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
}


# Move to TIPCommon
def get_first_event_data(chronicle_soar: SiemplifyAction) -> SecurityEventInfo:
    """Get the additional data of an event of an alert of the current case

    Args:
        chronicle_soar (SiemplifyAction): SDK object

    Returns:
        SingleJson: Additional data dict of the event
    """
    return next(
        iter(getattr(chronicle_soar.current_alert, "security_events", [])), None
    )


def is_curated_rule_id(rule_id: str) -> bool:
    """Check whether a rule ID is a curated rule ID

    Args:
        rule_id: The rule ID to check

    Returns:
        bool: True if it is a curated rule ID else False
    """
    return rule_id.startswith(consts.CURATED_RULE_ID_PREFIX)


def datetime_to_rfc3339(datetime_obj: datetime.datetime) -> str:
    """
    Convert datetime object to RFC 3999 representation
    :param datetime_obj: {datetime.datetime} The datetime object to convert
    :return: {str} The RFC 3999 representation of the datetime
    """
    utc_offset = datetime_obj.utcoffset()
    if utc_offset:
        datetime_obj_utc = datetime_obj.astimezone(datetime.timezone.utc)
        return datetime_obj_utc.strftime(consts.TIME_FORMAT)

    return datetime_obj.strftime(consts.TIME_FORMAT)


# Move to TIPCommon
def get_last_success_time(
    siemplify: ChronicleSOAR,
    offset_with_metric: dict[str, int],
    time_format: int = DATETIME_FORMAT,
    print_value: bool = True,
    timestamp_file_name: str | None = None,
    timestamp_db_key: str | None = None,
) -> int | datetime.datetime:
    """Get last success time datetime.

    Args:
        siemplify: {ChronicleSOAR} Siemplify object
        offset_with_metric: {dict} metric and value. Ex {'hours': 1}
        time_format: {int} The format of the output time. Ex DATETIME, UNIX
        print_value: {bool} Whether log the value or not
        timestamp_file_name: {str} The name of the timestamp file
        timestamp_db_key: {str} The key to use for timestamp file

    Returns:
        {time} If first run, return current time minus offset time, else
            return timestamp from file
    """
    last_run_timestamp = (
        fetch_timestamp_by_timestamp_file(
            siemplify, timestamp_file_name, timestamp_db_key, datetime_format=True
        )
        if timestamp_file_name
        else siemplify.fetch_timestamp(datetime_format=True)
    )

    offset = datetime.timedelta(**offset_with_metric)
    current_time = utc_now()
    datetime_result = last_run_timestamp

    # Check if first run
    if current_time - last_run_timestamp > offset:
        datetime_result = current_time - offset
        siemplify.LOGGER.info(
            f"Last run time {last_run_timestamp} is outside of 'Max Hours Backwards'"
            f" range. Connector will replace it with calculated time {datetime_result}."
        )

    unix_result = convert_datetime_to_unix_time(datetime_result)
    if print_value:
        siemplify.LOGGER.info(
            f"Last success time. Date time:{datetime_result}. Unix:{unix_result}"
        )
    return unix_result if time_format == UNIX_FORMAT else datetime_result


def filter_old_detections(
    chronicle_soar: ChronicleSOAR,
    detections: list,
    existing_ids: list[str],
    id_key: str = "alert_id",
) -> list:
    """Filters detections that were already processed and are not possible updates.

    Args:
        chronicle_soar (ChronicleSOAR): Chronicle SOAR SDK instance.
        detections (list[Detection]): list of `Detection` objects to filter.
        existing_ids (list[str]): list of detction ids to filter against.
        id_key (str): The key used for identifier in the alerts (default: 'alert_id').

    Returns:
        list[Detection]: The filtered detections.
    """
    detections_to_update = [
        alert for alert in detections if alert.is_alert_update_supported
    ]
    detections_to_filter = [
        alert for alert in detections if not alert.is_alert_update_supported
    ]
    filtered_detections = filter_old_alerts(
        chronicle_soar, detections_to_filter, existing_ids, id_key
    )
    return filtered_detections + detections_to_update


# Move to TIPCommon
def is_approaching_timeout(
    python_process_timeout, connector_starting_time, timeout_threshold=0.9
):
    """
    Check if a timeout is approaching.
    :param python_process_timeout: {int} The python process timeout
    :return: {bool} True if timeout is close, False otherwise
    """
    processing_time_ms = unix_now() - connector_starting_time
    return processing_time_ms > python_process_timeout * 1000 * timeout_threshold


def is_high_duplicate_ratio(total_scanned: int, duplicates: int) -> bool:
    """Checks if the percentage of duplicates in the scanned alerts exceeds the safety threshold.

    Args:
        total_scanned: Total number of scanned alerts.
        duplicates: Number of duplicates found in the scanned alerts.

    Returns:
        bool: True if duplication ratio exceeds the threshold and total_scanned is high enough, False otherwise.
    """
    if total_scanned < consts.UNIFIED_CONNECTOR_DUPLICATE_MIN_SCANNED:
        return False
    return (
        duplicates / total_scanned
    ) > consts.UNIFIED_CONNECTOR_DUPLICATE_RATIO_THRESHOLD


def get_hash_type(file_hash: str) -> str:
    """
    Get the type of a hash by its length
    :param file_hash: {str} The hash
    :return: {str} The type of the hash
    """
    if len(file_hash) == 32:
        return consts.HashArtifactTypes.MD5
    elif len(file_hash) == 64:
        return consts.HashArtifactTypes.SHA256
    elif len(file_hash) == 40:
        return consts.HashArtifactTypes.SHA1

    raise exceptions.GoogleChronicleValidationError(
        "Invalid hash type. Supported types: MD5, SHA1, SHA256."
    )


def get_timestamps_from_range(range_string, alert_start_time=None, alert_end_time=None):
    """
    Get start and end time timestamps from range
    :param range_string: {str} Time range string
    :param alert_start_time: {str} Start time of the alert
    :param alert_end_time: {str} End time of the alert
    :return: {tuple} start and end time timestamps
    """
    now = datetime.datetime.utcnow()
    timeframe = consts.TIMEFRAME_MAPPING.get(range_string)

    if isinstance(timeframe, dict):
        start_time, end_time = now - datetime.timedelta(**timeframe), now
    elif timeframe == consts.TIMEFRAME_MAPPING.get("Last Week"):
        start_time, end_time = now - datetime.timedelta(weeks=1), now
    elif timeframe == consts.TIMEFRAME_MAPPING.get("Last Month"):
        start_time, end_time = now - relativedelta(months=1), now
    elif timeframe == consts.TIMEFRAME_MAPPING.get("Alert Time Till Now"):
        start_time, end_time = alert_start_time, now
    elif timeframe == consts.TIMEFRAME_MAPPING.get("5 Minutes Around Alert Time"):
        start_time, end_time = (
            alert_start_time - datetime.timedelta(minutes=5),
            alert_end_time + datetime.timedelta(minutes=5),
        )
    elif timeframe == consts.TIMEFRAME_MAPPING.get("30 Minutes Around Alert Time"):
        start_time, end_time = (
            alert_start_time - datetime.timedelta(minutes=30),
            alert_end_time + datetime.timedelta(minutes=30),
        )
    elif timeframe == consts.TIMEFRAME_MAPPING.get("1 Hour Around Alert Time"):
        start_time, end_time = (
            alert_start_time - datetime.timedelta(hours=1),
            alert_end_time + datetime.timedelta(hours=1),
        )
    else:
        return None, None

    return datetime_to_rfc3339(start_time), datetime_to_rfc3339(end_time)


def get_timestamps(
    range_string,
    start_time_string=None,
    end_time_string=None,
    alert_start_time=None,
    alert_end_time=None,
):
    """
    Get start and end time timestamps
    :param range_string: {str} Time range string
    :param start_time_string: {str} Start time
    :param end_time_string: {str} End time
    :param alert_start_time: {str} Start time of the alert
    :param alert_end_time: {str} End time of the alert
    :return: {tuple} start and end time timestamps
    """
    start_time, end_time = get_timestamps_from_range(
        range_string, alert_start_time, alert_end_time
    )
    current_time_rfc3339 = datetime_to_rfc3339(datetime.datetime.utcnow())
    try:
        if not start_time and start_time_string:
            start_time = datetime_to_rfc3339(
                convert_string_to_datetime(start_time_string)
            )
    except Exception as err:
        raise InvalidTimeException("Invalid start date/time format provided.")
    try:
        if not end_time and end_time_string:
            if end_time_string.lower() == consts.NOW:
                end_time = current_time_rfc3339
            else:
                end_time = datetime_to_rfc3339(
                    convert_string_to_datetime(end_time_string)
                )
    except Exception as err:
        raise InvalidTimeException("Invalid end date/time format provided.")

    if not start_time:
        raise InvalidTimeException(
            '"Start Time" should be provided, when "Custom" is selected '
            'in "Time Frame" parameter.'
        )

    if not end_time:
        end_time = create_end_time(
            start_time_string=start_time_string,
            current_time_rfc3339=current_time_rfc3339,
        )

    if start_time > end_time:
        raise Exception('"End Time" should be later than "Start Time"')

    return start_time, end_time


def create_end_time(start_time_string: str, current_time_rfc3339: str) -> str:
    """Determines the end time based on the provided start time and current time.

    Args:
        start_time_string (str): The start time in a string format.
        current_time_rfc3339 (str): The current time in RFC 3339 format.

    Returns:
        str: The end time in RFC 3339 format.
    """
    start_time_obj = convert_string_to_datetime(start_time_string)
    utc_offset = start_time_obj.utcoffset()
    if utc_offset:
        tzinfo = datetime.timezone(utc_offset)
        return datetime_to_rfc3339(datetime.datetime.utcnow().replace(tzinfo=tzinfo))

    return current_time_rfc3339


def convert_comma_separated_to_list(comma_separated):
    """
    Convert comma-separated string to list
    :param comma_separated: String with comma-separated values
    :return: List of values
    """
    return (
        [item.strip() for item in comma_separated.split(",")] if comma_separated else []
    )


def convert_list_to_comma_string(values_list):
    """
    Convert list to comma-separated string
    :param values_list: List of values
    :return: String with comma-separated values
    """
    return (
        ", ".join(str(v) for v in values_list)
        if values_list and isinstance(values_list, list)
        else values_list
    )


def is_valid_email(user_name):
    """
    Check if the user_name is valid email.
    :param user_name: {str} User name
    :return: {bool} True if valid email, else False
    """
    return bool(re.search(VALID_EMAIL_REGEXP, user_name))


def get_entity_original_identifier(entity):
    """
    Helper function for getting entity original identifier
    :param entity: entity from which function will get original identifier
    :return: {str} original identifier
    """
    return entity.additional_properties.get("OriginalIdentifier", entity.identifier)


def get_domain_from_entity(identifier):
    """
    Extract domain from entity identifier
    :param identifier: {str} the identifier of the entity
    :return: {str} domain part from entity identifier
    """
    if "@" in identifier:
        return identifier.split("@", 1)[-1]
    try:
        import tldextract

        result = tldextract.extract(identifier)
        join_with = "."
        result_to_join = [
            item for item in [result.subdomain, result.domain, result.suffix] if item
        ]
        return join_with.join(result_to_join)

    except ImportError:
        raise ImportError("tldextract is not installed. Use pip and install it.")


def save_timestamp_by_timestamp_file(
    siemplify,
    alerts,
    timestamp_key="timestamp",
    incrementation_value=0,
    log_timestamp=True,
    timestamp_file_name="timestamp.stmp",
    timestamp_db_key="timestamp",
    fetched_alerts_count=0,
):
    """
    Save last timestamp for given alerts
    :param siemplify: {Siemplify} Siemplify object
    :param alerts: {list} The list of alerts to find the last timestamp
    :param timestamp_key: {str} key for getting timestamp from alert
    :param incrementation_value: {int} The value to increment last timestamp by
    milliseconds
    :param log_timestamp: {bool} Whether log timestamp or not
    :param timestamp_file_name: {str} The name of the timestamp file
    :param timestamp_db_key: {str} The key to use for timestamp file
    :param fetched_alerts_count: {int} total number of alerts that were fetched from API
    :return: {bool} Is timestamp updated
    """
    if not alerts:
        siemplify.LOGGER.info("Timestamp is not updated since no alerts fetched")
        return False

    last_alert = max(alerts, key=lambda alert: int(getattr(alert, timestamp_key)))

    if fetched_alerts_count > 0 and len(alerts) < fetched_alerts_count:
        # Partial processing detected (timeout occurred)
        # We save the last timestamp without incrementation to ensure we resume from it.
        last_timestamp = int(getattr(last_alert, timestamp_key))
        siemplify.LOGGER.info(
            f"Partial processing detected ({len(alerts)}/{fetched_alerts_count}). "
            f"Saving last processed timestamp without incrementation: {last_timestamp}"
        )
    else:
        last_timestamp = int(getattr(last_alert, timestamp_key)) + incrementation_value

    try:
        write_content(
            siemplify,
            str(last_timestamp),
            file_name=timestamp_file_name,
            db_key=timestamp_db_key,
        )

        if log_timestamp:
            siemplify.LOGGER.info(f"Saving timestamp:{last_timestamp}")

        return True

    except Exception as e:
        siemplify.LOGGER.error(
            f"Failed writing timestamp to {timestamp_file_name} file, ERROR: {e}"
        )
        siemplify.LOGGER.exception(e)
        return False


def fetch_timestamp_by_timestamp_file(
    siemplify,
    timestamp_file_name="timestamp.stmp",
    timestamp_db_key="timestamp",
    datetime_format=True,
):
    """
    Fetch timestamp from timestamp file
    :param siemplify: {Siemplify} Siemplify object
    :param timestamp_file_name: {str} The name of the timestamp file
    :param timestamp_db_key: {str} The key to use for timestamp file
    :param datetime_format: {bool} Specifies if datetime format should be returned
    return: {timestamp}
    """
    try:
        last_run_time = read_content(
            siemplify,
            file_name=timestamp_file_name,
            db_key=timestamp_db_key,
            default_value_to_return=0,
        )
    except Exception:
        siemplify.LOGGER.error("Unable to read timestamp file")
        last_run_time = 0

    return (
        convert_unixtime_to_datetime(int(last_run_time))
        if datetime_format
        else int(last_run_time)
    )


def generate_hash(string):
    """
    Generate the SHA1 hash from string
    :param string: {str} string to use in hash
    return: {str} generated hash
    """
    hash_obj = hashlib.sha1(string.encode())
    return hash_obj.hexdigest()


def get_formatted_date_from_timestamp(timestamp):
    """
    Format timestamp to date string with specific format
    :param timestamp: {int} timestamp to format
    :return: {str} formatted date string
    """
    timestamp_in_seconds = timestamp / 1000
    dt_object = datetime.datetime.fromtimestamp(
        timestamp_in_seconds, tz=datetime.timezone.utc
    )

    formatted_string = dt_object.strftime(consts.UNIFIED_CONNECTOR_DATETIME_FORMAT)

    return f"{formatted_string[:-3]}Z"


def separate_data_per_multiple_values_keys(
    raw_data, keys, additional_info, disable_split_event=True
):
    """
    Separate data per keys that contain multiple values
    :param raw_data: {dict} raw data
    :param keys: {list} list of keys with multiple values
    :param additional_info: {dict} additional info that separated items should contain
    :param disable_split_event: {bool} Whether to split events or not (default is False)
    :return: {list} list of separated data items
    """
    initial_data = copy.deepcopy(raw_data)
    initial_data.update(additional_info)

    key_values = {}
    for key in keys:
        values = next(
            get_value_from_nested_dict(
                raw_data, key.split(consts.NESTED_KEYS_DELIMITER)
            )
        )

        if values:
            key_values[key] = values

    if disable_split_event:
        for key, values in key_values.items():
            key_path = key.split(consts.NESTED_KEYS_DELIMITER)
            key_path = key_path[:1] + ["aggr"] + key_path[1:]
            initial_data["_".join(key_path)] = ",".join(values)

        return [initial_data]

    items_count = (
        max([len(values) for values in key_values.values()]) if key_values else 0
    )
    items = [] if items_count else [initial_data]

    for i in range(items_count):
        initial_data = copy.deepcopy(initial_data)

        for key, value in key_values.items():
            initial_data[key.replace(consts.NESTED_KEYS_DELIMITER, "_")] = (
                get_list_item_by_index(value, i)
            )

        items.append(initial_data)

    return items


def get_value_from_nested_dict(raw_data, keys_list):
    """
    Get value from nested dict with list of keys
    :param raw_data: {dict} raw data
    :param keys_list: {list} list of keys
    :return: extracted value
    """
    for key in keys_list:
        if isinstance(raw_data.get(key), dict):
            keys_list.pop(0)
            yield from get_value_from_nested_dict(raw_data.get(key), keys_list)

        elif isinstance(raw_data.get(key), list) and len(keys_list) > 1:
            keys_list.pop(0)
            merged_dict = dict()

            for list_item in raw_data.get(key):
                if not isinstance(list_item, dict):
                    continue

                for list_item_key, list_item_value in list_item.items():
                    list_item_value = (
                        list_item_value
                        if isinstance(list_item_value, list)
                        else [list_item_value]
                    )

                    if list_item_key not in merged_dict:
                        merged_dict[list_item_key] = list_item_value
                        continue

                    merged_dict[list_item_key] += [
                        item
                        for item in list_item_value
                        if item not in merged_dict[list_item_key]
                    ]

            yield from get_value_from_nested_dict(merged_dict, keys_list)

        else:
            yield raw_data.get(key)


def get_list_item_by_index(data, index):
    """
    Get list item by index
    :param data: {list} the list
    :param index: {int} the index
    :return: the list item
    """
    try:
        return data[index]
    except IndexError:
        return None


def get_filters_by_alert_type(
    logger: Any,
    dynamic_filters: list[str],
    alert_type: str,
    fail_on_invalid: bool = False,
) -> list[dict[str, Any]]:
    """
    Get alert type filters from dynamic filters list
    :param logger: Siemplify logger
    :param dynamic_filters: {list} list of dynamic filters
    :param alert_type: {str} alert type
    :param fail_on_invalid: {bool} Whether to fail if validation fails
    :return: {list} the list of filters
    """

    def handle_validation_error(error_message):
        if fail_on_invalid:
            raise GoogleChronicleValidationError(error_message)
        logger.warn(f"{error_message} Ignoring this filter.")

    filters = []
    supported_filters = consts.ALERT_TYPES_SUPPORTED_FILTERS.get(alert_type)

    if dynamic_filters:
        logger.info("Dynamic List Configuration:\n" + "\n".join(dynamic_filters))

    for dynamic_filter in dynamic_filters:
        if len(dynamic_filter.split(consts.FILTER_TYPE_DELIMITER)) < 2:
            handle_validation_error(
                f'Filter "{dynamic_filter}" is invalid because it does not '
                f'contain the required delimiter "{consts.FILTER_TYPE_DELIMITER}". '
                "It should be in the format "
                f'"{alert_type.capitalize()}.Key Operator Value".'
            )
            continue

        alert_type_key, *alert_type_filter = dynamic_filter.split(
            consts.FILTER_TYPE_DELIMITER
        )

        if alert_type_key.lower() != "rule":
            handle_validation_error(
                f'Filter "{dynamic_filter}" uses an unsupported alert type '
                f'"{alert_type_key}". Supported alert types are: rule.'
            )
            continue

        if alert_type_key.lower() != alert_type:
            continue

        filter_key, filter_value_key, filter_operator, filter_values = "", None, "", ""

        for supported_operator in consts.SUPPORTED_OPERATORS:
            items = [
                item.strip()
                for item in alert_type_filter[-1].split(supported_operator)
                if item.strip()
            ]

            if len(items) == 2:
                if len(alert_type_filter) > 1:
                    filter_key = alert_type_filter[0]
                    filter_value_key = items[0]
                else:
                    filter_key = items[0]
                filter_operator = supported_operator
                filter_values = [
                    value.strip().lower()
                    for value in items[1].split(consts.FILTER_VALUES_DELIMITER)
                    if value.strip()
                ]
                break

        if not (filter_key and filter_operator and filter_values):
            handle_validation_error(
                f'Filter "{dynamic_filter}" could not be parsed. '
                "Ensure it has a valid key, operator, and values "
                "in the format "
                f'"{alert_type.capitalize()}.Key Operator Value".'
            )
            continue

        if filter_key not in supported_filters.keys():
            handle_validation_error(
                f'Filter "{dynamic_filter}" uses an unsupported key "{filter_key}" '
                f'for alert type "{alert_type}". Supported keys for this alert '
                f'type are: {", ".join(supported_filters.keys())}.'
            )
            continue

        if filter_operator not in supported_filters.get(filter_key).get(
            "operators", []
        ):
            handle_validation_error(
                f'Filter "{dynamic_filter}" uses an unsupported operator '
                f'"{filter_operator}" for key "{filter_key}". Supported operators '
                f'for this key are: {", ".join(supported_filters.get(filter_key).get("operators", []))}.'
            )
            continue

        if supported_filters.get(filter_key).get("possible_values", []) and list(
            set(filter_values)
            - set(supported_filters.get(filter_key).get("possible_values", []))
        ):
            handle_validation_error(
                f'Filter "{dynamic_filter}" contains invalid values for key '
                f'"{filter_key}". Supported values are: '
                f'{", ".join(supported_filters.get(filter_key).get("possible_values", []))}.'
            )
            continue

        if (
            len(filter_values) > 1
            and filter_operator not in consts.MULTIPLE_VALUES_SUPPORTED_OPERATORS.keys()
        ):
            handle_validation_error(
                f'Filter "{dynamic_filter}" uses operator "{filter_operator}" '
                "with multiple values, which is not supported. For multiple values, "
                f'use operators: {", ".join(consts.MULTIPLE_VALUES_SUPPORTED_OPERATORS.keys())}.'
            )
            continue

        filters.append(
            {
                "filter_key": filter_key,
                "filter_value_key": filter_value_key,
                "operator": filter_operator,
                "filter_values": prepare_filter_values(
                    supported_filters, filter_key, filter_values
                ),
                "response_key": supported_filters.get(filter_key).get("response_key"),
            }
        )

    return filters


def prepare_filter_values(supported_filters, filter_key, filter_values):
    """
    Prepare filter values by applying mapping and transformer functions
    :param supported_filters: {list} List of supported filters
    :param filter_key: {str} filter key
    :param filter_values: {list} list of filter values
    :return: {list} list of transformed filter values
    """
    values = []

    for filter_value in filter_values:
        value = filter_value

        if supported_filters.get(filter_key).get("values_mapping"):
            value = (
                supported_filters.get(filter_key)
                .get("values_mapping")
                .get(filter_value)
            )

        if supported_filters.get(filter_key).get("transformer"):
            value = supported_filters.get(filter_key).get("transformer")(value)

        values.append(value)

    return values


def pass_filters(logger, alert, filters):
    """
    Check if alert passes all filters
    :param logger: Siemplify logger
    :param alert: alert object depends on alert type
    :param filters: {list} list of filter items dicts
    :return: {bool} True if alert passes all filters, False otherwise
    """
    for filter_item in filters:
        filter_results = []

        for filter_value in filter_item.get("filter_values"):
            response_value = getattr(alert, filter_item.get("response_key"))
            filter_value_key = filter_item.get("filter_value_key")
            if filter_value_key is not None:
                response_value = next(
                    filter(lambda v: v.get("key") == filter_value_key, response_value),
                    {},
                ).get("value")
            response_value = (
                response_value.lower()
                if isinstance(response_value, str)
                else response_value
            )

            filter_results.append(
                (response_value is not None or filter_item.get("operator") == "!=")
                and (
                    OPERATOR_FUNCTIONS.get(filter_item.get("operator"))(
                        response_value, filter_value
                    )
                )
            )

        if (
            filter_item.get("operator")
            in consts.MULTIPLE_VALUES_SUPPORTED_OPERATORS.keys()
        ):
            if consts.MULTIPLE_VALUES_SUPPORTED_OPERATORS.get(
                filter_item.get("operator")
            ) == consts.FILTER_LOGIC.get("or") and not next(
                (filter_result for filter_result in filter_results if filter_result),
                None,
            ):
                logger.info(f"'{alert.id}' did not pass filters.")
                return False
            elif consts.MULTIPLE_VALUES_SUPPORTED_OPERATORS.get(
                filter_item.get("operator")
            ) == consts.FILTER_LOGIC.get("and") and not all(filter_results):
                logger.info(f"'{alert.id}' did not pass filters.")
                return False
        elif not all(filter_results):
            logger.info(f"'{alert.id}' did not pass filters.")
            return False

    return True


def convert_hours_to_milliseconds(hours):
    """
    Convert hours to milliseconds
    :param hours: {int} hours to convert
    :return: {int} converted milliseconds
    """
    return hours * 60 * 60 * 1000


def rename_dict_key(original_dict, original_key, new_key):
    """
    Rename key in dict
    :param original_dict: {dict} dict to transform
    :param original_key: {str} original key
    :param new_key: {str} new key
    :return: {dict} transformed dict
    """
    result = original_dict.copy()
    result[new_key] = result.pop(original_key)
    return result


def fix_key_value_pair(raw_event):
    """
    Fix key/value pairs in dict
    :param raw_event: {dict} raw data
    :return: {dict} transformed dict
    """
    all_keys = {key: value for key, value in raw_event.items() if key.count("_key") > 0}

    for key, key_value in all_keys.items():
        value_key = key.replace("_key", "_value")
        value = raw_event.get(value_key)
        if value is not None:
            new_key = re.sub("_+\d+", "", key.replace("_key", f"_{key_value}"))
            if not key.count("detection_"):
                del raw_event[key]
                del raw_event[value_key]
            if new_key in raw_event:
                raw_event[new_key] = f"{value}, {raw_event[new_key]}"
            else:
                raw_event[new_key] = value

    return raw_event


def get_prefix_from_string(string, separator=consts.STRING_PREFIX_SEPARATOR):
    """
    Get prefix from string
    :param string: {str} string
    :param separator: {str} separator to use for string splitting
    :return: {str} prefix
    """
    return string.split(separator)[0]


def get_last_success_time_for_job(
    siemplify,
    offset_with_metric,
    time_format=DATETIME_FORMAT,
    print_value=True,
    microtime=False,
    timestamp_key=TIMESTAMP_KEY,
):
    last_run_timestamp = fetch_timestamp_for_job(
        siemplify, timestamp_key, datetime_format=True
    )
    offset = datetime.timedelta(**offset_with_metric)
    current_time = utc_now()
    # Check if first run
    datetime_result = (
        current_time - offset
        if current_time - last_run_timestamp > offset
        else last_run_timestamp
    )
    unix_result = convert_datetime_to_unix_time(datetime_result)
    unix_result = (
        unix_result if not microtime else int(unix_result / NUM_OF_MILLI_IN_SEC)
    )

    if print_value:
        siemplify.LOGGER.info(
            f"Last success time. Date time:{datetime_result}. Unix:{unix_result}"
        )
    return unix_result if time_format == UNIX_FORMAT else datetime_result


def save_timestamp_for_job(
    siemplify, new_timestamp=unix_now(), timestamp_key=TIMESTAMP_KEY
):
    if isinstance(new_timestamp, datetime.datetime):
        new_timestamp = convert_datetime_to_unix_time(new_timestamp)

    try:
        siemplify.set_scoped_job_context_property(
            property_key=timestamp_key, property_value=json.dumps(new_timestamp)
        )
    except Exception as e:
        raise Exception(f"Failed saving timestamps to db, ERROR: {e}")


def fetch_timestamp_for_job(
    siemplify, timestamp_key=TIMESTAMP_KEY, datetime_format=False
):
    try:
        last_run_time = siemplify.get_scoped_job_context_property(
            property_key=timestamp_key
        )
    except Exception as e:
        raise Exception(f"Failed reading timestamps from db, ERROR: {e}")

    if last_run_time is None:
        last_run_time = 0
    try:
        last_run_time = int(last_run_time)
    except:
        last_run_time = convert_string_to_unix_time(last_run_time)

    if datetime_format:
        last_run_time = convert_unixtime_to_datetime(last_run_time)
    else:
        last_run_time = int(last_run_time)

    return last_run_time


def read_ids_for_job(siemplify, db_key, default_value_to_return=None):
    try:
        str_data = siemplify.get_scoped_job_context_property(property_key=db_key)

        # Check if the db key exists
        if is_empty_string_or_none(str_data):
            siemplify.LOGGER.info(
                'Key: "{}" does not exist in the database. Returning default value instead: '
                "{}".format(db_key, default_value_to_return)
            )
            return default_value_to_return

        data = json.loads(str_data)
        return data

    # If an error happened in the json.loads methods
    except TypeError as err:
        siemplify.LOGGER.error(
            "Failed to parse data as JSON. Returning default value instead: "
            f'"{default_value_to_return}". \nERROR: {err}'
        )
        siemplify.LOGGER.exception(err)
        return default_value_to_return

    # If there is a connection problem with the DB
    except Exception as error:
        siemplify.LOGGER.error(
            f"Exception was raised from the database.  ERROR: {error}."
        )
        siemplify.LOGGER.exception(error)
        raise


def write_ids_for_job(siemplify, content_to_write, db_key, default_value_to_set=None):
    content_to_write = content_to_write[-consts.MAX_FETCH_LIMIT_FOR_JOB :]
    try:
        str_data = json.dumps(content_to_write, separators=(",", ":"))
        siemplify.set_scoped_job_context_property(
            property_key=db_key, property_value=str_data
        )

    # If an error happened in the json.dumps methods
    except TypeError as err:
        siemplify.LOGGER.error(
            "Failed parsing JSON to string. Writing default value instead: "
            f'"{default_value_to_set}". \nERROR: {err}'
        )
        siemplify.LOGGER.exception(err)
        siemplify.set_scoped_job_context_property(
            property_key=db_key,
            property_value=json.dumps(default_value_to_set, separators=(",", ":")),
        )
    # If there is a connection problem with the DB
    except Exception as err:
        siemplify.LOGGER.error(f"Exception was raised from the database.  ERROR: {err}")
        siemplify.LOGGER.exception(err)
        raise


def platform_supports_chronicle(siemplify):
    if hasattr(siemplify, "get_updated_sync_alerts_metadata"):
        return True


def platform_supports_uno_3(siemplify):
    """Return `True` if the SDK object supports latest UNO Phase 3
    syncing features, `False` otherwise.

    Args:
        siemplify (Siemplify): the SDK object

    Returns:
        bool: Whether the 'siemplify' object supports latest UNO Phase 3 updates.
    """
    if platform_supports_chronicle(siemplify):
        # 'include_non_synced_alerts' is an argument added to the SDK method
        # Siemplify.get_updated_sync_alerts_metadata() in UNO phase 3,
        # and does not exist in the Phase 2 SDK code.
        return "include_non_synced_alerts" in get_function_arg_names(
            siemplify.get_updated_sync_alerts_metadata
        )
    return False


def validate_alerts_creator_support(siemplify):
    """Returns true whether current platform version supports the required SDK methods
    for fetching SOAR alerts and creating them in SIEM.

    Args:
        siemplify (Siemplify): The SDK object

    Raises:
        GoogleChroniclePlatformUnsupportedError: Platform version does not support
        current integration code.
    """
    if not hasattr(siemplify, "update_new_alerts_sync_status"):
        raise exceptions.GoogleChroniclePlatformUnsupportedError(
            "Current platform version does not support SDK methods designed for"
            f" {consts.INTEGRATION_DISPLAY_NAME}. Please use version"
            f" {consts.ALERTS_CREATOR_MINIMUM_SUPPORTED_VERSION} or higher."
        )


def convert_time_ms_to_siem_time(timestamp: int | str) -> dict[str, int] | None:
    """Converts given unix / iso 8601 timestamp to Chronicle time representation.

    Args:
        timestamp (int|str): Unix time in milliseconds / ISO 8601 format string

    Returns:
        Chronicle SIEM time format representation of the input time.
        If `timestamp` is `None` or negative, it returns `None`.

    Raises:
        InvalidTimeException: When `timestamp` cannot be converted
    """
    if not timestamp:
        return None

    try:
        timestamp = int(timestamp)
        if timestamp < 0:
            return None
    except ValueError:
        try:
            timestamp = int(convert_string_to_unix_time(timestamp))
        except Exception as e:
            raise InvalidTimeException(
                f"Timestamp {timestamp} cannot be converted - Unknown format"
            ) from e

    seconds = int(timestamp / (10**3))
    nanos = (timestamp - seconds * 1000) * (10**6)
    return {"seconds": seconds, "nanos": nanos}


def retry_decorator(max_retries, delay_ms, siemplify_logger=None):
    """Decorator which retries a function up to @max_retries
    times if the function raises an exception. Retries will be made after a
    gradually increasing delay, using a backoff algorithm. This is done to reduce
    the likelihood of the operation failing again.

    Args:
        max_retries (int): Number of maximum failed retries until
        raising an exception.
        delay_ms (int): Initial delay time in milliseconds.
        siemplify_logger: Logger object, if None, logging will be disabled.

    Returns:
        A decorated function.
    """

    def decorator_function(func):
        def wrapper_function(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if siemplify_logger:
                        siemplify_logger.info(f"{func.__name__} has failed")
                        siemplify_logger.exception(e)

                    if i == max_retries - 1:
                        if siemplify_logger:
                            siemplify_logger.error(
                                f"{func.__name__} has reached the maximum number "
                                "of retries"
                            )
                        raise

                    delay_seconds = (delay_ms / 1000) * (i + 1) * 2
                    if siemplify_logger:
                        siemplify_logger.info(f"Retrying in: {delay_seconds} seconds")
                    time.sleep(delay_seconds)

        return wrapper_function

    return decorator_function


def retry_decorator_class(
    max_retries, delay_ms, siemplify_logger=None, siemplify_logger_attr=None
):
    """Decorator which retries a class function up to @max_retries
    times if the function raises an exception. Retries will be made after a
    gradually increasing delay, using a backoff algorithm. This is done to reduce
    the likelihood of the operation failing again.

    Args:
        max_retries (int): Number of maximum failed retries until
        raising an exception.
        delay_ms (int): Initial delay time in milliseconds.
        siemplify_logger: Logger object, if None, logger will be retrieved
        from the class.
        siemplify_logger_attr: Logger object class attribute name. If None,
        logging will be disabled.

    Returns:
        A decorated function.
    """

    def decorator_function(func):
        def get_attribute(instance):
            if not siemplify_logger_attr or not instance:
                return None
            return getattr(instance, siemplify_logger_attr)

        def wrapper_function(self, *args, **kwargs):
            logger = siemplify_logger
            if not logger:
                logger = get_attribute(self)
            decorated_function = retry_decorator(max_retries, delay_ms, logger)(func)
            return decorated_function(self, *args, **kwargs)

        return wrapper_function

    return decorator_function


def get_reference_list_filter(
    json_results: list[SingleJson],
    filter_key: str,
    filter_value: str,
    filter_logic: str,
) -> list[SingleJson]:
    """Get Reference list Filter

    Args:
        json_results: Get the json result
        filter_key: Get the key that needs to be used to filter lists
        filter_value: Get the filter value
        filter_logic: Get the filter logic either "Equal" or "Contains".

    Returns:
        list of Single Json
    """
    result_data = []
    for item in json_results:
        if (
            filter_key == consts.GET_REFERENCE_FILTER_KEY_CONTENT_TYPE
            and filter_key not in item
        ):
            if (
                filter_logic == consts.GET_REFERENCE_LIST_FILTER_LOGIC_EQUAL
                and filter_value == consts.GET_REFERENCE_LIST_CONTENT_TYPE
            ):
                result_data.append(item)
            elif (
                filter_logic == (consts.GET_REFERENCE_LIST_FILTER_LOGIC_CONTAINS)
                and filter_value in consts.GET_REFERENCE_LIST_CONTENT_TYPE
            ):
                result_data.append(item)
        else:
            for key, value in item.items():
                if key != filter_key:
                    continue

                if (
                    filter_logic == (consts.GET_REFERENCE_LIST_FILTER_LOGIC_EQUAL)
                    and filter_value == value
                ):
                    result_data.append(item)

                elif (
                    filter_logic == (consts.GET_REFERENCE_LIST_FILTER_LOGIC_CONTAINS)
                    and filter_value in value
                ):
                    result_data.append(item)

    return result_data


def transform_data_table_rows(
    raw_rows: list[dict], column_info: list[dict]
) -> list[dict]:
    """
    Transforms raw data table rows (e.g., {"values": ["v1", "v2"]})
    into a more readable dictionary format using column information
    (e.g., {"columnName1": "v1", "columnName2": "v2"}).

    Args:
        raw_rows: A list of raw row dictionaries, where each row has a 'values' list.
        column_info: A list of column information dictionaries,
                     where each dict has 'originalColumn' (the column name).

    Returns:
        A list of transformed row dictionaries.
        Example: [{"colA": "val1", "colB": "val2"}, {"colA": "val3", "colB": "val4"}]
    """
    transformed_rows = []
    column_names = [
        col.get("originalColumn") for col in column_info if col.get("originalColumn")
    ]

    for row in raw_rows:
        values = row.get("values", [])
        transformed_row_values = {}
        for column_index, column_name in enumerate(column_names):
            if column_index < len(values):
                transformed_row_values[column_name] = values[column_index]
            else:
                transformed_row_values[column_name] = None

        new_row = {}
        new_row.update(row)
        new_row["values"] = transformed_row_values

        transformed_rows.append(new_row)

    return transformed_rows


def extract_dict_from_resource_string(
    resource_str: str, pattern: str = consts.RESOURCE_REGEX_PATTERN
) -> dict[str, str]:
    """Extract dict from resource string by given pattern.

    Args:
        resource_str (str): resource string to extract data from
        pattern (str): pattern to apply to resource string

    Returns:
        dict[str, str]: dict extracted from the resource string using pattern
    """
    matches = re.findall(pattern, resource_str)

    return dict(matches)


def build_udm_query(ip: str = None, hostname: str = None, mac: str = None) -> str:
    """
    Build udm query based on ip/hostname/mac

    Args:
        ip (str): ip indicator for the asset
        hostname (str): hostname indicator for the asset
        mac (str): mac indicator for the asset

    Returns:
        str: constructed udm query
    """
    query = ""

    if sum([ip is not None, hostname is not None, mac is not None]) > 1:
        # More than 1 artifact was passed - invalid.
        raise exceptions.GoogleChronicleValidationError(
            "You can only specify a single indicator. The asset indicator may "
            "either be a hostname, an IP address or a MAC address."
        )

    if ip:
        query += " OR ".join(
            [f'{field}="{ip}"' for field in consts.ENTITY_TYPES_MAPPING.get("ADDRESS")]
        )
    elif hostname:
        query += " OR ".join(
            [
                f'{field}="{hostname}" nocase'
                for field in consts.ENTITY_TYPES_MAPPING.get("HOSTNAME")
            ]
        )
    elif mac:
        query += " OR ".join(
            [
                f'{field}="{mac}" nocase'
                for field in consts.ENTITY_TYPES_MAPPING.get("MAC_ADDRESS")
            ]
        )
    else:
        raise exceptions.GoogleChronicleValidationError(
            "You must specify at least one indicator. The asset indicator may "
            "either be a hostname, an IP address or a MAC address."
        )

    return query


def construct_url(
    url_format: str,
    root: str,
    entity_identifier: str = "",
    entity_type: str = "",
    params: dict[str, str] = None,
) -> str:
    """
    Construct a URL string

    Args:
        url_format (str): URL format
        root (str): root of the URL string
        entity_identifier (str): entity identifier
        entity_type (str): entity type
        params (dict[str, str]): url query params

    Returns:
        str: constructed URL
    """
    url = urljoin(
        root,
        url_format.format(entity_identifier=entity_identifier, entity_type=entity_type),
    )
    return update_url_query_params(url, params)


def update_url_query_params(url: str, params: dict[str, str]) -> str:
    """
    Update the url query params with the given params

    Args:
        url (str): url to update with query params
        params (dict[str, str]): given query params

    Returns:
        str: updated url
    """
    url_components = urlparse(url)
    query_params = dict(parse_qsl(url_components.query))
    query_params.update(params)
    updated_query_params = urlencode(query_params)
    updated_url = urlunparse(url_components._replace(query=updated_query_params))

    return str(updated_url)


def seek_to_start(fp: BytesIO) -> int:
    """Seek request's MIME to start of the HTTP response."""
    cur_pos = fp.tell()
    line_ = fp.readline()
    if not line_:
        return -1

    if b"HTTP" in line_:
        fp.seek(cur_pos)
        return 0

    return seek_to_start(fp)


def validate_api_root_for_backstory(api_root: str) -> None:
    if consts.BACKSTORY_API_ROOT_IDENTIFIER in api_root.lower():
        raise GoogleChronicleValidationError(
            "This action is not supported for Backstory API configuration. "
            "Please update the integration configuration."
        )


def _parse_iso_timestamp(timestamp_str: str, error_msg: str) -> datetime.datetime:
    try:
        normalized_str: str = timestamp_str.replace("Z", "+00:00")
        dt: datetime.datetime = datetime.datetime.fromisoformat(normalized_str)

        return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)

    except ValueError as exc:
        raise exceptions.GoogleChronicleValidationError(error_msg) from exc


def _get_custom_time_range(
    start_time_str: str,
    end_time_str: str,
) -> tuple[datetime.datetime, datetime.datetime]:
    """Parses custom start and end time strings into datetime objects.

    Args:
        start_time_str (str): The start time in ISO 8601 format.
        end_time_str (str): The end time in ISO 8601 format.

    Returns:
        A tuple containing the parsed start and end datetime objects.

    Raises:
        exceptions.GoogleChronicleValidationError: If the start time is missing
            or if either time string is not in a valid ISO 8601 format.
    """
    if not start_time_str:
        raise exceptions.GoogleChronicleValidationError(
            "Start Time is mandatory when Time Frame is 'Custom'."
        )

    start_dt: datetime.datetime = _parse_iso_timestamp(
        start_time_str,
        "Invalid Start Time format. Please use ISO 8601 "
        "(e.g., 2023-01-01T00:00:00Z).",
    )

    end_dt: datetime.datetime = (
        _parse_iso_timestamp(
            end_time_str,
            "Invalid End Time format. Please use ISO 8601 "
            "(e.g., 2023-01-01T00:00:00Z).",
        )
        if end_time_str
        else datetime.datetime.now(datetime.timezone.utc)
    )

    return start_dt, end_dt


def _get_predefined_time_range(
    time_frame: str,
    now_utc: datetime.datetime,
) -> tuple[datetime.datetime, datetime.datetime]:
    start_dt: datetime.datetime = now_utc - consts.TIME_DELTAS.get(
        time_frame, datetime.timedelta(days=30)
    )
    return start_dt, now_utc


def get_iso_time_range(
    time_frame: str,
    start_time_str: str,
    end_time_str: str,
) -> tuple[str, str]:
    """Calculates a time range and returns it in ISO 8601 format.

    Supports predefined time frames (e.g., "Last Hour") or a "Custom"
    range using start and end time strings.

    Args:
        time_frame (str): The time frame, e.g., "Last Hour" or "Custom".
        start_time_str (str): The start time in ISO 8601 format.
            Required for "Custom" time_frame.
        end_time_str (str): The end time in ISO 8601 format. Optional for
            "Custom" time_frame, defaults to now.

    Returns:
        A tuple of (start_time, end_time) as ISO 8601 strings.

    Raises:
        exceptions.GoogleChronicleValidationError: For invalid time formats or
            a missing start time with a "Custom" frame.
    """
    start_dt: datetime.datetime
    end_dt: datetime.datetime

    if time_frame == "Custom":
        start_dt, end_dt = _get_custom_time_range(start_time_str, end_time_str)

    else:
        now_utc: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)
        start_dt, end_dt = _get_predefined_time_range(time_frame, now_utc)

    formatted_start: str = start_dt.isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )
    formatted_end: str = end_dt.isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )

    return formatted_start, formatted_end


def deep_merge_dicts(
    dict1: SingleJson,
    dict2: SingleJson,
) -> SingleJson:
    """Recursively merges two dictionaries.

    Merges `dict2` into a copy of `dict1`. If a key exists in both and the
    values are dictionaries, they are merged recursively. Otherwise, the value
    from `dict2` overwrites the value from `dict1`.

    Args:
        dict1 (SingleJson): The base dictionary.
        dict2 (SingleJson): The dictionary to merge, its values take precedence.

    Returns:
        A new dictionary with the merged values.
    """
    merged: SingleJson = dict1.copy()

    for key, value in dict2.items():
        existing: Any = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = deep_merge_dicts(existing, value)

        else:
            merged[key] = value

    return merged


def parse_iso_time(time_str: str | None) -> datetime.datetime | None:
    """Parses an ISO 8601 formatted string into a datetime object.

    Args:
        time_str (str): The ISO 8601 formatted string to parse. Handles the 'Z'
            suffix for UTC for compatibility.

    Returns:
        A datetime object, or None if the input is None.

    Raises:
        GoogleChronicleValidationError: If the time_str is not a valid
            ISO 8601 format.
    """
    if not time_str:
        return None

    try:
        if time_str.endswith("Z"):
            time_str = time_str[:-1] + "+00:00"
        return datetime.datetime.fromisoformat(time_str)

    except (ValueError, TypeError) as exc:
        raise GoogleChronicleValidationError(
            f"Invalid time format: '{time_str}'. Please use a valid ISO 8601 "
            "format (e.g., '2023-10-27T10:00:00Z')."
        ) from exc


def restructure_entity_details(detailed_summary: SingleJson) -> SingleJson:
    """Restructures the entity summary for better readability.

    Extracts the nested 'entity' dictionary and merges it with key top-level
    details from the original summary.

    Args:
        detailed_summary (SingleJson): The original detailed entity summary.

    Returns:
        The restructured entity data.
    """
    if not isinstance(detailed_summary.get("entity"), dict):
        return detailed_summary

    restructured_data: SingleJson = detailed_summary.get("entity", {}).copy()

    for key in consts.KEYS_TO_PRESERVE:
        if key in detailed_summary:
            restructured_data[key] = detailed_summary[key]

    return restructured_data


def normalize_stats_results(raw_data: SingleJson) -> list[SingleJson]:
    """Normalize stats results from raw data into a list of events.

    Args:
        raw_data (SingleJson): Raw data containing stats results.

    Returns:
        list[SingleJson]: A list of events, each represented as a dictionary
        with column names as keys and their corresponding values.
    """
    results = raw_data.get("stats", {}).get("results", [])
    column_names = [col_data["column"] for col_data in results if "column" in col_data]
    column_values = [col_data["values"] for col_data in results if "values" in col_data]
    if not results or not column_values:
        return []
    events = []
    for values_row in zip(*column_values):
        event = {}
        for i, value_dict in enumerate(values_row):
            column_name = column_names[i]
            if "list" in value_dict:
                event[column_name] = {"values": value_dict["list"]["values"]}
            elif "value" in value_dict:
                event[column_name] = {"values": [value_dict["value"]]}
        events.append(event)

    return events


def get_curated_detections(response: SingleJson) -> list[SingleJson]:
    return response.get("curatedRuleDetections", []) or response.get(
        "curatedDetections", []
    )


def extract_and_decode_raw_log(
    raw_log_objects: list[Any],
    event_id: str,
    logger: ScriptLogger,
) -> SingleJson | None:
    """
    Extracts, decodes, and parses the raw log from a Chronicle API response.

    This function processes the response from the 'legacyFindRawLogs'
    endpoint, extracts the base64-encoded log, decodes it, and returns it
    as a JSON object.

    Args:
        raw_log_objects (list[Any]): The list of raw log objects from the API.
            Expected to be a list containing a single datamodel object with a
            `raw_data` attribute.
        event_id (str): The associated event ID, used for logging purposes.
        logger (ScriptLogger): A logger instance for logging warnings or errors.

    Returns:
        SingleJson | None: The decoded raw log as a dictionary, or None if
                        extraction or parsing fails.
    """
    if not raw_log_objects:
        logger.warn(f"No raw log data returned by the API for event ID: {event_id}")
        return None

    try:
        raw_log_json: dict = raw_log_objects[0].raw_data
        raw_logs_inner: list[SingleJson] | None = raw_log_json.get("rawLogs")
        log_bytes_b64: str | None = None

        if raw_logs_inner:
            log_bytes_b64 = raw_logs_inner[0].get("logBytes")

        if not log_bytes_b64:
            logger.info(
                "Could not find 'logBytes' in the response for event ID: %s",
                event_id,
            )
            return None

        decoded_log_str: str = base64.b64decode(log_bytes_b64).decode(
            "utf-8",
            errors="ignore",
        )
        try:
            return json.loads(decoded_log_str)
        except json.JSONDecodeError:
            return {"decodedString": decoded_log_str}

    except (IndexError, TypeError, UnicodeDecodeError) as e:
        logger.error(f"Failed to process raw log for event ID {event_id}. Reason: {e}")
        return None

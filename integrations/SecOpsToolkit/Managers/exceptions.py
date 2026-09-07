# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


class SecOpsToolkitManagerError(Exception):
    """
    General Exception for SecOps Toolkit manager
    """


GoogleSecOpsManagerError = SecOpsToolkitManagerError


class GoogleChronicleAPILimitError(Exception):
    """
    API Limit Exception for Google Chronicle manager
    """


class GoogleChronicleValidationError(Exception):
    """
    Validation Exception for Google Chronicle manager
    """


class GoogleChronicleParameterValidationError(Exception):
    """
    Parameter Validation Exception for Google Chronicle manager
    """


class GoogleChronicleAuthenticationError(Exception):
    """
    Authentication Exception for Google Chronicle manager
    """


class InvalidTimeException(Exception):
    """
    Exception for invalid time
    """


class GoogleChronicleBadRequestError(Exception):
    """
    Exception for Bad Request
    """


class GoogleChroniclePlatformUnsupportedError(Exception):
    """
    The integration code is not compatible with current Platform version.
    """


class GoogleChronicleNotFoundError(SecOpsToolkitManagerError):
    """When requested entity is not found in Google Chronicle"""


class GoogleChronicleDetectionBaseError(Exception):
    """ "Base exception for detection related errors"""


class DetectionNotFoundError(GoogleChronicleDetectionBaseError):
    """Detection cannot be found"""


class DetectionParsingError(GoogleChronicleDetectionBaseError):
    """Detection or Detection parts could not be parsed"""


class GoogleChroniclePermissionError(Exception):
    """Permission error for Google Chronicle manager"""


class InvalidParameterError(Exception):
    """Indicates that parameter value is invalid."""


class GoogleBigQueryManagerError(Exception):
    """General Exception for Google BigQuery manager"""


class GoogleBigQueryValidationError(GoogleBigQueryManagerError):
    """General Validation Error raised in Google BigQuery Integration"""

#! /usr/bin/env python3
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from dataclasses import dataclass
from enum import Enum


@dataclass
class LogTypeConfig:
    """Represents a local parser configuration for a specific log type."""
    log_type: str
    dir_path: str
    parser: str | None = None
    parser_ext: str | None = None

class ParserState(Enum):
    """Represents the state of a parser in Chronicle."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

class ParserExtensionState(Enum):
    """Represents the state of a parser extension in Chronicle."""
    LIVE = "LIVE"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"

class ParserValidationStatus(Enum):
    """Represents the validation outcome of a parser submission."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    INCOMPLETE = "INCOMPLETE"

class Operation(Enum):
    """Represents the planned action for a parser or extension."""
    NONE = "NONE"
    CREATE = "CREATE"
    UPDATE = "UPDATE"

class ParserError(Exception):
    """Base exception for all application-specific errors."""
    pass

class InitializationError(ParserError):
    """Raised when the application cannot be initialized (e.g., missing env vars)."""
    pass

class ValidationError(ParserError):
    """Raised when local validation (e.g., event comparison) fails."""
    pass

class APIError(ParserError):
    """Raised for issues communicating with the SecOps API."""
    pass
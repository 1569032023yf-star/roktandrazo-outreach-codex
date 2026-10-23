"""Allowlisted diagnostics; exception text is evidence only, never telemetry."""
from enum import Enum
import socket


class ErrorCode(str, Enum):
    BROWSER_LAUNCH_ERROR = "BROWSER_LAUNCH_ERROR"
    BROWSER_PROCESS_EXITED = "BROWSER_PROCESS_EXITED"
    PROXY_CONNECTION_ERROR = "PROXY_CONNECTION_ERROR"
    DNS_RESOLUTION_ERROR = "DNS_RESOLUTION_ERROR"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    SOURCE_RATE_LIMITED = "SOURCE_RATE_LIMITED"
    SOURCE_ACCESS_RESTRICTED = "SOURCE_ACCESS_RESTRICTED"
    SOURCE_VERIFICATION_REQUIRED = "SOURCE_VERIFICATION_REQUIRED"
    DOM_LAYOUT_CHANGED = "DOM_LAYOUT_CHANGED"
    RESULT_PARSE_ERROR = "RESULT_PARSE_ERROR"
    CACHE_READ_ERROR = "CACHE_READ_ERROR"
    CACHE_WRITE_ERROR = "CACHE_WRITE_ERROR"
    UNKNOWN_PROVIDER_ERROR = "UNKNOWN_PROVIDER_ERROR"


STAGES = frozenset({"IMPORT", "LAUNCH", "CONTEXT", "NAVIGATION", "SOURCE_CHECK", "DOM", "PARSE", "DETAIL", "SCROLL", "CACHE_READ", "CACHE_WRITE", "CLEANUP", "UNKNOWN"})


class ProviderFailure(Exception):
    def __init__(self, code, stage):
        self.code = ErrorCode(code)
        self.stage = stage if stage in STAGES else "UNKNOWN"
        super().__init__(f"{self.code.value}:{self.stage}")


def classify(exc, stage):
    if isinstance(exc, ProviderFailure):
        return exc
    # Stable Chromium net codes are explicit evidence. Do not guess from
    # arbitrary 'proxy', 'blocked' or 'timeout' words in customer-controlled data.
    text = str(exc)
    if "net::ERR_PROXY_CONNECTION_FAILED" in text or "net::ERR_TUNNEL_CONNECTION_FAILED" in text:
        code = ErrorCode.PROXY_CONNECTION_ERROR
    elif isinstance(exc, socket.gaierror) or "net::ERR_NAME_NOT_RESOLVED" in text:
        code = ErrorCode.DNS_RESOLUTION_ERROR
    elif isinstance(exc, TimeoutError) or "net::ERR_TIMED_OUT" in text or (type(exc).__name__ == "TimeoutError" and type(exc).__module__.startswith("playwright.")):
        code = ErrorCode.NETWORK_TIMEOUT
    elif type(exc).__name__ == "TargetClosedError" and type(exc).__module__.startswith("playwright."):
        code = ErrorCode.BROWSER_PROCESS_EXITED
    elif stage == "IMPORT" and isinstance(exc, ModuleNotFoundError) and (exc.name or "").startswith("playwright"):
        code = ErrorCode.BROWSER_LAUNCH_ERROR
    elif stage == "LAUNCH":
        code = ErrorCode.BROWSER_LAUNCH_ERROR
    elif stage == "CACHE_READ":
        code = ErrorCode.CACHE_READ_ERROR
    elif stage == "CACHE_WRITE":
        code = ErrorCode.CACHE_WRITE_ERROR
    else:
        code = ErrorCode.UNKNOWN_PROVIDER_ERROR
    return ProviderFailure(code, stage)


def safe_error(value, stage="UNKNOWN"):
    """Accept only the exact version-one code:stage wire format."""
    if isinstance(value, str):
        code, sep, observed_stage = value.partition(":")
        if sep and code in ErrorCode._value2member_map_ and observed_stage in STAGES:
            return value
    return str(ProviderFailure(ErrorCode.UNKNOWN_PROVIDER_ERROR, stage))

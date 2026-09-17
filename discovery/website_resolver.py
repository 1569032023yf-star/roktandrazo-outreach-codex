"""Deterministic official-website resolution through a configured provider."""
from __future__ import annotations

from dataclasses import dataclass, field
import ctypes
import multiprocessing
import os
import re
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit


_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001


def _attach_kill_on_close_job(pid: int):
    """Attach a Windows child tree to a close-to-kill Job Object.

    Playwright starts a Node driver and Chromium descendants.  Terminating only
    the multiprocessing Python child leaves those descendants alive on Windows.
    Closing this Job Object terminates every resolver-owned descendant too.
    Non-Windows platforms retain their existing multiprocessing behavior.
    """
    if os.name != "nt":
        return None
    from ctypes import wintypes

    class _BasicLimit(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
        )]

    class _ExtendedLimit(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _BasicLimit), ("IoInfo", _IoCounters),
                   ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                   ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    child = kernel32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, int(pid))
    assigned = False
    try:
        if not child:
            return None
        limits = _ExtendedLimit()
        limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                                 ctypes.byref(limits), ctypes.sizeof(limits)):
            return None
        if not kernel32.AssignProcessToJobObject(job, child):
            return None
        assigned = True
        return job
    finally:
        if child:
            kernel32.CloseHandle(child)
        if job and not assigned:
            kernel32.CloseHandle(job)


def _close_kill_job(job) -> None:
    if job:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(job)

from discovery.normalizer import normalize_business_name, normalize_phone, normalized_domain

NON_OFFICIAL_DOMAINS = {
    "facebook.com", "instagram.com", "linkedin.com", "yelp.com", "yellowpages.com",
    "mapquest.com", "wargames.com", "localgamestores.com", "chamberofcommerce.com",
}


@dataclass(frozen=True)
class WebsiteResolution:
    status: str
    website: str = ""
    score: int = 0
    evidence: list[str] = field(default_factory=list)
    error: str = ""


def _official_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not text.startswith(("http://", "https://")):
        text = "https://" + text
    parsed = urlsplit(text)
    domain = normalized_domain(text)
    if not parsed.netloc or any(domain == item or domain.endswith("." + item) for item in NON_OFFICIAL_DOMAINS):
        return ""
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "", "", ""))


def _name_tokens(value: str) -> set[str]:
    stop = {"the", "and", "store", "shop", "llc", "inc", "company", "co"}
    return {part for part in re.findall(r"[a-z0-9]+", normalize_business_name(value)) if len(part) > 2 and part not in stop}


def score_candidate(subject: dict[str, Any], candidate: Any) -> tuple[int, list[str]]:
    subject_tokens = _name_tokens(subject.get("business_name") or "")
    candidate_tokens = _name_tokens(getattr(candidate, "business_name", ""))
    overlap = len(subject_tokens & candidate_tokens)
    evidence: list[str] = []
    score = 0
    if overlap / max(1, len(subject_tokens)) >= 0.6:
        score += 60
        evidence.append("business_name")
    subject_phone = normalize_phone(subject.get("phone") or "")
    candidate_phone = normalize_phone(getattr(candidate, "phone", "") or "")
    if subject_phone and candidate_phone and subject_phone == candidate_phone:
        score += 35
        evidence.append("phone")
    if (str(subject.get("city") or "").strip().lower() == str(getattr(candidate, "city", "") or "").strip().lower()
            and str(subject.get("state") or "").strip().upper() == str(getattr(candidate, "state", "") or "").strip().upper()):
        score += 20
        evidence.append("city_state")
    return score, evidence


class ProviderWebsiteResolver:
    def __init__(self, provider, minimum_score: int = 80, timeout_seconds: float | None = None) -> None:
        self.provider = provider
        self.minimum_score = minimum_score
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else float(os.getenv("WEBSITE_RESOLUTION_TIMEOUT_SECONDS", "45"))

    @staticmethod
    def _provider_call(provider, query, city, state, result_pipe):
        try:
            result_pipe.send(("ok", provider.search_places(query, city, state, "", 10)))
        except BaseException as exc:
            result_pipe.send(("error", f"{type(exc).__name__}:{exc}"))
        finally:
            result_pipe.close()

    def _bounded_search(self, query: str, city: str, state: str):
        """Run one provider lookup with a hard, cleaned-up deadline."""
        parent, child = multiprocessing.Pipe(duplex=False)
        process = multiprocessing.get_context("spawn").Process(
            target=self._provider_call, args=(self.provider, query, city, state, child), daemon=False,
        )
        started = time.monotonic()
        process.start(); child.close()
        job = _attach_kill_on_close_job(process.pid)
        try:
            process.join(max(0.1, self.timeout_seconds))
            elapsed_ms = int((time.monotonic() - started) * 1000)
            if process.is_alive():
                process.terminate(); process.join(5)
                parent.close()
                return None, WebsiteResolution("network_retry", error=f"provider_timeout:{elapsed_ms}ms"), elapsed_ms
            if not parent.poll():
                parent.close()
                return None, WebsiteResolution("network_retry", error="provider_process_no_result"), elapsed_ms
            kind, value = parent.recv(); parent.close()
            if kind != "ok":
                return None, WebsiteResolution("network_retry", error=value), elapsed_ms
            return value, None, elapsed_ms
        finally:
            # On Windows, this kills the driver/browser tree even if the Python
            # child has already exited or was terminated for a timeout.
            _close_kill_job(job)

    def resolve(self, subject: dict[str, Any]) -> WebsiteResolution:
        query = " ".join(filter(None, [subject.get("business_name"), subject.get("formatted_address"), subject.get("phone")]))
        page, failure, _elapsed_ms = self._bounded_search(query, subject.get("city") or "", subject.get("state") or "")
        if failure:
            return failure
        if not page.ok:
            return WebsiteResolution("network_retry", error=page.error or page.status)
        ranked = []
        for candidate in page.results:
            website = _official_url(getattr(candidate, "website", ""))
            if not website:
                continue
            score, evidence = score_candidate(subject, candidate)
            ranked.append((score, normalized_domain(website), website, evidence))
        if not ranked:
            return WebsiteResolution("not_found")
        score, _domain, website, evidence = sorted(ranked, key=lambda item: (-item[0], item[1], item[2]))[0]
        if score < self.minimum_score:
            return WebsiteResolution("identity_review", website=website, score=score, evidence=evidence)
        return WebsiteResolution("resolved", website=website, score=score, evidence=evidence)

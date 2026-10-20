"""Bounded, credential-free diagnostics for public network capability."""
from __future__ import annotations

import os
import socket
import time
from urllib.parse import urlsplit


def diagnose_network(*, endpoints: dict[str, str] | None = None, fetcher=None,
                     resolver=socket.getaddrinfo, proxy_probe=None) -> dict:
    endpoints = endpoints or {
        "tiktok": "https://shop.tiktok.com/us/k/greetings-cards",
        "amazon": "https://www.amazon.com/s?k=greeting+cards",
        "faire": "https://www.faire.com/category/Holiday%20Cards",
    }
    started = time.monotonic()
    proxy_vars = [name for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY") if os.environ.get(name)]
    proxy_host = ""
    proxy_port = None
    proxy_scheme = ""
    proxy_source = "none"
    proxy_reachable = None
    selected_proxy_var = next((name for name in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY") if os.environ.get(name)), None)
    candidate_proxy = os.environ.get(selected_proxy_var) if selected_proxy_var else None
    if candidate_proxy:
        parsed = urlsplit(candidate_proxy)
        proxy_host = parsed.hostname or "configured"
        proxy_port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        proxy_scheme = parsed.scheme.lower()
        proxy_source = f"process_environment:{selected_proxy_var}"
        if proxy_probe:
            try: proxy_reachable = bool(proxy_probe(parsed.hostname, proxy_port))
            except Exception: proxy_reachable = False
        else:
            try:
                with socket.create_connection((parsed.hostname, proxy_port), timeout=1):
                    proxy_reachable = True
            except OSError:
                proxy_reachable = False
    dns_available = False
    try:
        resolver("example.com", 443, type=socket.SOCK_STREAM)
        dns_available = True
    except OSError:
        pass
    fetcher = fetcher or __import__("brand_acquisition.providers", fromlist=["PublicPageFetcher"]).PublicPageFetcher()
    results = {}
    for source, url in endpoints.items():
        host = urlsplit(url).hostname or ""
        try:
            resolver(host, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            results[source] = {"status":"DNS_ERROR", "error_type":type(exc).__name__}
            continue
        try:
            response = fetcher.fetch(url)
            status = response.status
            results[source] = {"status":status.upper(), "http_status":response.http_status,
                               "error_type":response.error_type or response.error}
        except Exception as exc:
            results[source] = {"status":"NETWORK_ERROR", "error_type":type(exc).__name__}
    https_ok = any(x.get("http_status") is not None for x in results.values())
    egress = dns_available and https_ok
    blocked = not dns_available or bool(proxy_vars and proxy_reachable is False) or not https_ok
    reasons = []
    if not dns_available: reasons.append("DNS resolution failed")
    if proxy_vars and proxy_reachable is False: reasons.append("configured proxy is unreachable")
    if dns_available and not https_ok and not (proxy_vars and proxy_reachable is False): reasons.append("public HTTPS endpoints did not return an HTTP response")
    statuses = {"tiktok":results.get("tiktok",{}).get("status","NOT_CHECKED"),
                "amazon":results.get("amazon",{}).get("status","NOT_CHECKED"),
                "faire":results.get("faire",{}).get("status","NOT_CHECKED")}
    return {
        "NETWORK_EGRESS_AVAILABLE": bool(egress),
        "DEVELOPMENT_ENV_NETWORK_BLOCKED": bool(blocked),
        "DNS_RESOLUTION_AVAILABLE": dns_available,
        "HTTPS_PUBLIC_SITE_AVAILABLE": https_ok,
        "TIKTOK_NETWORK_STATUS": statuses["tiktok"],
        "AMAZON_NETWORK_STATUS": statuses["amazon"],
        "FAIRE_NETWORK_STATUS": statuses["faire"],
        "FAILURE_LAYER": "local_dns_or_proxy_or_egress" if blocked else ("platform_or_page" if not https_ok else "none"),
        "FAILURE_REASON": "; ".join(reasons) or "no diagnosed failure",
        "PROXY_CONFIGURED": bool(proxy_vars),
        "PROXY_VARIABLES_PRESENT": proxy_vars,
        "PROXY_HOST": proxy_host,
        "PROXY_PORT": proxy_port,
        "PROXY_SCHEME": proxy_scheme,
        "PROXY_CONFIG_SOURCE": proxy_source,
        "PROXY_SELECTED_VARIABLE": selected_proxy_var,
        "PROXY_REACHABLE": proxy_reachable,
        "NETWORK_POLICY_SOURCE_IDENTIFIED": False,
        "NETWORK_POLICY_SOURCE_NOTE": "Process environment reveals proxy variables only; application injection versus host policy cannot be determined from this runtime.",
        "BROWSER_RENDERER_AVAILABLE": False,
        "PROVIDER_DIAGNOSTICS": results,
        "TOTAL_RUNTIME_SECONDS": round(time.monotonic()-started, 3),
    }

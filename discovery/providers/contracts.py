"""Read-only Provider capabilities; never a dispatch or billing authorization."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderContract:
    provider: str
    transport: str
    authentication: str
    status: str = "CONTRACT_MISSING"
    supports_operation_lookup: bool = False
    supports_idempotent_submit: bool = False
    supports_cancel: bool = False
    authoritative_cost_available: bool = False
    missing_fields: tuple[str, ...] = (
        "operation_id_to_run_claim_binding",
        "authoritative_terminal_status",
        "idempotency_guarantee",
        "cancellation_receipt_and_fee",
        "billing_account_project_sku_binding",
        "usage_period_quantity_unit",
        "billed_amount_currency_credits",
        "billing_evidence_reference",
    )


def provider_contract(name: str, mode: str = "") -> ProviderContract:
    if name == "google_places":
        return ProviderContract(name, "synchronous_https_post", "X-Goog-Api-Key")
    if name == "browser_maps":
        # Reading a cache does not prove a new browser request or zero cost.
        transport = "local_file" if mode == "file" else "browser"
        return ProviderContract(name, transport, "existing_browser_session",
            missing_fields=ProviderContract.missing_fields + (
                "source_usage_authorization", "browser_request_receipt",))
    if name == "serpapi_maps":
        return ProviderContract(name, "disabled", "disabled", status="DISABLED")
    return ProviderContract(name, "unspecified", "unspecified")


def bound_search_request(value):
    """Validate existing search_places arguments without dispatch or defaults.
    校验真实适配器已有参数；不授予请求权限、不补默认业务值。
    """
    keys = {'provider', 'query', 'city', 'state', 'page_cursor', 'page_size'}
    if type(value) is not dict or set(value) != keys:
        raise ValueError('PROVIDER_SEARCH_REQUEST_SCHEMA')
    if value['provider'] not in ('google_places', 'browser_maps'):
        raise ValueError('PROVIDER_SEARCH_REQUEST_DISABLED')
    for key, limit in (('query', 2048), ('city', 256), ('state', 128), ('page_cursor', 8192)):
        item = value[key]
        if (type(item) is not str or len(item.encode('utf-8')) > limit or
                any(ord(c) < 32 or ord(c) == 127 for c in item) or
                (key != 'page_cursor' and not item.strip())):
            raise ValueError('PROVIDER_SEARCH_ARGUMENT_REJECTED')
    if type(value['page_size']) is not int or not 1 <= value['page_size'] <= 20:
        raise ValueError('PROVIDER_SEARCH_PAGE_SIZE')
    return dict(value)

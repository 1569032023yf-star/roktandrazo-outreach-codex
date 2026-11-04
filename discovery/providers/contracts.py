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

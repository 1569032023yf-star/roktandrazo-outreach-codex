"""Locked V6 content and evidence-based routing; no transport or database access."""
from __future__ import annotations

import hashlib
import html
import json
import re

RETAIL = "retail_distributor_v6_locked"
CUSTOM = "custom_production_v6_locked"
REFERRAL = "general_inbox_referral_v6_locked"
RENDERER_VERSION = "v6_plain_html_v1"

TEMPLATES = {
    RETAIL: ("Puzzles & card games for {store_name}?", """Hi {greeting},

I'm Ian from rokt&razo. We create family card games and jigsaw puzzles, including our 24-in-1 puzzle series.

We're expanding our retail partnerships and offer low minimum orders, DDP pricing, and product samples for review.

Would you be interested in taking a look at our wholesale catalog to see if anything might be a fit for {store_name}?

{signature}"""),
    CUSTOM: ("Custom product production for {store_name}", """Hi {greeting},

I'm Ian from rokt&razo. With over 10 years of experience, we help brands develop and manufacture custom card games, puzzles, printed paper products, and packaging.

We support flexible production runs, from small test orders to larger-scale manufacturing.

Are you currently developing new products or exploring additional production partners? I'd be happy to share a brief overview of our capabilities.

{signature}"""),
    REFERRAL: ("Right contact at {store_name}?", """Hi {greeting},

I'm Ian from rokt&razo. We offer wholesale puzzles and family card games, as well as custom product development and production services.

Could you please point me to the person responsible for purchasing or product development at {store_name}?

I'd be happy to share a short introduction with the right person.

Thank you for your help!

{signature}"""),
}
SIGNATURE = """Best regards,

Ian
Business Development Specialist
rokt&razo

This is a commercial introduction from rokt&razo.

Business mailing address: {address}

If you prefer not to receive further business emails from us, reply "unsubscribe" and we'll stop."""

RETAIL_TYPES = frozenset({"toy_store", "game_store", "board_game_store", "puzzle_store",
    "bookstore", "independent_bookstore", "gift_shop", "museum_store", "museum_gift_shop",
    "souvenir_store", "card_game_store", "hobby_store", "comic_store", "childrens_store",
    "educational_store", "distributor", "wholesaler"})
CUSTOM_TYPES = frozenset({"brand_owner", "card_game_brand", "puzzle_brand", "game_brand",
    "greeting_card_brand", "paper_goods_brand", "publisher", "design_brand",
    "private_label", "custom_merchandise", "oem"})


def canonical_hash(key):
    value = [key, *TEMPLATES[key], SIGNATURE, RENDERER_VERSION]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()


# Fixed separately from runtime calculations. Updating content requires a reviewed lock update.
LOCKED_SHA256 = {'retail_distributor_v6_locked': '37fb98788e6d3f89fcd105ec1d009ed68ece086e7d13375660746d8727e635d3', 'custom_production_v6_locked': '7ead050c156c70042e11459f400c1d4b41eccbd2c60198707717f43bac81911c', 'general_inbox_referral_v6_locked': '434956cee706dc9753669b63c7ade881690a6095b727d285f6b605a002b5e0f9'}


def _clean(value):
    value = str(value or "").strip()
    if not value or any(c in value for c in "\r\n{}<>\x00") or re.search(r"https?://|www\.", value, re.I):
        raise ValueError("V6_UNSAFE_OR_MISSING_FIELD")
    return value


def reviewed_lead(lead, policy):
    """Operational review is separate from and never replaces V2/history eligibility."""
    review = (policy.get("reviewed_leads") or {}).get(str(lead.get("id")))
    if not isinstance(review, dict) or review.get("identity_verified") is not True:
        raise ValueError("V6_IDENTITY_REVIEW_REQUIRED")
    if not str(review.get("evidence_url") or "").startswith("https://"):
        raise ValueError("V6_BUSINESS_EVIDENCE_REQUIRED")
    if not review.get("organization_key") or review.get("organization_key") != lead.get("organization_key"):
        raise ValueError("V6_ORGANIZATION_REVIEW_MISMATCH")
    if str(review.get("email") or "").casefold() != str(lead.get("email") or "").casefold():
        raise ValueError("V6_RECIPIENT_REVIEW_MISMATCH")
    if review.get("product_fit_verified") is not True or review.get("business_contact_basis_verified") is not True:
        raise ValueError("V6_PRODUCT_FIT_OR_CONTACT_BASIS_UNVERIFIED")
    return review


def route(lead, policy):
    review = reviewed_lead(lead, policy)
    override = str(lead.get("template_override") or review.get("template_override") or "")
    if override:
        if override not in TEMPLATES or review.get("approved_template_override") != override:
            raise ValueError("V6_MANUAL_TEMPLATE_NOT_VERIFIED")
        return override
    kind = str(review.get("business_type") or "").lower().replace("-", "_").replace(" ", "_")
    if review.get("business_type_verified") is True:
        if kind in RETAIL_TYPES:
            return RETAIL
        if kind in CUSTOM_TYPES:
            return CUSTOM
    role = str(review.get("recipient_role") or "").lower()
    if role in {"unknown", "general", "support", "service"}:
        return REFERRAL
    raise ValueError("V6_BUSINESS_TYPE_REVIEW_REQUIRED")


def render(lead, policy, template_key=None):
    from send_resumption import require_content_evidence
    require_content_evidence(policy)
    key = route(lead, policy)
    if template_key is not None and template_key != key:
        raise ValueError("V6_TEMPLATE_ROUTE_MISMATCH")
    if canonical_hash(key) != LOCKED_SHA256.get(key):
        raise ValueError("V6_TEMPLATE_INTEGRITY_FAILED")
    name = _clean(lead.get("store_name"))
    address = _clean(policy.get("verified_postal_address"))
    signature = SIGNATURE.format(address=address)
    subject = TEMPLATES[key][0].format(store_name=name)
    text = TEMPLATES[key][1].format(greeting=f"{name} team", store_name=name, signature=signature)
    body_html = "\n".join("<p>" + html.escape(p).replace("\n", "<br>\n") + "</p>" for p in text.split("\n\n"))
    digest = hashlib.sha256(json.dumps([key, subject, text, body_html], ensure_ascii=False).encode()).hexdigest()
    return {"template_key": key, "template_id": key, "template_status": "ACTIVE_LOCKED",
        "template_sha256": LOCKED_SHA256[key], "content_sha256": digest,
        "renderer_version": RENDERER_VERSION,
        "renderer_sha256": hashlib.sha256(RENDERER_VERSION.encode()).hexdigest(),
        "subject": subject, "body_text": text, "body_html": body_html,
        "body_html_no_pixel": body_html, "has_pixel": False, "routing_reason": "verified_business_review"}


def validate_message(record, lead, policy):
    """Exact re-render, not a phrase/length check. Old V5 FSPs cannot pass."""
    key = record.get("template_id") or record.get("template_key")
    if key not in TEMPLATES:
        raise ValueError("V6_ONLY_NEW_OUTREACH")
    expected = render(lead, policy, key)
    for field, frozen in (("subject", "email_subject"), ("body_text", "email_body"), ("body_html", "email_body_html")):
        actual = record[field] if field in record else record.get(frozen)
        if actual != expected[field]:
            raise ValueError("V6_FROZEN_CONTENT_MISMATCH:" + field)
    for field in ("template_key", "content_sha256", "renderer_version", "renderer_sha256"):
        if record.get(field) and record[field] != expected[field]:
            raise ValueError("V6_METADATA_MISMATCH:" + field)
    if record.get("pixel_tracking") or record.get("attachments"):
        raise ValueError("V6_TRACKING_OR_ATTACHMENTS_FORBIDDEN")
    return expected


def render_internal_test(key, recipient, policy):
    """User-controlled mailbox only; no postal-address exception for customers."""
    if key not in TEMPLATES or canonical_hash(key) != LOCKED_SHA256.get(key):
        raise ValueError("V6_TEMPLATE_INTEGRITY_FAILED")
    approved = {str(x).casefold() for x in policy.get("controlled_test_recipients", [])}
    if not recipient or recipient.casefold() not in approved or not policy.get("test_ownership_reference"):
        raise ValueError("V6_TEST_RECIPIENT_NOT_CONTROLLED")
    if policy.get("internal_test_only") is not True:
        raise ValueError("V6_INTERNAL_TEST_SCOPE_REQUIRED")
    signature = SIGNATURE.replace("Business mailing address: {address}\n\n", "")
    text = TEMPLATES[key][1].format(greeting="rokt&razo team", store_name="rokt&razo", signature=signature)
    text = "INTERNAL TEMPLATE TEST — not customer outreach. Business claims await verification.\n\n" + text
    subject = "[INTERNAL V6 TEST] " + TEMPLATES[key][0].format(store_name="rokt&razo")
    body_html = "\n".join("<p>" + html.escape(p).replace("\n", "<br>\n") + "</p>" for p in text.split("\n\n"))
    return {"template_id": key, "subject": subject, "body_text": text, "body_html": body_html,
            "test_only": True, "attachments": [], "has_pixel": False}

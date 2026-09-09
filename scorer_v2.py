"""
Roktandrazo BD Outreach - Lead Scorer V2.1 (Checklist-Based + MX Validation)
Updated A/B/C rules per user spec 2026-06-17

A级: 官网+官网邮箱+实体零售+产品匹配+未suppress+未发送+有evidence_url+email域名有MX
B级: 有官网+只有contact form 或 邮箱来自第三方但门店高度匹配
C级: 非实体零售/制造商/个人工作室/官网不完整/邮箱来源无法确认/产品不匹配/email域名无MX
"""


def score_lead_v2(lead: dict, suppression_emails: set = None, sent_emails: set = None) -> dict:
    """
    V2 checklist-based scoring.

    Returns dict with grade, reasons list, and detailed checklist results.
    """
    if suppression_emails is None:
        suppression_emails = set()
    if sent_emails is None:
        sent_emails = set()

    reasons = []
    checklist = {}

    # ---- MX cache (global, shared across calls) ----
    if not hasattr(score_lead_v2, "_mx_cache"):
        score_lead_v2._mx_cache = {}

    # ---- Extract fields ----
    website = (lead.get("official_website") or "").strip()
    email = (lead.get("email") or "").strip()
    email_source = (lead.get("email_source_page") or lead.get("evidence_url") or "").strip()
    contact_form = (lead.get("contact_form_url") or "").strip()
    contact_page = (lead.get("contact_page") or "").strip()
    wholesale_page = (lead.get("wholesale_or_vendor_page") or "").strip()
    store_type = (lead.get("store_type") or "").lower()
    store_name = (lead.get("store_name") or "").lower()
    product_fit = (lead.get("product_fit") or "").lower()
    evidence_url = (lead.get("evidence_url") or "").strip()
    fit_reason = (lead.get("fit_reason") or "").lower()

    # ============================================================
    # CHECK 1: Official website exists?
    # ============================================================
    has_website = bool(website and website.startswith("http"))
    checklist["has_official_website"] = has_website
    if has_website:
        reasons.append("Has official website")
    else:
        reasons.append("NO official website")

    # ============================================================
    # CHECK 2: Email from own website?
    # ============================================================
    email_from_own_site = False
    if email and has_website:
        from urllib.parse import urlparse
        email_domain = urlparse(email_source).netloc.lower() if email_source else ""
        site_domain = urlparse(website).netloc.lower().replace("www.", "")
        if email_domain:
            email_domain_clean = email_domain.replace("www.", "")
            email_from_own_site = (
                email_domain_clean == site_domain or
                email_domain_clean.endswith("." + site_domain) or
                site_domain.endswith("." + email_domain_clean)
            )
        # Also check if email_source is the same as website
        if not email_from_own_site and email_source:
            if site_domain in email_source.lower():
                email_from_own_site = True

    checklist["email_from_own_website"] = email_from_own_site
    if email:
        if email_from_own_site:
            reasons.append(f"Email {email} from own website")
        else:
            reasons.append(f"Email {email} from third-party or unconfirmed source")

    # ============================================================
    # CHECK 3: Physical retail store?
    # ============================================================
    non_retail_keywords = [
        "escape room", "escape game", "virtual", "online only",
        "workshop", "studio", "maker", "artisan", "manufacturer only",
        "event space", "party venue", "birthday party",
    ]
    retail_positive_keywords = [
        "toy store", "toy shop", "game store", "game shop",
        "puzzle shop", "puzzle store", "gift shop", "gift store",
        "museum store", "museum shop", "bookstore", "hobby shop",
        "hobby store", "retail", "store", "shop",
    ]

    is_non_retail = any(kw in store_type or kw in store_name or kw in fit_reason for kw in non_retail_keywords)
    is_retail = any(kw in store_type or kw in store_name or kw in fit_reason for kw in retail_positive_keywords)

    # If explicitly non-retail, override
    has_physical_store = is_retail and not is_non_retail
    checklist["is_physical_retail"] = has_physical_store

    if has_physical_store:
        reasons.append(f"Physical retail store: {store_type}")
    elif is_non_retail:
        reasons.append(f"NOT retail (detected non-retail keywords): {store_type}")
    else:
        reasons.append(f"Retail status unclear: {store_type}")

    # ============================================================
    # CHECK 4: Product match for rokt&razo?
    # ============================================================
    product_match_keywords = [
        "toy", "game", "puzzle", "card game", "board game",
        "gift", "educational", "learning", "family",
        "museum", "bookstore", "hobby", "craft",
    ]
    product_mismatch_keywords = [
        "escape room", "virtual", "online only",
        "antique", "vintage collectible", "auto parts",
    ]

    product_match = any(
        kw in store_type or kw in store_name or kw in product_fit or kw in fit_reason
        for kw in product_match_keywords
    )
    product_mismatch = any(
        kw in store_type or kw in store_name or kw in fit_reason
        for kw in product_mismatch_keywords
    )

    is_product_match = product_match and not product_mismatch
    checklist["product_match"] = is_product_match

    if is_product_match:
        reasons.append(f"Product match: {product_fit}")
    elif product_mismatch:
        reasons.append(f"Product MISMATCH detected")
    else:
        reasons.append(f"Product match unclear")

    # ============================================================
    # CHECK 5: Not in suppression list?
    # ============================================================
    not_suppressed = email and email.lower() not in {e.lower() for e in suppression_emails}
    checklist["not_suppressed"] = not_suppressed
    if email and not not_suppressed:
        reasons.append("IN SUPPRESSION LIST")

    # ============================================================
    # CHECK 6: Not already sent?
    # ============================================================
    not_sent = email and email.lower() not in {e.lower() for e in sent_emails}
    checklist["not_already_sent"] = not_sent
    if email and not not_sent:
        reasons.append("ALREADY SENT")

    # ============================================================
    # CHECK 7: Has evidence_url?
    # ============================================================
    has_evidence = bool(evidence_url and evidence_url.startswith("http"))
    checklist["has_evidence_url"] = has_evidence
    if has_evidence:
        reasons.append("Has evidence URL")
    else:
        reasons.append("NO evidence URL")

    # ============================================================
    # CHECK 8a: Email domain has valid MX records? (V2.1)
    # ============================================================
    has_valid_mx = True
    if email and has_website:
        email_domain = email.split("@")[-1].lower().strip()
        # Skip if it's a common free email domain (gmail, yahoo, etc.)
        free_email_domains = {
            "gmail.com", "yahoo.com", "yahoo.co.uk", "hotmail.com", "outlook.com",
            "live.com", "msn.com", "aol.com", "ymail.com", "mail.com",
            "protonmail.com", "proton.me", "icloud.com", "me.com",
            "comcast.net", "verizon.net", "att.net", "bellsouth.net",
            "earthlink.net", "sbcglobal.net", "charter.net",
        }
        if email_domain not in free_email_domains:
            # Check MX cache first
            if email_domain in score_lead_v2._mx_cache:
                has_valid_mx = score_lead_v2._mx_cache[email_domain]
            else:
                try:
                    import dns.resolver
                    answers = dns.resolver.resolve(email_domain, 'MX')
                    has_valid_mx = len(answers) > 0
                except Exception:
                    has_valid_mx = False
                score_lead_v2._mx_cache[email_domain] = has_valid_mx

    checklist["email_domain_has_mx"] = has_valid_mx
    if email and has_valid_mx:
        reasons.append(f"Email domain {email.split('@')[1]} has valid MX")
    elif email and not has_valid_mx:
        reasons.append(f"Email domain {email.split('@')[1]} has NO MX record — cannot receive email")

    # ============================================================
    # CHECK 8: Contact form available? (for B grade)
    # ============================================================
    has_contact_form = bool(contact_form)
    checklist["has_contact_form"] = has_contact_form

    # ============================================================
    # GRADING
    # ============================================================
    grade = "C"
    grade_reason = ""

    # A grade: all of the following
    a_conditions = [
        has_website,
        bool(email),
        email_from_own_site,
        has_physical_store,
        is_product_match,
        not_suppressed if email else True,
        not_sent if email else True,
        has_evidence,
        has_valid_mx,  # V2.1: MX validation
    ]

    if all(a_conditions):
        grade = "A"
        grade_reason = "All A-grade conditions met: official website + email from own site + physical retail + product match + evidence"
    else:
        # B grade
        b_conditions = [
            has_website,
            is_product_match,
            has_physical_store,
        ]

        if all(b_conditions):
            if has_contact_form and not email:
                grade = "B"
                grade_reason = "Has website + product match + physical store, but only contact form (no email)"
            elif email and not email_from_own_site:
                grade = "B"
                grade_reason = "Has website + product match + physical store, but email from third-party source"
            elif email and email_from_own_site and not has_evidence:
                grade = "B"
                grade_reason = "Has website + email from own site, but missing evidence_url"
            elif email and email_from_own_site and not not_suppressed:
                grade = "B"
                grade_reason = "Has website + email from own site, but in suppression list"
            elif email and email_from_own_site and not not_sent:
                grade = "B"
                grade_reason = "Has website + email from own site, but already sent"
            else:
                grade = "B"
                grade_reason = "Has website + product match + physical store, but some A-grade conditions missing"
        else:
            grade = "C"
            # Determine why
            if not has_website:
                grade_reason = "No official website"
            elif not is_product_match:
                grade_reason = "Product mismatch"
            elif not has_physical_store:
                grade_reason = "Not a physical retail store"
            elif email and not has_valid_mx:
                grade_reason = f"Email domain {email.split('@')[1]} has no MX record"
            else:
                grade_reason = "Multiple conditions not met"

    reasons.insert(0, f"Grade: {grade} — {grade_reason}")

    return {
        "grade": grade,
        "grade_reason": grade_reason,
        "reasons": reasons,
        "checklist": checklist,
        "a_conditions_met": all(a_conditions),
        "can_dry_run": grade == "A",
    }


def batch_score_v2(leads: list, suppression_emails: set = None, sent_emails: set = None) -> list:
    """Batch score leads with V2 rules."""
    for lead in leads:
        result = score_lead_v2(lead, suppression_emails, sent_emails)
        lead["confidence_score"] = result["grade"]
        lead["scoring_detail"] = result
    return leads


if __name__ == "__main__":
    # Test
    test_leads = [
        {
            "store_name": "Test Store",
            "store_type": "independent toy store",
            "city": "Portland",
            "state": "OR",
            "official_website": "https://teststore.com",
            "email": "info@teststore.com",
            "evidence_url": "https://teststore.com/contact",
            "email_source_page": "https://teststore.com/contact",
            "product_fit": "both",
            "fit_reason": "Toy store selling games and puzzles",
        },
    ]
    for lead in test_leads:
        result = score_lead_v2(lead)
        print(f"\n{lead['store_name']}:")
        print(f"  Grade: {result['grade']}")
        print(f"  Reasons:")
        for r in result["reasons"]:
            print(f"    - {r}")
        print(f"  Checklist: {result['checklist']}")

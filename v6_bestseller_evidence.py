"""Read-only evidence preparation. Not a registered template or sending entry point."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent
ASSET = ROOT / 'assets/v6/evidence/tiktok_jigsaw_bestsellers_original.png'
ORIGINAL_SHA256 = 'd2c82e81da5ad3071b2644d3edc2727985edb1c54a1c6a632ac43162874ae81b'
TEMPLATE_KEY = 'retail_tiktok_bestseller_v6_locked'
EVIDENCE_RENDER_VERSION = 'historical_category_cid_v1'
CID = 'v6-ranking-' + ORIGINAL_SHA256 + '@roktandrazo.invalid'
RELEVANT_TYPES = frozenset({'toy_store', 'game_store', 'board_game_store',
    'puzzle_store', 'card_game_store', 'distributor', 'wholesaler'})


def inspect_original(path=ASSET):
    """A receipt date or filesystem timestamp does not prove capture date."""
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != ORIGINAL_SHA256:
        raise ValueError('V6_SCREENSHOT_BYTES_CHANGED')
    if not raw.startswith(b'\x89PNG\r\n\x1a\n') or raw[12:16] != b'IHDR':
        raise ValueError('V6_SCREENSHOT_INVALID_PNG')
    width, height = struct.unpack('>II', raw[16:24])
    if len(raw) > 200_000 or min(width, height) < 100:
        raise ValueError('V6_SCREENSHOT_NOT_LIGHTWEIGHT_VISIBLE_EVIDENCE')
    return {'sha256': digest, 'bytes': len(raw), 'width': width, 'height': height}


def require_capture_evidence(record, *, today=None):
    """Require a reviewed attestation tied to these exact original bytes."""
    inspect_original()
    today = today or datetime.now(timezone(timedelta(hours=8))).date()
    if not isinstance(record, dict) or record.get('source_sha256') != ORIGINAL_SHA256:
        raise ValueError('V6_CAPTURE_SOURCE_MISMATCH')
    if record.get('capture_date_verified') is not True or not str(record.get('capture_date_reference') or '').strip():
        raise ValueError('V6_CAPTURE_DATE_UNVERIFIED')
    try:
        captured = date.fromisoformat(record['capture_date'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('V6_CAPTURE_DATE_INVALID') from None
    if captured > today:
        raise ValueError('V6_CAPTURE_DATE_IN_FUTURE')
    if (record.get('platform') != 'TikTok Shop' or record.get('platform_verified') is not True
            or not str(record.get('platform_reference') or '').strip()):
        raise ValueError('V6_PLATFORM_UNVERIFIED')
    if (record.get('category') != 'Jigsaw Puzzles'
            or type(record.get('rank')) is not int or record['rank'] != 1):
        raise ValueError('V6_RANKING_SCOPE_MISMATCH')
    if record.get('product_identity_verified') is not True or not str(record.get('product_identity_reference') or '').strip():
        raise ValueError('V6_PRODUCT_IDENTITY_UNVERIFIED')
    return captured.isoformat()


def relevant_review(review):
    """Category or an info@ prefix alone is insufficient relevance evidence."""
    kind = str(review.get('business_type') or '').lower().replace('-', '_').replace(' ', '_')
    return bool(review.get('identity_verified') is True
        and review.get('business_type_verified') is True and kind in RELEVANT_TYPES
        and review.get('product_fit_verified') is True
        and review.get('tiktok_product_relevance_verified') is True
        and str(review.get('tiktok_product_relevance_url') or '').startswith('https://')
        and str(review.get('tiktok_product_relevance_reference') or '').strip())


def load_receipt():
    return json.loads((ROOT / 'assets/v6/evidence/receipt.json').read_text(encoding='utf-8'))


def append_ranking_evidence(text, body_html, record):
    import html
    captured = require_capture_evidence(record)
    note = (f'Ranking screenshot captured on {captured}: Travel Series 24 Mini Pack, '
        '#1 in TikTok Shop Jigsaw Puzzles Best Sellers. Historical category ranking only; '
        'this is not a claim of current rank or first place across TikTok.')
    return (text + '\n\n' + note,
        body_html + '<p>' + html.escape(note) + '</p><img src="cid:' + CID
        + '" alt="Original historical Jigsaw Puzzles ranking screenshot" width="400">')


def attach_verified_cid(message, body_html, record):
    """Only the pinned original is allowed; callers cannot provide paths or bytes."""
    if 'cid:' + CID not in (body_html or ''):
        return message
    from email.mime.image import MIMEImage
    from email.mime.multipart import MIMEMultipart
    require_capture_evidence(record)
    if body_html.count('cid:' + CID) != 1:
        raise ValueError('V6_CID_REFERENCE_INVALID')
    payload = message.get_payload()
    if message.get_content_type() != 'multipart/alternative' or len(payload) != 2:
        raise ValueError('V6_MIME_ALTERNATIVE_REQUIRED')
    related = MIMEMultipart('related')
    related.attach(payload[1])
    image = MIMEImage(ASSET.read_bytes(), _subtype='png')
    # Recheck bytes used for MIME, rather than trusting a prior filesystem read.
    if hashlib.sha256(image.get_payload(decode=True)).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('V6_SCREENSHOT_BYTES_CHANGED')
    image.add_header('Content-ID', '<' + CID + '>')
    image.add_header('Content-Disposition', 'inline', filename='historical-jigsaw-ranking.png')
    related.attach(image)
    message.set_payload([payload[0], related])
    return message

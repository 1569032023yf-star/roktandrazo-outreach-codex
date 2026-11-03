"""Offline host evidence consumer; deliberately contains no production dispatcher.

Trust keys are provisioned outside envelopes. HMAC verifies provenance, not the
truth of a collector's OS measurements. Production trust provisioning and the
formal execution adapter remain separate release gates.
"""
import hashlib
import hmac
import json
import re
from pathlib import Path
from dataclasses import dataclass
from autonomy.unattended_policy import GATES, INVENTORY, readiness
from autonomy.bridge_acceptance import classify_pair


class EvidenceError(ValueError):
    pass


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


@dataclass(frozen=True)
class TrustedSource:
    source_id: str
    principal_id: str
    key: bytes


class EvidenceConsumer:
    def __init__(self, sources, *, max_age_seconds=300):
        if type(max_age_seconds) is not int or not 0 < max_age_seconds <= 3600:
            raise EvidenceError('INVALID_TRUST_POLICY')
        self.sources = dict(sources)
        if any(type(s) is not TrustedSource or type(s.key) is not bytes or len(s.key) < 32
               or k != s.source_id for k, s in self.sources.items()):
            raise EvidenceError('INVALID_TRUST_POLICY')
        self.max_age = max_age_seconds

    def verify(self, envelope, *, kind, now):
        if type(now) is not int or now < 0 or type(envelope) is not dict:
            raise EvidenceError('INVALID_EVIDENCE')
        if set(envelope) != {'payload', 'mac'} or type(envelope['payload']) is not dict:
            raise EvidenceError('INVALID_EVIDENCE')
        p = envelope['payload']
        try:
            source = self.sources.get(p.get('source_id'))
            raw = canonical(p)
        except (TypeError, ValueError, OverflowError):
            raise EvidenceError('INVALID_EVIDENCE') from None
        if source is None:
            raise EvidenceError('UNTRUSTED_SOURCE')
        mac = envelope['mac']
        if type(mac) is not str or not re.fullmatch('[0-9a-f]{64}', mac):
            raise EvidenceError('INVALID_SIGNATURE')
        if not hmac.compare_digest(hmac.new(source.key, raw, hashlib.sha256).hexdigest(), mac):
            raise EvidenceError('INVALID_SIGNATURE')
        if p.get('principal_id') != source.principal_id or p.get('inventory_id') != INVENTORY:
            raise EvidenceError('IDENTITY_MISMATCH')
        if p.get('kind') != kind or p.get('schema') != 'rokt.host-evidence.v1':
            raise EvidenceError('CONTRACT_MISMATCH')
        stamp = p.get('observed_at_epoch')
        if type(stamp) is not int or not 0 <= now - stamp <= self.max_age:
            raise EvidenceError('STALE_OR_FUTURE_EVIDENCE')
        if 'expires_at_epoch' in p:
            expiry = p['expires_at_epoch']
            if type(expiry) is not int or not stamp <= now <= expiry or expiry - stamp > self.max_age:
                raise EvidenceError('EXPIRED_OR_INVALID_LIFETIME')
        if type(p.get('receipt_id')) is not str or not re.fullmatch('[a-zA-Z0-9_-]{1,100}', p['receipt_id']):
            raise EvidenceError('INVALID_RECEIPT_ID')
        return json.loads(raw)

    def verify_bound(self, envelope, *, kind, now, expected):
        """Verify a receipt bound to exact slot/epoch/owner values supplied by ledger.

        Ledger must keep envelope intact and compare all security-critical fields
        through expected. A successful signature alone is never a dispatch permit.
        """
        try:
            p = self.verify(envelope, kind=kind, now=now)
            if type(expected) is not dict or not expected:
                return False
            return all(key in p and type(p[key]) is type(value) and p[key] == value
                       for key, value in expected.items())
        except EvidenceError:
            return False


def host_admission(consumer, envelope, *, now):
    try:
        p = consumer.verify(envelope, kind='host_readiness', now=now)
        facts = p.get('gates')
        if type(facts) is not dict or set(facts) != set(GATES):
            raise EvidenceError('INVALID_GATES')
        reasons = list(readiness(dict(facts, inventory_id=INVENTORY)))
        egress = p.get('egress')
        if type(egress) is not dict or egress.get('mode') != 'approved_noninteractive':
            reasons.append('NONINTERACTIVE_EGRESS_NOT_PROVEN')
        elif (egress.get('target_principal_id') != p['principal_id'] or
              egress.get('dns_tls_proxy_probe_ok') is not True or
              egress.get('interactive_session_required') is not False):
            reasons.append('NONINTERACTIVE_EGRESS_NOT_PROVEN')
        # No runtime toggle can grant production execution in this release.
        reasons.append('FORMAL_EXECUTION_ADAPTER_NOT_INSTALLED')
        return {'allow_dispatch': False, 'exit_code': 78, 'reasons': reasons}
    except EvidenceError as exc:
        return {'allow_dispatch': False, 'exit_code': 78, 'reasons': [str(exc)]}


def bridge_acceptance(consumer, envelopes, *, now):
    result = dict.fromkeys(('HKCU_RUN_CONFIGURED', 'CROSS_CALL_VERIFIED',
                           'CROSS_LOGON_VERIFIED', 'NO_LOGIN_BOOT_VERIFIED'), 'NOT_VERIFIED')
    result['reason'] = 'INSUFFICIENT_EVIDENCE'
    try:
        if type(envelopes) not in (list, tuple) or len(envelopes) != 2:
            raise EvidenceError('INDEPENDENT_RECEIPTS_REQUIRED')
        rows = [consumer.verify(e, kind='bridge_observation', now=now) for e in envelopes]
        if len(rows) != 2 or rows[0]['receipt_id'] == rows[1]['receipt_id']:
            raise EvidenceError('INDEPENDENT_RECEIPTS_REQUIRED')
        if rows[0]['source_id'] != rows[1]['source_id']:
            raise EvidenceError('SOURCE_CHANGED')
        for row in rows:
            if row.get('method') != 'POST' or row.get('endpoint') != 'health':
                raise EvidenceError('WRONG_PROBE_CONTRACT')
        verdict = classify_pair(rows[0], rows[1])
        if rows[1].get('hkcu_run_verified') is True:
            result['HKCU_RUN_CONFIGURED'] = 'VERIFIED_AT_OBSERVATION'
        if verdict == 'SAME_SESSION_TWO_CALLS_OBSERVED':
            result['CROSS_CALL_VERIFIED'] = 'VERIFIED_AT_OBSERVATION'
        result['reason'] = verdict
    except EvidenceError as exc:
        result['reason'] = str(exc)
    return result


def runtime_file_check(path, expected_sha256):
    """Read-only approved local runtime check, no execution and no path echo."""
    if type(expected_sha256) is not str or not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        return 'INVALID_EXPECTED_HASH'
    try:
        target = Path(path)
        if not target.is_absolute() or not target.is_file():
            return 'RUNTIME_NOT_FOUND'
        with target.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        return 'RUNTIME_HASH_MATCH' if digest == expected_sha256 else 'RUNTIME_HASH_MISMATCH'
    except (OSError, ValueError, TypeError):
        return 'RUNTIME_UNREADABLE'


def main():
    # Offline candidate action never reads credentials, contacts a source or runs Inventory.
    print(json.dumps({'allow_dispatch': False, 'exit_code': 78,
                      'reasons': ['TRUST_PROVISIONING_REQUIRED', 'FORMAL_EXECUTION_ADAPTER_NOT_INSTALLED']}))
    return 78


if __name__ == '__main__':
    raise SystemExit(main())

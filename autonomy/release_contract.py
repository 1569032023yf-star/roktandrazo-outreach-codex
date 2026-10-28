"""Offline compatibility contract consumption; never installation or dispatch.

Expected fingerprints must come from the separately approved release plan, not
from the envelope under examination. Signatures authenticate the collector only.
Live exclusion, backups and safety windows must be checked by the formal deployer.
"""
import re

from autonomy.host_preparation import EvidenceError
from autonomy.unattended_policy import INVENTORY

BINDINGS = frozenset(('principal_id', 'inventory_id', 'source_commit',
    'package_sha256', 'backend_id', 'exclusive_lock_id', 'runtime_sha256',
    'publisher_sha256', 'ledger_schema', 'files'))
CAPABILITIES = ('single_inventory_only', 'idempotent_dispatch',
    'durable_operation_receipts', 'hard_deadline_and_cancel',
    'drain_reconciliation', 'sole_lock_binding', 'noninteractive_identity',
    'approved_noninteractive_egress', 'sqlite_deserialize', 'timezone_data',
    'atomic_new_file_install', 'new_file_backup_or_absence_record',
    'new_file_removal_rollback', 'preserve_current_ledgers',
    'old_executor_reads_current_ledger', 'dependency_fingerprints_verified')


def _hex(value, size):
    return type(value) is str and re.fullmatch('[0-9a-f]{%d}' % size, value) is not None


def _valid_context(expected):
    if type(expected) is not dict or set(expected) != BINDINGS:
        return False
    if expected['inventory_id'] != INVENTORY or type(expected['inventory_id']) is not str:
        return False
    if not _hex(expected['source_commit'], 40):
        return False
    if any(not _hex(expected[k], 64) for k in
           ('package_sha256', 'runtime_sha256', 'publisher_sha256')):
        return False
    if type(expected['ledger_schema']) is not int or expected['ledger_schema'] < 1:
        return False
    for key in ('principal_id', 'backend_id', 'exclusive_lock_id'):
        if type(expected[key]) is not str or re.fullmatch('[A-Za-z0-9_-]{1,100}', expected[key]) is None:
            return False
    files = expected['files']
    if type(files) is not list or not 1 <= len(files) <= 100:
        return False
    paths = set()
    for entry in files:
        if type(entry) is not dict or set(entry) != {'path', 'source_sha256', 'target_sha256'}:
            return False
        path = entry['path']
        # Canonical relative paths only, including Windows case-fold collisions.
        if (type(path) is not str or len(path) > 240 or
                re.fullmatch('[A-Za-z0-9_./-]+', path) is None or
                any(part in ('', '.', '..') or part.endswith('.') for part in path.split('/'))):
            return False
        if path.casefold() in paths:
            return False
        for part in path.split('/'):
            stem = part.split('.')[0].upper()
            if stem in {'CON', 'PRN', 'AUX', 'NUL'} or re.fullmatch('(COM|LPT)[1-9]', stem):
                return False
        folded = path.casefold()
        if any(folded.startswith(old + '/') or old.startswith(folded + '/') for old in paths):
            return False
        paths.add(path.casefold())
        if not _hex(entry['source_sha256'], 64):
            return False
        if entry['target_sha256'] != 'ABSENT' and not _hex(entry['target_sha256'], 64):
            return False
    return True


def inspect_release_contract(consumer, envelope, *, now, expected):
    """Admit a compatibility plan only; no return value grants execution rights."""
    denied = dict(compatible=False, allow_install=False, allow_dispatch=False,
                  reason='INVALID_APPROVED_CONTEXT')
    if not _valid_context(expected):
        return denied
    try:
        payload = consumer.verify(envelope, kind='release_compatibility', now=now)
    except EvidenceError:
        return dict(denied, reason='UNVERIFIED_CONTRACT')
    if any(key not in payload or type(payload[key]) is not type(value) or payload[key] != value
           for key, value in expected.items()):
        return dict(denied, reason='APPROVED_CONTEXT_MISMATCH')
    facts = payload.get('capabilities')
    if type(facts) is not dict or set(facts) != set(CAPABILITIES):
        return dict(denied, reason='INCOMPLETE_CAPABILITY_CONTRACT')
    if any(facts[key] is not True for key in CAPABILITIES):
        return dict(denied, reason='UNSUPPORTED_OR_UNKNOWN_CAPABILITY')
    return dict(denied, compatible=True, reason='COMPATIBILITY_PLAN_ONLY')

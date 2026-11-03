"""Offline classification of already authenticated, redacted observations.

Not a probe, authentication verifier, or proof of continuous availability.
Session identifiers must be opaque per-logon identifiers, not reusable WTS IDs.
"""
from collections.abc import Mapping


def classify_pair(first, second):
    """Classify two ordered observations; never infer no-login from HKCU Run."""
    for row in (first, second):
        if not isinstance(row, Mapping):
            return 'INVALID_EVIDENCE'
        for key in ('call_id', 'boot_id', 'logon_id', 'principal_id', 'instance_id'):
            if type(row.get(key)) is not str or not row[key].strip():
                return 'INVALID_EVIDENCE'
        if type(row.get('observed_at_epoch')) is not int or row['observed_at_epoch'] < 0:
            return 'INVALID_EVIDENCE'
        if row.get('authenticated') is not True or row.get('post_health_ok') is not True:
            return 'HEALTH_NOT_ACCEPTED'
        if type(row.get('interactive_login_present')) is not bool:
            return 'INVALID_EVIDENCE'
    if first['call_id'] == second['call_id']:
        return 'NOT_INDEPENDENT_CALLS'
    if second['observed_at_epoch'] <= first['observed_at_epoch']:
        return 'NOT_ORDERED'
    if first['principal_id'] != second['principal_id']:
        return 'PRINCIPAL_CHANGED'
    if first['boot_id'] != second['boot_id']:
        # Two successful endpoints alone cannot prove absence of login between them.
        return 'REBOOT_ENDPOINTS_ONLY'
    if first['logon_id'] != second['logon_id']:
        return 'CROSS_LOGON_ENDPOINTS_ONLY'
    if first['instance_id'] != second['instance_id']:
        return 'PROCESS_RESTARTED'
    if first['interactive_login_present'] is not second['interactive_login_present']:
        return 'LOGIN_STATE_CHANGED'
    return 'SAME_SESSION_TWO_CALLS_OBSERVED'

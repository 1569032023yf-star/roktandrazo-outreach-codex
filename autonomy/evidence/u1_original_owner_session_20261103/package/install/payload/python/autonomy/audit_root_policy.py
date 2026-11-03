"""Conservative offline evaluation of a read-only Windows audit-root snapshot.

Snapshot agreement is not a trusted handle, live ACL guarantee or installation
authority. No filesystem/ACL operations are performed by this policy.
"""
import ntpath

SCHEMA = 'rokt.install-audit-root-observation.v1'
ROOT = r'C:\ProgramData\RoktU1InstallAudit'
CHAIN = ('C:\\', r'C:\ProgramData', ROOT)
TRUSTED_WRITERS = {'S-1-5-18', 'S-1-5-32-544'}
FULL_CONTROL = 0x1F01FF
ROOT_WRITE = 0xD0156
ANCESTOR_REPLACE = 0xD0040


def evaluate_audit_root(snapshot):
    """Reject incomplete facts and permissive ACLs without changing either."""
    reason = 'INVALID_OBSERVATION'
    try:
        if type(snapshot) is not dict or snapshot['schema'] != SCHEMA:
            raise ValueError(reason)
        nodes = snapshot['nodes']
        if type(nodes) is not list or len(nodes) != len(CHAIN):
            raise ValueError('INCOMPLETE_ANCESTOR_CHAIN')
        for index, (node, expected) in enumerate(zip(nodes, CHAIN)):
            if ntpath.normcase(node['path']) != ntpath.normcase(expected):
                raise ValueError('WRONG_PATH')
            if node['exists'] is not True or node['directory'] is not True:
                raise ValueError('ABSENT_OR_NOT_DIRECTORY')
            if node['reparse_point'] is not False:
                raise ValueError('REPARSE_OR_UNKNOWN')
            is_root = index == len(CHAIN) - 1
            # An owner can replace the DACL even without an allow-write ACE.
            # Other platform owners require a separately reviewed policy.
            if node['owner_sid'] not in TRUSTED_WRITERS:
                raise ValueError('UNTRUSTED_OWNER')
            if is_root and (node['protected'] is not True or node['owner_sid'] not in TRUSTED_WRITERS):
                raise ValueError('UNPROTECTED_ROOT_OR_OWNER')
            aces = node['aces']
            if type(aces) is not list or not aces:
                raise ValueError('MISSING_DACL')
            full = set()
            for ace in aces:
                rights = ace['rights']
                if (type(rights) is not int or not 0 <= rights <= FULL_CONTROL
                        or type(ace['inherit_only']) is not bool
                        or ace['type'] not in ('Allow', 'Deny')
                        or type(ace['sid']) is not str):
                    raise ValueError('UNKNOWN_ACE')
                # Root inherit-only write grants also threaten child journals.
                if not is_root and ace['inherit_only']:
                    continue
                if ace['type'] == 'Deny':
                    raise ValueError('DENY_REQUIRES_EFFECTIVE_ACCESS_REVIEW')
                if ace['sid'] not in TRUSTED_WRITERS and rights & (ROOT_WRITE if is_root else ANCESTOR_REPLACE):
                    raise ValueError('UNTRUSTED_WRITE_OR_REPLACE')
                if not ace['inherit_only'] and rights & FULL_CONTROL == FULL_CONTROL:
                    full.add(ace['sid'])
            if is_root and not TRUSTED_WRITERS <= full:
                raise ValueError('ADMIN_SYSTEM_FULL_CONTROL_REQUIRED')
        reason = 'SNAPSHOT_POLICY_MATCH_ONLY'
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError):
            reason = str(exc)
    return dict(snapshot_policy_match=reason == 'SNAPSHOT_POLICY_MATCH_ONLY',
                reason=reason, trusted_handle_verified=False,
                allow_install=False, allow_dispatch=False, production_execution=False)

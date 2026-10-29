"""Offline, fail-closed host candidate verifier. No OS, network or install API."""
import re
from autonomy.host_preparation import EvidenceError
from autonomy.unattended_policy import INVENTORY

SERVICE = 'RoktU1Bridge'
ROOT = r'C:\Program Files\RoktU1Bridge\v1'
STATE = r'C:\ProgramData\RoktU1Bridge'
GATES = (
    'service_logon_right', 'service_acl_verified', 'code_read_execute_only',
    'credentials_acl_verified', 'token_available', 'outside_agent_job',
    'audit_durable', 'heartbeat_durable', 'health_authenticated',
    'recovery_bounded', 'no_customer_db_access', 'no_arbitrary_commands',
    'single_inventory_only', 'lock_run_firing_bound', 'unknown_no_replay',
    'preserve_budget_slot_cancel_journal', 'protocol_exact_match',
    'publisher_compatible', 'proxy_headless_approved', 'provider_egress',
    'dns_mx_fail_closed', 'proxy_error_fail_closed', 'smtp_disabled',
    'kill_host_reconciled', 'logoff_verified', 'reboot_verified',
    'lost_receipt_reconciled', 'proxy_down_rejected',
    'expired_credential_rejected', 'service_restart_reconciled',
    'two_natural_inventory_cycles',
)
CONFIG = dict(
    service_name=SERVICE, account=r'NT SERVICE\RoktU1Bridge',
    start_type='disabled', listener='127.0.0.1:8791',
    code_root=ROOT, state_root=STATE,
    executable=ROOT + r'\service\RoktU1Bridge.exe',
    runtime=ROOT + r'\runtime\python.exe',
    credentials=STATE + r'\secrets\bridge-token',
    inventory_id=INVENTORY, scheduler_created=False,
    allow_dispatch=False, allow_cancel_dispatch=False,
    operations=['health', 'status', 'reconcile_existing_operation'],
    network_mode='approved_headless_service',
    rollback='disable_new_service_preserve_all_durable_state',
)
BINDINGS = ('source_commit', 'package_sha256', 'runtime_sha256',
            'service_wrapper_sha256', 'publisher_sha256', 'config_sha256',
            'principal_id', 'exclusive_lock_id', 'backend_protocol',
            'approved_proxy_id')


def inspect_host_candidate(consumer, envelope, *, now, expected):
    """Check separately approved immutable bindings; never grant installation.

    A caller-supplied manifest cannot authorize itself. Trust and expected values
    must be provisioned by the existing formal publisher outside this envelope.
    Tests with synthetic signatures prove rejection mechanics, not OS facts.
    """
    denied = dict(compatible=False, allow_install=False, allow_start=False,
                  allow_dispatch=False, allow_cancel_dispatch=False,
                  production_accepted=False, reason='INVALID_APPROVED_CONTEXT',
                  missing_gates=list(GATES))
    if type(expected) is not dict or set(expected) != set(BINDINGS):
        return denied
    for key in BINDINGS:
        value = expected[key]
        pattern = ('[0-9a-f]{40}' if key == 'source_commit' else
                   '[0-9a-f]{64}' if key.endswith('sha256') else
                   '[A-Za-z0-9_.:-]{1,100}')
        if type(value) is not str or re.fullmatch(pattern, value) is None:
            return denied
    if expected['backend_protocol'] != 'rokt.offline-backend.v1':
        return dict(denied, reason='BACKEND_PROTOCOL_MISMATCH')
    try:
        payload = consumer.verify(envelope, kind='host_remediation', now=now)
    except EvidenceError:
        return dict(denied, reason='UNVERIFIED_CONTRACT')
    if any(type(payload.get(k)) is not type(v) or payload.get(k) != v
           for k, v in expected.items()):
        return dict(denied, reason='APPROVED_CONTEXT_MISMATCH')
    config = payload.get('config')
    if type(config) is not dict or set(config) != set(CONFIG) or any(
            type(config[k]) is not type(v) or config[k] != v
            for k, v in CONFIG.items()):
        return dict(denied, reason='UNSAFE_SERVICE_CONFIG')
    # Bind the actual config bytes as well as the signed expected fingerprint.
    import hashlib
    from autonomy.host_preparation import canonical
    if hashlib.sha256(canonical(config)).hexdigest() != expected['config_sha256']:
        return dict(denied, reason='CONFIG_HASH_MISMATCH')
    facts = payload.get('gates')
    if type(facts) is not dict or set(facts) != set(GATES):
        return dict(denied, reason='INVALID_GATES')
    missing = [key for key in GATES if facts[key] is not True]
    return dict(denied, compatible=not missing,
                reason='EVIDENCE_COMPATIBLE_OFFLINE_ONLY' if not missing else 'GATES_PENDING',
                missing_gates=missing)

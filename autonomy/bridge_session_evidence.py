"""Offline aggregation of authenticated bridge/config/OS-event observations.

No probe, OS access, persistence, service creation or production authorization.
Completeness is an assertion of the independently provisioned trusted collector;
a valid signature does not itself establish collector correctness.
"""
import hashlib
import re
from autonomy.host_preparation import EvidenceError, canonical
from autonomy.bridge_acceptance import classify_pair


FIELDS = ('HKCU_RUN_CONFIGURED', 'CROSS_CALL_VERIFIED',
          'CROSS_LOGON_VERIFIED', 'NO_LOGIN_BOOT_VERIFIED')


def _require(condition, code):
    if not condition:
        raise EvidenceError(code)


def _identifier(value):
    return type(value) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value) is not None


def aggregate(consumer, configuration, observations, event_window, *, now):
    """Return four observation-scoped statuses, never a combined healthy flag.

    Re-signed receipts for the same observation pair retain acceptance_id.
    A caller counting accepted cycles must deduplicate acceptance_id, not the
    transport evidence digest. Endpoint recovery is not continuous availability.
"""
    result = dict.fromkeys(FIELDS, 'NOT_VERIFIED')
    result.update(reason='INSUFFICIENT_EVIDENCE', evidence_digest=None,
                  acceptance_id=None, PROCESS_OBSERVATION='NOT_VERIFIED')
    try:
        config = consumer.verify(configuration, kind='bridge_configuration', now=now)
        config_id = config.get('configuration_id')
        _require(type(config_id) is str and re.fullmatch('[0-9a-f]{64}', config_id), 'CONFIG_ID_INVALID')
        _require(_identifier(config.get('bridge_principal_id')), 'BRIDGE_IDENTITY_INVALID')
        _require(type(config.get('hkcu_run_verified')) is bool, 'CONFIG_CONTRACT_INVALID')
        if config['hkcu_run_verified']:
            result['HKCU_RUN_CONFIGURED'] = 'VERIFIED_AT_OBSERVATION'
        _require(type(observations) in (list, tuple) and len(observations) == 2, 'TWO_PROBES_REQUIRED')
        rows = [consumer.verify(e, kind='bridge_observation', now=now) for e in observations]
        all_rows = [config, *rows]
        _require(len({r['receipt_id'] for r in all_rows}) == 3, 'DUPLICATE_RECEIPT')
        for row in rows:
            _require(all(row.get(k) == config.get(k) for k in
                         ('source_id', 'principal_id', 'configuration_id', 'bridge_principal_id')), 'BINDING_MISMATCH')
            _require(row.get('method') == 'POST' and row.get('endpoint') == 'health', 'WRONG_PROBE_CONTRACT')
            _require(config['observed_at_epoch'] <= row['observed_at_epoch'], 'CONFIG_AFTER_PROBE')
        verdict = classify_pair(*rows)
        result['reason'] = verdict
        if verdict == 'SAME_SESSION_TWO_CALLS_OBSERVED':
            result['CROSS_CALL_VERIFIED'] = 'VERIFIED_AT_OBSERVATION'
        _require(verdict in ('SAME_SESSION_TWO_CALLS_OBSERVED', 'CROSS_LOGON_ENDPOINTS_ONLY'), 'PROBE_CHAIN_NOT_ACCEPTED')
        identity = dict(configuration_id=config_id, bridge_principal_id=config['bridge_principal_id'],
            probes=[{k:r[k] for k in ('boot_id','call_id','observed_at_epoch','logon_id','instance_id')} for r in rows])
        result['acceptance_id'] = hashlib.sha256(canonical(identity)).hexdigest()
        result['PROCESS_OBSERVATION'] = ('SAME_INSTANCE_ENDPOINTS' if rows[0]['instance_id'] == rows[1]['instance_id']
                                         else 'DIFFERENT_INSTANCE_ENDPOINTS')
        window = consumer.verify(event_window, kind='bridge_os_event_window', now=now)
        _require(window['receipt_id'] not in {r['receipt_id'] for r in all_rows}, 'DUPLICATE_RECEIPT')
        _require(all(window.get(k) == config.get(k) for k in
                     ('source_id', 'principal_id', 'configuration_id', 'bridge_principal_id')), 'BINDING_MISMATCH')
        _require(window.get('boot_id') == rows[0]['boot_id'] == rows[1]['boot_id'], 'BOOT_BINDING_MISMATCH')
        start, end = window.get('coverage_from'), window.get('coverage_to')
        _require(type(start) is int and type(end) is int and
                 0 <= start <= rows[0]['observed_at_epoch'] < rows[1]['observed_at_epoch'] <= end <= window['observed_at_epoch'], 'COVERAGE_GAP')
        _require(window.get('complete') is True and window.get('gaps_detected') is False and
                 window.get('all_interactive_sessions_included') is True, 'INCOMPLETE_OS_EVIDENCE')
        events = window.get('events')
        _require(type(events) is list and 0 < len(events) <= 1024, 'EVENT_CONTRACT_INVALID')
        first, last = window.get('first_sequence'), window.get('last_sequence')
        _require(type(first) is int and type(last) is int and first >= 0 and last-first+1 == len(events), 'EVENT_SEQUENCE_GAP')
        previous = start
        for index, event in enumerate(events):
            _require(type(event) is dict and type(event.get('sequence')) is int and event['sequence'] == first+index, 'EVENT_SEQUENCE_GAP')
            stamp = event.get('at_epoch')
            _require(type(stamp) is int and previous <= stamp <= end, 'EVENT_TIME_INVALID')
            previous = stamp
            _require(event.get('type') in ('boot', 'logon', 'logoff', 'coverage_end'), 'UNKNOWN_OS_EVENT')
            if event['type'] in ('logon', 'logoff'):
                _require(_identifier(event.get('logon_id')) and _identifier(event.get('user_id')), 'SESSION_EVENT_INVALID')
        _require(events[-1]['type'] == 'coverage_end' and events[-1]['at_epoch'] == end, 'COVERAGE_END_MISSING')
        result['evidence_digest'] = hashlib.sha256(canonical([config, *rows, window])).hexdigest()
        if verdict == 'CROSS_LOGON_ENDPOINTS_ONLY':
            between = [e for e in events if rows[0]['observed_at_epoch'] < e['at_epoch'] < rows[1]['observed_at_epoch']]
            old = [e for e in between if e['type'] == 'logoff' and e['logon_id'] == rows[0]['logon_id']]
            new = [e for e in between if e['type'] == 'logon' and e['logon_id'] == rows[1]['logon_id']]
            _require(len(old) == len(new) == 1 and old[0]['at_epoch'] < new[0]['at_epoch'] and
                     old[0]['user_id'] == new[0]['user_id'] and
                     all(r['interactive_login_present'] is True for r in rows), 'LOGON_CHAIN_NOT_PROVEN')
            closed_interval = [e for e in events if rows[0]['observed_at_epoch'] <= e['at_epoch'] <= rows[1]['observed_at_epoch']]
            relevant = [e for e in closed_interval if e.get('logon_id') in (rows[0]['logon_id'], rows[1]['logon_id'])]
            _require(relevant == [old[0], new[0]], 'SESSION_LIFECYCLE_CONFLICT')
            _require(not any(e['type'] == 'boot' for e in closed_interval), 'BOOT_WITHIN_LOGON_CHAIN')
            result['CROSS_LOGON_VERIFIED'] = 'VERIFIED_AT_OBSERVATION'
            result['reason'] = 'SIGNED_NORMAL_RELOGON_OBSERVED'
        else:
            boot = events[0]
            if (config.get('startup_mode') == 'machine_boot' and config.get('interactive_session_required') is False and
                    window.get('initial_interactive_sessions') == 0 and type(window.get('initial_interactive_sessions')) is int and
                    boot['type'] == 'boot' and boot['at_epoch'] == start and
                    all(e['type'] == 'coverage_end' for e in events[1:]) and
                    all(r['interactive_login_present'] is False for r in rows)):
                result['NO_LOGIN_BOOT_VERIFIED'] = 'VERIFIED_AT_OBSERVATION'
                result['reason'] = 'SIGNED_BOOT_WITHOUT_INTERACTIVE_LOGIN_OBSERVED'
        return result
    except (EvidenceError, TypeError, KeyError, ValueError):
        # No untrusted source strings, URLs or raw OS payloads escape the consumer.
        result['reason'] = 'EVIDENCE_NOT_ACCEPTED'
        return result

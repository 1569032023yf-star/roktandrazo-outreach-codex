"""Pure bounded recovery decisions / 纯函数有界恢复决策。

No networking, sleeping, shell, credentials or production imports. Callers keep
the actual transport and its authorization boundary. 不执行请求、睡眠或命令。
"""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import math
import re

READ_ONLY_OPERATIONS = frozenset({
    'health', 'telemetry', 'status', 'runtime', 'city', 'provider-audit',
    'scheduler', 'safe', 'releases', 'github-fetch', 'github-head',
})
MUTATIONS = frozenset({'register', 'apply', 'rollback', 'github-push'})
TRANSIENT = frozenset({'NETWORK_TIMEOUT', 'PROXY_UNAVAILABLE',
    'REMOTE_CONNECTION_RESET', 'DNS_FAILURE', 'HTTP_429_RATE_LIMIT'})
CODES = TRANSIENT | {'AUTH_FAILED', 'SOURCE_POLICY_BLOCKED', 'GITHUB_CONFLICT',
    'UNKNOWN_SIDE_EFFECT', 'UNKNOWN_NETWORK_FAILURE'}


def utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('AWARE_TIME_REQUIRED')
    return value.astimezone(timezone.utc)


def classify_failure(*, error_code=None, http_status=None, policy_blocked=False):
    """Only fixed codes are retained; arbitrary exception text is never saved."""
    if type(policy_blocked) is not bool:
        raise ValueError('INVALID_POLICY_FLAG')
    if policy_blocked:
        return 'SOURCE_POLICY_BLOCKED'
    if http_status in (401, 403):
        return 'AUTH_FAILED'
    if http_status == 429:
        return 'HTTP_429_RATE_LIMIT'
    if http_status == 409:
        return 'GITHUB_CONFLICT'
    return error_code if error_code in CODES else 'UNKNOWN_NETWORK_FAILURE'


def _retry_after(value, now):
    if value is None:
        return 0.0
    if type(value) in (int, float) and math.isfinite(value) and value >= 0:
        return float(value)
    if isinstance(value, str):
        try:
            seconds = float(value)
            if math.isfinite(seconds) and seconds >= 0:
                return seconds
        except ValueError:
            pass
        try:
            return max(0.0, (utc(parsedate_to_datetime(value)) - now).total_seconds())
        except (ValueError, TypeError, OverflowError):
            pass
    raise ValueError('INVALID_RETRY_AFTER')


def recovery_plan(*, operation, error_code, attempt_count, now,
                  max_attempts=4, base_seconds=15, max_seconds=900,
                  jitter=0.5, retry_after=None, outcome_unknown=False):
    """Return a schedule, never execute it / 只返回计划，不执行重试。

    attempt_count counts completed transport attempts in this budget. A budget
    exhausted task remains deferred until a separate verified event starts a
    new budget. Mutation outcomes are never replayed by this policy.
    """
    now = utc(now)
    if operation not in READ_ONLY_OPERATIONS | MUTATIONS:
        raise ValueError('UNSUPPORTED_OPERATION')
    if error_code not in CODES or type(outcome_unknown) is not bool:
        raise ValueError('INVALID_RECOVERY_CLASSIFICATION')
    if type(attempt_count) is not int or not 1 <= attempt_count <= 2**31 - 1:
        raise ValueError('INVALID_ATTEMPT_COUNT')
    if type(max_attempts) is not int or not 1 <= max_attempts <= 8:
        raise ValueError('INVALID_RETRY_BUDGET')
    for value in (base_seconds, max_seconds, jitter):
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('INVALID_BACKOFF')
    if not 0 < base_seconds <= max_seconds <= 86400 or not 0 <= jitter <= 1:
        raise ValueError('INVALID_BACKOFF')
    result = {'operation': operation, 'last_error': error_code,
              'attempt_count': attempt_count, 'next_retry_at': None,
              'automatic_replay': False, 'budget_exhausted': False}
    if outcome_unknown or error_code == 'UNKNOWN_SIDE_EFFECT':
        result.update(action='RECONCILE_STATUS', blocked_reason='UNKNOWN_SIDE_EFFECT',
                      next_action='Read official status/audit by operation_id before any new decision.')
    elif operation in MUTATIONS:
        result.update(action='RECONCILE_STATUS', blocked_reason='MUTATION_NOT_REPLAYABLE',
                      next_action='Inspect official status or remote HEAD; never retry this mutation automatically.')
    elif error_code in {'AUTH_FAILED', 'SOURCE_POLICY_BLOCKED', 'GITHUB_CONFLICT', 'UNKNOWN_NETWORK_FAILURE'}:
        result.update(action='BLOCKED', blocked_reason=error_code,
                      next_action='Await a verified authorization, policy or conflict resolution; do not rotate credentials or bypass policy.')
    else:
        delay = min(max_seconds, base_seconds * 2 ** min(attempt_count - 1, 8))
        # Add positive jitter so neither the exponential delay nor Retry-After
        # can be shortened by a negative random draw.
        delay = max(min(max_seconds, delay * (1 + 0.25 * jitter)),
                    _retry_after(retry_after, now))
        if delay > 366 * 86400:
            raise ValueError('RETRY_AFTER_OUT_OF_RANGE')
        result.update(action='READ_ONLY_RETRY' if attempt_count < max_attempts else 'DEFERRED',
                      blocked_reason=None if attempt_count < max_attempts else 'RETRY_BUDGET_EXHAUSTED',
                      budget_exhausted=attempt_count >= max_attempts,
                      next_retry_at=(now + timedelta(seconds=delay)).isoformat(),
                      automatic_replay=attempt_count < max_attempts,
                      next_action='Retry the same approved read-only operation when due.' if attempt_count < max_attempts else
                      'Persist task; wait for a verified dependency-change event before granting another retry budget.')
    return result


def git_sync_plan(*, target_commit, remote_head, remote_is_ancestor=None):
    """Plan only. An allowed push is not proof of success / 允许推送不等于成功。

    remote_is_ancestor must come from a successful local merge-base check after
    an authenticated fetch. No force push or merge is executed here.
    """
    for value in (target_commit, remote_head):
        if value is not None and (type(value) is not str or not re.fullmatch(r'[0-9a-f]{40}', value)):
            raise ValueError('INVALID_GIT_SHA')
    if target_commit is None or (remote_is_ancestor is not None and type(remote_is_ancestor) is not bool):
        raise ValueError('INVALID_GIT_EVIDENCE')
    if remote_head == target_commit:
        return {'action': 'VERIFIED', 'push_success': True, 'force': False}
    if remote_head is None or remote_is_ancestor is None:
        return {'action': 'FETCH_AND_RECONCILE', 'push_success': False, 'force': False}
    if remote_is_ancestor is True:
        return {'action': 'PUSH_FAST_FORWARD_THEN_VERIFY', 'push_success': False, 'force': False}
    return {'action': 'CONFLICT_REQUIRES_RECONCILIATION', 'push_success': False, 'force': False}

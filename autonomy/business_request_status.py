"""Read-only business request projection of existing authenticated ledgers.

查询现有账本，不创建请求、不恢复执行、不推断 Provider 货币费用。
The existing owner must remain held. Resource units are not billed money.
"""
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from autonomy.growth_ledger import SCHEMA, SCHEMA_VERSION, GrowthError, digest, opaque, vector
from autonomy.drain_bundle_preflight import SLOT_SCHEMA
from autonomy.single_slot_adapter import AdapterError, SingleSlotAdapter
from autonomy.unattended_policy import INVENTORY


def request_status(adapter, admission):
    _, common = adapter._admission(admission, require_backend=False)
    opaque(common['request_id'])
    expected = dict(inventory_id=INVENTORY, **common)
    try:
        # Both handles are read-only: a missing ledger cannot be recreated.
        # The existing exclusive owner, checked before/after this read, remains
        # the cross-ledger guard; this does not claim cross-file atomic writes.
        with closing(sqlite3.connect(Path(adapter.slots.path).resolve().as_uri()+'?mode=ro',
                                     uri=True, isolation_level=None)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('ATTACH DATABASE ? AS budget',
                         (Path(adapter.budget.path).resolve().as_uri()+'?mode=ro',))
            conn.execute('PRAGMA query_only=ON')
            conn.execute('PRAGMA trusted_schema=OFF')
            conn.execute('BEGIN')
            for database, schema, version in (('main', SLOT_SCHEMA, 0),
                                               ('budget', SCHEMA, SCHEMA_VERSION)):
                objects = conn.execute(
                    f"SELECT type,sql FROM {database}.sqlite_master WHERE name NOT GLOB 'sqlite_*'").fetchall()
                if (conn.execute(f'PRAGMA {database}.user_version').fetchone()[0] != version
                        or len(objects) != len(schema)
                        or any(row['type'] != 'table' or row['sql'] is None for row in objects)
                        or {row['sql'].lower() for row in objects} != {sql.lower() for sql in schema}):
                    raise AdapterError('REQUEST_STATUS_SCHEMA_REJECTED')
            authority = conn.execute('SELECT epoch,owner FROM authority WHERE singleton=1').fetchone()
            if authority is None or tuple(authority) != (common['epoch'], common['owner']):
                raise AdapterError('REQUEST_STATUS_AUTHORITY_CONFLICT')
            slot = conn.execute('SELECT * FROM slots WHERE slot=?', (common['slot'],)).fetchone()
            reservation = conn.execute('SELECT * FROM budget.reservations WHERE id=?',
                                       (common['request_id'],)).fetchone()
            result = _project(adapter, common, expected, slot, reservation)
            adapter._lock()
            conn.rollback()
            return result
    except (sqlite3.Error, OSError):
        raise AdapterError('REQUEST_STATUS_STORAGE_UNAVAILABLE') from None


def _project(adapter, common, expected, slot, reservation):
    result = dict(schema='rokt.offline-business-request-status.v1',
                  request_id=common['request_id'], run_id=common['run_id'],
                  business_state='UNKNOWN_RECONCILE_ONLY', slot_state='NOT_RECORDED',
                  resource_budget=None,
                  provider_billing=dict(status='CONTRACT_MISSING', billed_amount=None,
                                        currency=None, evidence_reference=None),
                  replay_authorized=False, allow_dispatch=False,
                  allow_cancel_dispatch=False, production_execution=False)
    token = None
    if slot is not None:
        state = slot['state']
        if slot['inventory'] != INVENTORY or state not in (
                'pending', 'deferred', 'claimed', 'running', 'unknown', 'completed', 'failed'):
            raise AdapterError('REQUEST_STATUS_SLOT_CONFLICT')
        token = slot['token']
        if state in ('pending', 'deferred'):
            if token is not None or slot['epoch'] is not None or slot['owner'] is not None:
                raise AdapterError('REQUEST_STATUS_SLOT_CONFLICT')
        elif (type(slot['epoch']) is not int or slot['epoch'] != common['epoch']
              or slot['owner'] != common['owner'] or type(token) is not str or not token):
            raise AdapterError('REQUEST_STATUS_CLAIM_CONFLICT')
        result['slot_state'] = state.upper()
    if reservation is None:
        # An original owner can persist an event intent before either ledger
        # receives a row.  An admission alone cannot identify that event.
        # Unknown adapter subclasses may hold other unobserved authorities too.
        if slot is None and type(adapter) is SingleSlotAdapter:
            result['business_state'] = 'NOT_RECORDED'
        # A scheduled slot has no request ID. It cannot establish that this
        # specific request was recorded, even if the slot is pending/deferred.
        return result

    try:
        binding = json.loads(reservation['binding'])
        if (reservation['run'] != common['run_id'] or binding != expected
                or any(type(binding[k]) is not type(v) for k, v in expected.items())):
            raise AdapterError('REQUEST_STATUS_BUDGET_CONFLICT')
        reserved = vector(json.loads(reservation['amount']))
        charged = vector(json.loads(reservation['charged']))
        state = reservation['state']
        if state not in ('reserved', 'unknown', 'settled', 'overrun'):
            raise AdapterError('REQUEST_STATUS_BUDGET_CONFLICT')
        claim_hash = reservation['claim_hash']
        if claim_hash is not None:
            opaque(claim_hash)
        if token is not None and claim_hash is not None and claim_hash != digest(token):
            raise AdapterError('REQUEST_STATUS_CLAIM_CONFLICT')
        # A lost claim acknowledgement is deliberately queryable as UNKNOWN.
        # Neither an unmatched claim nor a terminal slot proves settlement.
        joined = token is not None and claim_hash == digest(token)
        if joined and hasattr(adapter, 'original_owner'):
            adapter.original_owner.receipt_binding(dict(common, claim_token_hash=claim_hash))
        receipt_hash = reservation['receipt_hash']
        if receipt_hash is not None:
            opaque(receipt_hash)
        if state in ('settled', 'overrun') and (receipt_hash is None or claim_hash is None):
            raise AdapterError('REQUEST_STATUS_SETTLEMENT_CONFLICT')
        overrun = any(charged[k] > reserved[k] for k in reserved)
        if ((state in ('reserved', 'unknown') and charged != reserved)
                or (state == 'settled' and overrun) or (state == 'overrun' and not overrun)):
            raise AdapterError('REQUEST_STATUS_ACCOUNTING_CONFLICT')
        result['resource_budget'] = dict(state=state.upper(), reserved=reserved,
            charged=charged, actual=charged if state in ('settled', 'overrun') else None,
            receipt_digest=receipt_hash)
        if (joined and state == 'settled' and slot['state'] in ('completed', 'failed')
                and type(slot['receipt']) is str and slot['receipt']):
            opaque(slot['receipt'])
            result['business_state'] = slot['state'].upper()
    except (GrowthError, ValueError, TypeError, KeyError):
        raise AdapterError('REQUEST_STATUS_RECORD_REJECTED') from None
    return result

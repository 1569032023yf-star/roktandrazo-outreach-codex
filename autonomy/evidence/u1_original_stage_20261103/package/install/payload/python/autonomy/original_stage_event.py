"""Fixed original-stage consumer; no acquisition, scheduler or dispatch grant.

The original owner acquires its existing DB lock before approved evidence can
bind that fresh incarnation. This object carries that already-held authority
into the original stage; it never falls back to reacquisition or the old body.
The current signed execution protocol remains isolated_offline.
"""
from contextlib import closing
import json

from autonomy.inventory_event_bridge import ExistingOwnerBridge
from autonomy.original_inventory_owner import _session, _binding
from autonomy.release_store import canonical
from autonomy.single_slot_adapter import OriginalOwnerSlotAdapter


class OriginalStageEvent:
    def __init__(self, bridge, event, *, captured_owner):
        if (type(bridge) is not ExistingOwnerBridge or
                type(bridge.adapter) is not OriginalOwnerSlotAdapter or
                type(captured_owner) is not dict or
                captured_owner != bridge.adapter.original_owner.check()):
            raise ValueError('CAPTURED_ORIGINAL_STAGE_OWNER_REQUIRED')
        # Freeze signed bytes. Later mutations of the caller's nested dictionaries
        # cannot replace the approved event after stage-context validation.
        encoded = canonical(event)
        if len(encoded) > 65536:
            raise ValueError('ORIGINAL_STAGE_EVENT_TOO_LARGE')
        self.event = encoded
        self.bridge = bridge
        self.captured_owner = json.loads(canonical(captured_owner))

    def owner_binding(self, connect, run_id, business_date):
        with closing(connect()) as conn:
            conn.execute('BEGIN')
            try:
                session = _session(conn, own_process=True)
                if (session['holder'] != run_id or
                        session['lock_key'] != 'run_lock:daily_outreach:inventory:'+business_date or
                        _binding(session) != self.captured_owner or
                        self.bridge.adapter.original_owner.check() != self.captured_owner):
                    raise ValueError('ORIGINAL_STAGE_CONTEXT_MISMATCH')
                job=conn.execute("SELECT status,dry_run FROM job_runs WHERE run_id=? "
                    "AND stage='inventory' AND business_date=?",(run_id,business_date)).fetchone()
                if job is None or tuple(job) != ('running',0):
                    raise ValueError('ORIGINAL_STAGE_RUNNING_JOB_REQUIRED')
            finally:
                conn.rollback()
        return dict(self.captured_owner)

    def consume(self, connect, run_id, business_date):
        self.owner_binding(connect, run_id, business_date)
        return self.bridge.consume(json.loads(self.event))

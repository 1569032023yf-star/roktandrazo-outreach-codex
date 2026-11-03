"""Pinned subprocess transport for the existing offline admission protocol.
现有离线准入的真实子进程传输；不生成准入、回执或调度，不授权生产。
"""
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
from autonomy.growth_ledger import digest
from autonomy.process_job import run_tree
from autonomy.release_store import ordinary, read_file
from autonomy.single_slot_adapter import BACKEND_PROTOCOL, OPERATION_SCHEMA
from autonomy.unattended_policy import INVENTORY


class ExecutionUnknown(RuntimeError):
    pass


class ProcessBackend:
    protocol_version=BACKEND_PROTOCOL

    def __init__(self, journal, *, python, python_sha256, worker, worker_sha256,
                 backend_id, offline_only=False):
        if offline_only is not True:raise ValueError('OFFLINE_ONLY')
        self.path=ordinary(journal)
        if not self.path.parent.is_dir():raise ValueError('JOURNAL_PARENT_REQUIRED')
        self.python=Path(python);self.worker=Path(worker)
        if not self.python.is_absolute() or not self.worker.is_absolute():raise ValueError('ABSOLUTE_EXECUTABLE_REQUIRED')
        self.hashes=(python_sha256,worker_sha256)
        self.backend_id=backend_id
        self._verify_files()
        with self._db() as c:
            c.execute('CREATE TABLE IF NOT EXISTS executions (key TEXT PRIMARY KEY, binding TEXT NOT NULL, state TEXT NOT NULL, result TEXT)')

    def _verify_files(self):
        for p,h in zip((self.python,self.worker),self.hashes):
            if hashlib.sha256(read_file(p)).hexdigest()!=h:raise ValueError('EXECUTABLE_HASH_MISMATCH')

    def _db(self):
        ordinary(self.path)
        if self.path.exists() and self.path.stat().st_nlink!=1:raise ValueError('JOURNAL_HARDLINK')
        c=sqlite3.connect(self.path,timeout=5,isolation_level=None)
        c.execute('PRAGMA synchronous=FULL')
        return closing(c)

    def status(self, idempotency_key):
        """Read-only transport status; never makes UNKNOWN replayable.
        只读状态，不签发重放、终态或预算退款权限。
        """
        import re
        if type(idempotency_key) is not str or not re.fullmatch('[0-9a-f]{64}',idempotency_key):
            raise ValueError('IDEMPOTENCY_KEY_REJECTED')
        ordinary(self.path)
        if self.path.stat().st_nlink!=1:raise ValueError('JOURNAL_HARDLINK')
        with closing(sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True)) as c:
            row=c.execute('SELECT state FROM executions WHERE key=?',(idempotency_key,)).fetchone()
        state='NOT_RECORDED' if row is None else row[0]
        if state not in {'NOT_RECORDED','IN_FLIGHT','UNKNOWN','OUTPUT_RECORDED'}:raise ValueError('JOURNAL_STATE_REJECTED')
        return dict(transport_state=state,outcome='OUTPUT_RECORDED' if state=='OUTPUT_RECORDED' else 'UNKNOWN',
                    replay_authorized=False,terminal_accepted=False,production_execution=False)

    def execute_once(self,operation,*,deadline_monotonic):
        if (type(operation) is not dict or operation.get('scope')!='isolated_offline' or
            operation.get('production_execution') is not False or operation.get('inventory_id')!=INVENTORY or
            operation.get('schema')!=OPERATION_SCHEMA or operation.get('backend_protocol')!=BACKEND_PROTOCOL or
            operation.get('backend_id')!=self.backend_id):raise ValueError('OPERATION_REJECTED')
        body=dict(operation);key=body.pop('idempotency_key',None)
        if key!=digest(body):raise ValueError('IDEMPOTENCY_BINDING')
        binding=digest(dict(operation=operation,python_sha256=self.hashes[0],worker_sha256=self.hashes[1]))
        wall=operation.get('max_wall_seconds')
        if type(wall) is not int or not 0<wall<=3600:raise ValueError('WALL_BOUND')
        remaining=deadline_monotonic-time.monotonic()
        if not math.isfinite(remaining) or not 0<remaining<=wall:raise ValueError('DEADLINE_REJECTED')
        raw=json.dumps(operation,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        if len(raw)>65536:raise ValueError('INPUT_LIMIT')
        self._verify_files()
        # Commit before entering any child. IN_FLIGHT survives process death and
        # is never replayed. Output is cached transport evidence, not acceptance.
        with self._db() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT binding,state,result FROM executions WHERE key=?',(key,)).fetchone()
            if row:
                c.rollback()
                if row[0]!=binding:raise ValueError('EXECUTION_CONFLICT')
                if row[1]=='OUTPUT_RECORDED':return json.loads(row[2])
                raise ExecutionUnknown('UNKNOWN_NO_REPLAY')
            c.execute('INSERT INTO executions VALUES (?,?,?,NULL)',(key,binding,'IN_FLIGHT'));c.commit()
        try:
            remaining=deadline_monotonic-time.monotonic()
            if remaining<=0:raise ExecutionUnknown('DEADLINE_EXPIRED')
            result=run_tree([str(self.python),'-I','-B',str(self.worker)],timeout=remaining,
                            stdin_bytes=raw,stdout_limit_bytes=65536,stderr_limit_bytes=4096,event_limit_bytes=65536)
            if result.returncode!=0 or not result.cleanup_verified or time.monotonic()>deadline_monotonic:
                raise ExecutionUnknown('CHILD_OUTCOME_UNKNOWN')
            receipts=json.loads(result.stdout)
            if type(receipts) is not dict or set(receipts)!={'slot_receipt','budget_receipt'}:raise ExecutionUnknown('RECEIPTS_MISSING')
            with self._db() as c:
                c.execute('BEGIN IMMEDIATE')
                c.execute("UPDATE executions SET state='OUTPUT_RECORDED',result=? WHERE key=? AND binding=? AND state='IN_FLIGHT'",
                          (json.dumps(receipts,separators=(',',':')),key,binding))
                if c.execute('SELECT changes()').fetchone()[0]!=1:raise ExecutionUnknown('JOURNAL_CONFLICT')
                c.commit()
            # SingleSlotAdapter authenticates both receipts and joins the exact
            # persisted run/claim before any terminal or budget reconciliation.
            return receipts
        except BaseException:
            with self._db() as c:
                c.execute("UPDATE executions SET state='UNKNOWN' WHERE key=? AND state='IN_FLIGHT'",(key,))
            raise


def consume_existing_inventory_event(adapter, event):
    """Called by the existing Inventory owner while its existing lease is held.
    原Inventory事件消费，无轮询、新调度器、租约签发或生产派发授权。
    """
    if (type(event) is not dict or set(event)!={'inventory_id','admission','schedule','idle','budget_request'} or
        event['inventory_id']!=INVENTORY):raise ValueError('INVENTORY_EVENT_REJECTED')
    adapter._lock()  # No fallback lease acquisition, stale-lock removal or replay.
    return adapter.execute(event['admission'],event['schedule'],event['idle'],event['budget_request'])

"""Pinned subprocess transport for the existing offline admission protocol.
现有离线准入的真实子进程传输；不生成准入、回执或调度，不授权生产。
"""
from contextlib import closing, nullcontext
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


def _receipts(raw):
    # Preserve the exact receipt meaning across the worker and durable cache.
    # Reject ambiguous JSON before recording transport success.
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:raise ExecutionUnknown('DUPLICATE_RECEIPT_KEY')
            value[key] = item
        return value
    def nonfinite(_):raise ExecutionUnknown('NONFINITE_RECEIPT')
    def finite_float(raw):
        value = float(raw)
        if not math.isfinite(value):raise ExecutionUnknown('NONFINITE_RECEIPT')
        return value
    value = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite,
                       parse_float=finite_float)
    if type(value) is not dict or set(value)!={'slot_receipt','budget_receipt'}:
        raise ExecutionUnknown('RECEIPTS_MISSING')
    return value


class ProcessBackend:
    protocol_version=BACKEND_PROTOCOL

    def __init__(self, journal, *, python, python_sha256, worker, worker_sha256,
                 backend_id, offline_only=False, original_owner=None,
                 provider_config=None, provider_config_sha256=None):
        if offline_only is not True:raise ValueError('OFFLINE_ONLY')
        if original_owner is not None:
            from autonomy.original_inventory_owner import OriginalOwnerAuthority
            if type(original_owner) is not OriginalOwnerAuthority:
                raise ValueError('EXACT_ORIGINAL_BACKEND_OWNER_REQUIRED')
        if (provider_config is None)!=(provider_config_sha256 is None):
            raise ValueError('PROVIDER_REFERENCE_PAIR_REQUIRED')
        self.provider_reference=None
        if provider_config is not None:
            import re
            if (type(provider_config) is not str or not Path(provider_config).is_absolute() or
                type(provider_config_sha256) is not str or not re.fullmatch('[0-9a-f]{64}',provider_config_sha256)):
                raise ValueError('PROVIDER_REFERENCE_REJECTED')
            self.provider_reference=dict(path=provider_config,sha256=provider_config_sha256)
        self.original_owner=original_owner
        self.path=ordinary(journal)
        if not self.path.parent.is_dir():raise ValueError('JOURNAL_PARENT_REQUIRED')
        self.python=Path(python);self.worker=Path(worker)
        if not self.python.is_absolute() or not self.worker.is_absolute():raise ValueError('ABSOLUTE_EXECUTABLE_REQUIRED')
        self.hashes=(python_sha256,worker_sha256)
        self.backend_id=backend_id
        self._verify_files()
        with self._db() as c:
            c.execute('CREATE TABLE IF NOT EXISTS executions (key TEXT PRIMARY KEY, binding TEXT NOT NULL, state TEXT NOT NULL, result TEXT)')

    @classmethod
    def for_provider_worker(cls, journal, *, python, python_sha256,
                            worker_sha256, backend_id, provider_config,
                            provider_config_sha256, original_owner=None):
        """Bind the packaged Worker; hashes must come from the approved manifest.
        绑定包内固定入口；不自算可信摘要，不授权派发。
        """
        return cls(journal,python=python,python_sha256=python_sha256,
                   worker=str(Path(__file__).with_name('provider_worker.py').absolute()),
                   worker_sha256=worker_sha256,backend_id=backend_id,offline_only=True,
                   original_owner=original_owner,provider_config=provider_config,
                   provider_config_sha256=provider_config_sha256)

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
        # Validate before durable intent; retain file/ancestor pins through child
        # cleanup and result commit. Never export Provider secrets to the host.
        from autonomy.provider_environment import pinned_provider_environment
        reference=self.provider_reference
        context=(nullcontext() if reference is None else
                 pinned_provider_environment(reference['path'],reference['sha256']))
        from publisher_channel.install_inputs import InstallInputPins
        # Hash verification alone leaves a replacement window before CreateProcess.
        # Retain executable/source and ancestor handles through child cleanup and
        # durable receipt recording. Invalid inputs never create execution intent.
        with InstallInputPins() as executable_pins:
            for path, expected in zip((self.python,self.worker),self.hashes):
                executable_pins.add(path,expected)
            with context as environment:
                if reference is not None:
                    from discovery.providers.contracts import bound_search_request
                    if type(operation) is not dict or 'provider_request' not in operation:
                        raise ValueError('PROVIDER_SEARCH_REQUEST_REQUIRED')
                    request=bound_search_request(operation['provider_request'])
                    if request['provider']!=environment['WORKBUDDY_DISCOVERY_PROVIDER']:
                        raise ValueError('PROVIDER_REQUEST_CONFIG_MISMATCH')
                return self._execute_pinned(operation,deadline_monotonic=deadline_monotonic,
                                            executable_pins=executable_pins)

    def _execute_pinned(self,operation,*,deadline_monotonic,executable_pins):
        if (type(operation) is not dict or operation.get('scope')!='isolated_offline' or
            operation.get('production_execution') is not False or operation.get('inventory_id')!=INVENTORY or
            operation.get('schema')!=OPERATION_SCHEMA or operation.get('backend_protocol')!=BACKEND_PROTOCOL or
            operation.get('backend_id')!=self.backend_id):raise ValueError('OPERATION_REJECTED')
        original_context=any(k in operation for k in ('original_event_digest','original_claim_digest'))
        if original_context != (self.original_owner is not None):
            raise ValueError('EXACT_ORIGINAL_BACKEND_OWNER_REQUIRED')
        def assert_original_owner():
            common={k:operation[k] for k in ('slot','epoch','owner','run_id','request_id')}
            expected=self.original_owner.receipt_binding(dict(common,claim_token_hash=digest(operation['token'])))
            if any(type(operation.get(k)) is not type(v) or operation[k]!=v for k,v in expected.items()):
                raise ValueError('ORIGINAL_BACKEND_OWNER_BINDING_REJECTED')
            return True
        live=assert_original_owner if original_context else None
        if live is not None:live()
        body=dict(operation);key=body.pop('idempotency_key',None)
        if key!=digest(body):raise ValueError('IDEMPOTENCY_BINDING')
        execution_binding=dict(operation=operation,python_sha256=self.hashes[0],worker_sha256=self.hashes[1])
        if self.provider_reference is not None:
            execution_binding['provider_reference']=self.provider_reference
        binding=digest(execution_binding)
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
                if row[1]=='OUTPUT_RECORDED':return _receipts(row[2])
                raise ExecutionUnknown('UNKNOWN_NO_REPLAY')
            c.execute('INSERT INTO executions VALUES (?,?,?,NULL)',(key,binding,'IN_FLIGHT'));c.commit()
        try:
            remaining=deadline_monotonic-time.monotonic()
            if remaining<=0:raise ExecutionUnknown('DEADLINE_EXPIRED')
            arguments=[str(self.python),'-I','-B',str(self.worker)]
            if self.provider_reference is not None:
                arguments+=['--provider-config',self.provider_reference['path'],
                            '--provider-config-sha256',self.provider_reference['sha256']]
            result=run_tree(arguments,timeout=remaining,
                            stdin_bytes=raw,stdout_limit_bytes=65536,stderr_limit_bytes=4096,event_limit_bytes=65536,
                            assert_live=live)
            if result.returncode!=0 or not result.cleanup_verified or time.monotonic()>deadline_monotonic:
                raise ExecutionUnknown('CHILD_OUTCOME_UNKNOWN')
            receipts=_receipts(result.stdout)
            executable_pins.revalidate()
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

"""Service mailbox and existing-owner bridge; never a scheduler or authority.

HTTP authentication authorizes transport only. The existing owner still holds
its original lease and validates signed admission, budgets and settlement using
SingleSlotAdapter. Reserved events never become executable again after death.
This candidate supports isolated_offline contracts only; dispatch stays false.
"""
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import urllib.request
from autonomy import lock_recovery
from autonomy.growth_ledger import digest
from autonomy.release_store import canonical, ordinary, read_file
from autonomy.process_backend import consume_existing_inventory_event
from autonomy.unattended_policy import INVENTORY

MAX_EVENT = 65536


def owner_observer(runtime):
    runtime=ordinary(runtime)
    identity=(runtime.stat().st_dev,runtime.stat().st_ino)
    def observe():
        ordinary(runtime)
        if (runtime.stat().st_dev,runtime.stat().st_ino)!=identity:
            raise ValueError('OWNER_RUNTIME_CHANGED')
        with lock_recovery._guard(runtime):
            lease=json.loads(read_file(runtime/'supervisor.lock',8192))
            if (type(lease.get('schema_version')) is not int or lease['schema_version']!=3 or type(lease.get('pid')) is not int or
                    lease.get('recovery_only') or lease.get('recovery_required') or
                    not lease.get('token') or not lease.get('process_identity') or
                    lock_recovery.process_identity(lease['pid'])!=lease['process_identity']):
                raise ValueError('EXISTING_LIVE_OWNER_REQUIRED')
            return dict(lock_token_hash=digest(lease['token']),process_identity_hash=digest(lease['process_identity']))
    return observe


class EventMailbox:
    def __init__(self,path,*,observe_owner):
        self.path=ordinary(path)
        self.observe_owner=observe_owner
        if not self.path.parent.is_dir() or not callable(observe_owner):
            raise ValueError('PROVISIONED_MAILBOX_REQUIRED')
        if self.path.exists():read_file(self.path)
        with self.connection() as c:
            c.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY,event BLOB NOT NULL,owner BLOB NOT NULL,state TEXT NOT NULL,result BLOB)')
            c.commit()

    def connection(self):
        ordinary(self.path)
        if self.path.exists() and self.path.stat().st_nlink!=1:
            raise ValueError('MAILBOX_HARDLINK')
        c=sqlite3.connect(self.path,timeout=2)
        c.execute('PRAGMA synchronous=FULL')
        return closing(c)

    def submit(self,event,owner):
        if (type(event) is not dict or set(event)!={'inventory_id','admission','schedule','idle','budget_request'} or
                event['inventory_id']!=INVENTORY or any(type(event[k]) is not dict for k in ('admission','schedule','idle','budget_request')) or
                len(canonical(event))>MAX_EVENT or owner!=self.observe_owner()):
            raise ValueError('EVENT_OR_EXISTING_OWNER_REJECTED')
        identity=digest(dict(event=event,owner=owner))
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT event,owner FROM events WHERE id=?',(identity,)).fetchone()
            if row is None:
                c.execute('INSERT INTO events VALUES (?,?,?,\'PENDING\',NULL)',(identity,canonical(event),canonical(owner)))
            elif row!=(canonical(event),canonical(owner)):
                raise ValueError('EVENT_BINDING_CONFLICT')
            c.commit()
        return identity

    def reserve(self,identity,owner):
        if owner!=self.observe_owner():raise ValueError('EXISTING_OWNER_REQUIRED')
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT event,owner,state FROM events WHERE id=?',(identity,)).fetchone()
            if row is None or row[1]!=canonical(owner):raise ValueError('EVENT_OWNER_CONFLICT')
            if row[2]!='PENDING':raise ValueError('STOP_AND_PRESERVE_NO_EVENT_REPLAY')
            c.execute("UPDATE events SET state='RESERVED' WHERE id=? AND state='PENDING'",(identity,))
            c.commit()  # Must precede releasing event bytes to the caller.
        return json.loads(row[0])

    def report(self,identity,owner,result):
        if owner!=self.observe_owner() or type(result) is not dict or len(canonical(result))>MAX_EVENT:
            raise ValueError('OWNER_REPORT_REJECTED')
        # Transport receipt is never evidence of execution terminal success.
        with self.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT owner,state,result FROM events WHERE id=?',(identity,)).fetchone()
            if row is None or row[0]!=canonical(owner):raise ValueError('EVENT_OWNER_CONFLICT')
            raw=canonical(result)
            if row[1]=='OWNER_REPORTED' and row[2]==raw:return
            if row[1]!='RESERVED':raise ValueError('STOP_AND_PRESERVE_REPORT_CONFLICT')
            c.execute("UPDATE events SET state='OWNER_REPORTED',result=? WHERE id=?",(raw,identity));c.commit()

    def status(self,identity):
        if not re.fullmatch('[0-9a-f]{64}',identity):raise ValueError('EVENT_ID_REQUIRED')
        with self.connection() as c:
            row=c.execute('SELECT state FROM events WHERE id=?',(identity,)).fetchone()
        return dict(transport_state='NOT_RECORDED' if row is None else row[0],
                    execution_terminal='UNKNOWN',replay_allowed=False,allow_dispatch=False,
                    allow_cancel_dispatch=False,production_accepted=False)


def event_handler(base,mailbox):
    class Handler(base):
        def do_POST(self):
            authorized=self.authenticated()
            lengths=self.headers.get_all('Content-Length',[])
            if (self.headers.get_all('Transfer-Encoding') or len(lengths)!=1 or
                    not re.fullmatch('[0-9]{1,6}',lengths[0]) or not 0<int(lengths[0])<=MAX_EVENT):
                self.reply(400 if authorized else 401,error='BOUNDED_BODY_REQUIRED' if authorized else 'UNAUTHORIZED');return
            try:
                raw=self.rfile.read(int(lengths[0]))
                if len(raw)!=int(lengths[0]):raise ValueError('SHORT_BODY')
                if not authorized or not self.authenticated():self.reply(401,error='UNAUTHORIZED');return
                # Reject ambiguous requests before any durable reservation or
                # report. The response path already enforces the same rule.
                def unique_object(pairs):
                    obj={}
                    for key,item in pairs:
                        if key in obj:raise ValueError('DUPLICATE_REQUEST_KEY')
                        obj[key]=item
                    return obj
                def reject_constant(_):raise ValueError('NONFINITE_REQUEST')
                value=json.loads(raw,object_pairs_hook=unique_object,parse_constant=reject_constant)
                if type(value) is not dict:raise ValueError('BODY_SCHEMA')
                if self.path=='/v1/inventory-events' and set(value)=={'event','owner'}:
                    identity=mailbox.submit(value['event'],value['owner'])
                    if not self.authenticated():self.reply(401,error='UNAUTHORIZED');return
                    self.reply(200,event_id=identity,replay_allowed=False);return
                match=re.fullmatch('/v1/inventory-events/([0-9a-f]{64})/(reserve|report|status)',self.path)
                if not match:raise ValueError('ROUTE')
                identity,action=match.groups()
                if action=='reserve' and set(value)=={'owner'}:
                    event=mailbox.reserve(identity,value['owner'])
                    if not self.authenticated():self.reply(401,error='UNAUTHORIZED');return
                    self.reply(200,event=event,replay_allowed=False);return
                if action=='report' and set(value)=={'owner','result'}:
                    mailbox.report(identity,value['owner'],value['result'])
                    if not self.authenticated():self.reply(401,error='UNAUTHORIZED');return
                    self.reply(200,transport_state='OWNER_REPORTED',execution_terminal='UNKNOWN',replay_allowed=False);return
                if action=='status' and not value:
                    status=mailbox.status(identity)
                    if not self.authenticated():self.reply(401,error='UNAUTHORIZED');return
                    self.reply(200,transport_state=status['transport_state'],execution_terminal='UNKNOWN',replay_allowed=False);return
                raise ValueError('BODY_SCHEMA')
            except Exception:
                # No exception text, envelopes, credentials or local paths leak.
                self.reply(409,error='STOP_AND_PRESERVE');return
    return Handler


class ExistingOwnerBridge:
    def __init__(self,adapter,*,port,token):
        if type(port) is not int or not 1<=port<=65535 or not re.fullmatch('[A-Za-z0-9_-]{32,128}',token or ''):
            raise ValueError('PROVISIONED_LOOPBACK_TRANSPORT_REQUIRED')
        self.adapter=adapter;self.port=port;self.token=token

    def request(self,route,value):
        raw=canonical(value)
        request=urllib.request.Request('http://127.0.0.1:'+str(self.port)+route,data=raw,
            headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'},method='POST')
        # No environment proxy, redirect, arbitrary host or automatic retry.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args):return None
        with urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open(request,timeout=5) as response:
            reply=response.read(MAX_EVENT+1)
        # A reserved event is never released to the executor on an ambiguous
        # transport envelope. In particular, Python's JSON decoder otherwise
        # accepts duplicate keys and non-finite constants.
        def unique_object(pairs):
            value={}
            for key,item in pairs:
                if key in value:raise ValueError('DUPLICATE_RESPONSE_KEY')
                value[key]=item
            return value
        def reject_constant(_):raise ValueError('NONFINITE_RESPONSE')
        if len(reply)>MAX_EVENT:raise ValueError('SERVICE_RESPONSE_TOO_LARGE')
        result=json.loads(reply,object_pairs_hook=unique_object,parse_constant=reject_constant)
        if (type(result) is not dict or result.get('schema')!='rokt.offline-host-readonly.v1' or
                result.get('inventory_id')!=INVENTORY or
                any(result.get(key) is not False for key in
                    ('allow_dispatch','allow_cancel_dispatch','allow_reconcile','production_accepted','replay_allowed'))):
            raise ValueError('SERVICE_RESPONSE_REJECTED')
        return result

    def consume(self,event):
        owner=self.adapter._lock()
        # Validate authority BEFORE reserving the transport event. This does not
        # create a claim or budget reservation; execute still repeats all gates.
        admission, _ = self.adapter._admission(event['admission'])
        # Reject malformed search arguments before consuming the owner's
        # durable, non-replayable event intent. This grants no dispatch rights.
        if 'provider_request' in admission:
            from discovery.providers.contracts import bound_search_request
            bound_search_request(admission['provider_request'])
        self.adapter.prepare_event(event)
        identity=self.request('/v1/inventory-events',dict(event=event,owner=owner))['event_id']
        route='/v1/inventory-events/'+identity
        delivered=self.request(route+'/reserve',dict(owner=owner))['event']
        if delivered!=event:raise ValueError('EVENT_DELIVERY_MISMATCH')
        self.adapter._lock()
        result=consume_existing_inventory_event(self.adapter,delivered)
        self.adapter._lock()
        self.request(route+'/report',dict(owner=owner,result=result))
        return dict(event_id=identity,owner_result=result,transport_terminal_accepted=False,
                    allow_dispatch=False,allow_cancel_dispatch=False,production_execution=False)

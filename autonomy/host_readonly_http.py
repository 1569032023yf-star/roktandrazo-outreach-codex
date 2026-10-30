"""Offline HTTP adapter candidate; no bind/start/install or execution entrypoint.

The caller supplies an independently provisioned token and a read-only backend
status reader. This is not integrated into the disabled SCM package or 8791.
"""
import hmac
import json
import re
import math
import time
import threading
from http.server import BaseHTTPRequestHandler
from autonomy.unattended_policy import INVENTORY
from autonomy.recovery_status import inspect_recovery_status


def snapshot_status_reader(snapshot, expected_sha256):
    """Freeze caller-provided bytes and an independent digest; no live paths."""
    if type(snapshot) is not bytes:raise ValueError('IMMUTABLE_SNAPSHOT_REQUIRED')
    if type(expected_sha256) is not str or re.fullmatch('[0-9a-f]{64}',expected_sha256) is None:
        raise ValueError('INDEPENDENT_DIGEST_REQUIRED')
    return lambda identity: inspect_recovery_status(snapshot, expected_sha256, identity)


def readonly_handler(token, status_reader, *, credential_expires_at, clock=time.time):
    if type(token) is not str or re.fullmatch('[A-Za-z0-9_-]{32,128}',token) is None:
        raise ValueError('PROVISIONED_TOKEN_REQUIRED')
    if not callable(status_reader):raise ValueError('READ_ONLY_STATUS_READER_REQUIRED')
    if type(credential_expires_at) is not int or credential_expires_at<=0 or not callable(clock):
        raise ValueError('EXPLICIT_CREDENTIAL_DEADLINE_REQUIRED')
    expected=('Bearer '+token).encode('ascii')
    credential_lock=threading.Lock()
    last_clock=None
    invalidated=False

    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.0'
        server_version='RoktOfflineReadOnly/1'
        sys_version=''

        def setup(self):
            super().setup();self.connection.settimeout(3)

        def log_message(self,*args):
            pass  # Never log Authorization, request paths or backend exceptions.

        def reply(self,code,**fields):
            payload=dict(schema='rokt.offline-host-readonly.v1',inventory_id=INVENTORY,
                allow_dispatch=False,allow_cancel_dispatch=False,allow_reconcile=False,
                production_accepted=False,**fields)
            raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode('ascii')
            self.send_response(code);self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(raw)))
            self.send_header('Connection','close');self.end_headers()
            if self.command!='HEAD':self.wfile.write(raw)

        def authenticated(self):
            nonlocal last_clock,invalidated
            # Shared by all handler instances for this credential. Once time
            # becomes untrustworthy, this factory cannot revive the credential.
            with credential_lock:
                try:
                    now=clock()
                    valid=(not invalidated and type(now) in (int,float) and
                           math.isfinite(now) and 0<=now<credential_expires_at and
                           (last_clock is None or now>=last_clock))
                except Exception:
                    valid=False
                if valid:last_clock=now
                else:invalidated=True
            auth=self.headers.get_all('Authorization',[])
            return (valid and len(auth)==1 and
                    hmac.compare_digest(auth[0].encode('utf-8'),expected))

        def do_GET(self):
            if not self.authenticated():
                self.reply(401,error='UNAUTHORIZED');return
            if (self.headers.get_all('Transfer-Encoding') or
                self.headers.get_all('Content-Length',[]) not in ([],['0'])):
                self.reply(400,error='BODY_NOT_ALLOWED');return
            if self.path=='/v1/health':
                self.reply(200,health='OFFLINE_ADAPTER_ONLY',backend_accepted=False);return
            match=re.fullmatch(r'/v1/recovery-status/([0-9a-f]{64})',self.path)
            if not match:
                self.reply(404,error='READ_ONLY_ROUTE_REQUIRED');return
            operation_id=match.group(1)
            try:
                value=status_reader(operation_id)
                fixed=dict(schema='rokt.offline-recovery-status.v1',accepted=True,
                    execution_terminal='UNKNOWN',lock_closed='UNKNOWN',source_authorized='UNKNOWN',
                    allow_dispatch=False,allow_cancel_dispatch=False,allow_reconcile=False,
                    replay_allowed=False,production_accepted=False)
                if (type(value) is not dict or
                    set(value)!=set(fixed)|{'reason','journal_phase'} or
                    any(type(value[k]) is not type(v) or value[k]!=v for k,v in fixed.items()) or
                    (value.get('reason'),value.get('journal_phase')) not in (
                        ('NOT_RECORDED','NOT_RECORDED'),('RECOVERY_JOURNAL_ONLY','PREPARED'),
                        ('RECOVERY_JOURNAL_ONLY','COMPLETED'))):
                    self.reply(503,error='BACKEND_STATUS_UNAVAILABLE');return
            except Exception:
                self.reply(503,error='BACKEND_STATUS_UNAVAILABLE');return
            self.reply(200,cancel_identity=operation_id,journal_phase=value['journal_phase'],
                execution_terminal='UNKNOWN',lock_closed='UNKNOWN',source_authorized='UNKNOWN',
                replay_allowed=False)

        def reject(self):
            if not self.authenticated():
                self.reply(401,error='UNAUTHORIZED');return
            self.reply(405,error='READ_ONLY_METHOD_REQUIRED')

        do_POST=do_PUT=do_DELETE=do_PATCH=do_HEAD=do_OPTIONS=reject

    return Handler

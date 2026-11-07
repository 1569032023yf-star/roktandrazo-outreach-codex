"""Runnable authenticated read-only host bootstrap; no collector or scheduler.

Composes the version store, lifetime process exclusion and existing 8791 handler.
SCM child supervision and production execution backend remain release blockers.
"""
import argparse
import hashlib
import json
import time
import re
import sqlite3
from contextlib import contextmanager, ExitStack
from http.server import HTTPServer
from pathlib import Path
from autonomy.host_readonly_http import readonly_handler, snapshot_status_reader
from autonomy.release_store import ReleaseStore, read_file, ordinary
from autonomy.growth_snapshot import MAX_SNAPSHOT_BYTES


def original_owner_reader(path):
    """Provisioned local DB reference; never create, migrate or write the DB.

    Capture file identity once. Replacement requires a new approved bootstrap;
    it must not silently switch the authority observed by a running service.
    """
    path = Path(path)
    if not path.is_absolute():raise ValueError('ABSOLUTE_ORIGINAL_DB_REQUIRED')
    def identity():
        ordinary(path)
        stat = path.stat()
        if not path.is_file() or stat.st_nlink != 1:
            raise ValueError('ORDINARY_ORIGINAL_DB_REQUIRED')
        return stat.st_dev, stat.st_ino
    expected = identity()
    def connect():
        if identity() != expected:raise ValueError('ORIGINAL_DB_REPLACED')
        conn = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=5)
        try:
            conn.execute('PRAGMA query_only=ON')
            if identity() != expected:raise ValueError('ORIGINAL_DB_REPLACED')
            return conn
        except BaseException:
            conn.close()
            raise
    return connect


@contextmanager
def open_host(release_root, state_root, token, credential_expires_at,
              snapshot, snapshot_sha256, *, port=8791, event_runtime=None,
              original_owner_connect=None):
    if event_runtime is not None and original_owner_connect is not None:
        raise ValueError('EXACTLY_ONE_OWNER_AUTHORITY_REQUIRED')
    release=ReleaseStore(release_root)
    if release.recovery_status()['pending']:
        raise ValueError('STOP_AND_PRESERVE_PENDING_PUBLICATION')
    version=release.status()['version']
    if version is None: raise ValueError('NO_ACTIVE_RELEASE')
    handler=readonly_handler(token,snapshot_status_reader(snapshot,snapshot_sha256),
                             credential_expires_at=credential_expires_at)
    # Persistent OS byte lock, held until the listener closes. Process death
    # releases the lock; backend UNKNOWN outcomes are never replayed here.
    state=ReleaseStore(state_root)
    with state.locked():
        if event_runtime is not None or original_owner_connect is not None:
            from autonomy.inventory_event_bridge import EventMailbox,event_handler,owner_observer
            if original_owner_connect is not None:
                from autonomy.original_inventory_owner import observer
                observe = observer(original_owner_connect)
            else:
                observe = owner_observer(event_runtime)
            mailbox=EventMailbox(Path(state_root)/'inventory-events.sqlite',observe_owner=observe)
            handler=event_handler(handler,mailbox)
        with HTTPServer(('127.0.0.1',port),handler) as server:
            server.timeout=1
            yield server


def validate_startup_bytes(token_bytes, token_digest, snapshot, snapshot_digest, expires):
    """Reject stale credentials or changed snapshot before state/authority/listen."""
    if token_digest is not None:
        if type(token_digest) is not str or not re.fullmatch('[0-9a-f]{64}',token_digest):
            raise ValueError('APPROVED_TOKEN_DIGEST_REQUIRED')
        if hashlib.sha256(token_bytes).hexdigest()!=token_digest:
            raise ValueError('APPROVED_TOKEN_CHANGED')
    token=token_bytes.decode('ascii').strip()
    if re.fullmatch('[A-Za-z0-9_-]{32,128}',token) is None:
        raise ValueError('PROVISIONED_TOKEN_REQUIRED')
    if type(expires) is not int or expires<=time.time():
        raise ValueError('CREDENTIAL_EXPIRED')
    if type(snapshot_digest) is not str or re.fullmatch('[0-9a-f]{64}',snapshot_digest) is None:
        raise ValueError('APPROVED_SNAPSHOT_DIGEST_REQUIRED')
    if hashlib.sha256(snapshot).hexdigest()!=snapshot_digest:
        raise ValueError('APPROVED_SNAPSHOT_CHANGED')
    return token


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release-root',required=True);p.add_argument('--state-root',required=True)
    p.add_argument('--token-file',required=True);p.add_argument('--credential-expires-at',type=int,required=True)
    p.add_argument('--token-sha256')
    p.add_argument('--provider-config');p.add_argument('--provider-config-sha256')
    p.add_argument('--snapshot',required=True);p.add_argument('--snapshot-sha256',required=True)
    owner=p.add_mutually_exclusive_group()
    owner.add_argument('--event-runtime')
    owner.add_argument('--original-owner-db')
    p.add_argument('--preflight',action='store_true',help='Validate pinned startup inputs without state writes or listening')
    a=p.parse_args(argv)
    if (a.provider_config is None)!=(a.provider_config_sha256 is None):
        raise ValueError('PROVIDER_CONFIG_PAIR_REQUIRED')
    token_bytes=read_file(Path(a.token_file),128)
    # Hash the exact bytes read, before decoding or normalization, and before
    # opening original authority, creating state or binding the listener.
    if a.token_sha256 is not None:
        if not re.fullmatch('[0-9a-f]{64}',a.token_sha256):raise ValueError('APPROVED_TOKEN_DIGEST_REQUIRED')
        if hashlib.sha256(token_bytes).hexdigest()!=a.token_sha256:raise ValueError('APPROVED_TOKEN_CHANGED')
    token=token_bytes.decode('ascii').strip()
    with ExitStack() as lifetime:
        if a.provider_config is not None:
            from autonomy.provider_environment import pinned_provider_environment
            # Validate and hold the approved external file for this host lifetime.
            # Never expose keys through HTTP, inherit them into the service env,
            # or treat this reference as authority to start a Worker.
            lifetime.enter_context(pinned_provider_environment(a.provider_config,a.provider_config_sha256))
        snapshot=read_file(Path(a.snapshot),MAX_SNAPSHOT_BYTES)
        token=validate_startup_bytes(token_bytes,a.token_sha256,snapshot,a.snapshot_sha256,a.credential_expires_at)
        connect=original_owner_reader(a.original_owner_db) if a.original_owner_db else None
        if a.preflight:
            # resolve_release performs read-only pointer/manifest/namespace checks;
            # ReleaseStore.status/recovery_status acquire a writable lock instead.
            from autonomy.windows.u1_bootstrap import resolve_release
            resolve_release(a.release_root)
            if not ordinary(Path(a.state_root)).is_dir():
                raise ValueError('EXISTING_STATE_DIRECTORY_REQUIRED')
            if a.event_runtime is not None and not ordinary(Path(a.event_runtime)).is_dir():
                raise ValueError('EXISTING_EVENT_RUNTIME_REQUIRED')
            print(json.dumps(dict(schema='rokt.u1-startup-preflight.v1',inventory_id='1784775229336',
                startup_inputs_verified=True,release_integrity_verified=True,
                provider_config_pinned=a.provider_config is not None,
                owner_mode='original_owner_db' if connect else 'event_runtime' if a.event_runtime else 'none',
                owner_authority_verified=False,live_lock_verified=False,snapshot_schema_verified=False,
                provider_contract='CONTRACT_MISSING',allow_install=False,allow_dispatch=False,
                allow_cancel_dispatch=False,smtp_enabled=False,listener_started=False,production_ready=False)))
            return
        with open_host(a.release_root,a.state_root,token,a.credential_expires_at,snapshot,a.snapshot_sha256,
                       event_runtime=a.event_runtime,original_owner_connect=connect) as server:
            try: server.serve_forever(poll_interval=0.5)
            except KeyboardInterrupt: pass



if __name__=='__main__':main()

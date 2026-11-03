"""Runnable authenticated read-only host bootstrap; no collector or scheduler.

Composes the version store, lifetime process exclusion and existing 8791 handler.
SCM child supervision and production execution backend remain release blockers.
"""
import argparse
from contextlib import contextmanager
from http.server import HTTPServer
from pathlib import Path
from autonomy.host_readonly_http import readonly_handler, snapshot_status_reader
from autonomy.release_store import ReleaseStore, read_file
from autonomy.growth_snapshot import MAX_SNAPSHOT_BYTES


@contextmanager
def open_host(release_root, state_root, token, credential_expires_at,
              snapshot, snapshot_sha256, *, port=8791, event_runtime=None):
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
        if event_runtime is not None:
            from autonomy.inventory_event_bridge import EventMailbox,event_handler,owner_observer
            mailbox=EventMailbox(Path(state_root)/'inventory-events.sqlite',observe_owner=owner_observer(event_runtime))
            handler=event_handler(handler,mailbox)
        with HTTPServer(('127.0.0.1',port),handler) as server:
            server.timeout=1
            yield server


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release-root',required=True);p.add_argument('--state-root',required=True)
    p.add_argument('--token-file',required=True);p.add_argument('--credential-expires-at',type=int,required=True)
    p.add_argument('--snapshot',required=True);p.add_argument('--snapshot-sha256',required=True)
    p.add_argument('--event-runtime')
    a=p.parse_args()
    token=read_file(Path(a.token_file),128).decode('ascii').strip()
    snapshot=read_file(Path(a.snapshot),MAX_SNAPSHOT_BYTES)
    with open_host(a.release_root,a.state_root,token,a.credential_expires_at,snapshot,a.snapshot_sha256,event_runtime=a.event_runtime) as server:
        try: server.serve_forever(poll_interval=0.5)
        except KeyboardInterrupt: pass


if __name__=='__main__':main()

"""Publisher-owned install exclusion. No CLI, scheduler, process or DB discovery.

Only a trusted publisher caller supplies the already-authorized connection,
installer and independent final verifier. Public installation remains disabled.
Maintenance operation IDs identify a single invocation; target_operation_id
identifies the install journal, allowing a distinct explicit rollback invocation.
"""
import hashlib
import json
import re

from autonomy import inventory_maintenance as authority


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


class InstallMaintenance:
    def __init__(self, conn, binding, *, target_operation_id, action):
        authority.binding_bytes(binding)
        if (type(target_operation_id) is not str or
                not re.fullmatch('[0-9a-f]{64}', target_operation_id) or
                action not in ('install', 'upgrade', 'recover', 'rollback')):
            raise ValueError('EXACT_INSTALL_CONTEXT_REQUIRED')
        self.conn = conn
        self.binding = dict(binding)
        self.context = dict(binding=self.binding, target_operation_id=target_operation_id, action=action)
        self.key = authority.KEY+':session:'+binding['operation_id']

    def _records(self):
        prefix = self.key+':'
        rows = self.conn.execute('SELECT key,value FROM system_config WHERE substr(key,1,?)=? ORDER BY key',
                                 (len(prefix), prefix)).fetchall()
        previous = ''
        records = []
        for index, (key, raw) in enumerate(rows):
            try:
                record = json.loads(raw)
                if (key != prefix+f'{index:06d}' or record['sequence'] != index or
                        record['context'] != self.context or record['previous_sha256'] != previous or
                        canonical(record) != raw):
                    raise ValueError('invalid record')
            except (TypeError, KeyError, ValueError) as e:
                raise ValueError('STOP_AND_PRESERVE_MAINTENANCE_JOURNAL') from e
            previous = hashlib.sha256(raw.encode()).hexdigest()
            records.append(record)
        return records, previous

    def _append(self, phase, detail=None):
        records, previous = self._records()
        index = len(records)
        record = dict(sequence=index, previous_sha256=previous, context=self.context,
                      phase=phase, detail=detail)
        self.conn.execute("INSERT INTO system_config(key,value,updated_at) VALUES(?,?,datetime('now'))",
                          (self.key+f':{index:06d}', canonical(record)))

    def _transition(self, phase, detail=None):
        try:
            self.conn.execute('BEGIN IMMEDIATE')
            authority.assert_held(self.conn, self.binding)
            self._append(phase, detail)
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def acquire(self):
        # Original authority persists both exclusion and replay tombstone before
        # any installer can run. A crash before HELD intentionally stays fenced.
        authority.acquire(self.conn, self.binding)
        self._transition('HELD')

    def assert_held(self, target_operation_id, source_commit, manifest_sha256, action):
        if (target_operation_id != self.context['target_operation_id'] or
                source_commit != self.binding['source_commit'] or
                manifest_sha256 != self.binding['manifest_sha256'] or action != self.context['action']):
            raise ValueError('STOP_AND_PRESERVE_INSTALL_BINDING_MISMATCH')
        authority.assert_held(self.conn, self.binding)
        records, _ = self._records()
        if not records or records[-1]['phase'] in ('RELEASED', 'UNKNOWN'):
            raise ValueError('STOP_AND_PRESERVE_SESSION_NOT_ACTIVE')
        return True

    def _verify_and_release(self, observed, verifier):
        self._transition('FINAL_VERIFY_INTENT')
        # The trusted publisher must independently read target/service/ACL state;
        # installer stdout alone is not final verification.
        proof = verifier(self, observed)
        if (type(proof) is not dict or set(proof) != {'context', 'outcome', 'evidence_sha256'} or
                proof['context'] != self.context or proof['outcome'] not in ('COMMITTED', 'ROLLED_BACK') or
                type(proof['evidence_sha256']) is not str or
                not re.fullmatch('[0-9a-f]{64}', proof['evidence_sha256']) or
                (self.context['action'] in ('recover', 'rollback') and proof['outcome'] != 'ROLLED_BACK')):
            raise ValueError('STOP_AND_PRESERVE_FINAL_VERIFICATION_REQUIRED')
        try:
            self.conn.execute('BEGIN IMMEDIATE')
            authority.assert_held(self.conn, self.binding)
            self._append('FINAL_VERIFIED', proof)
            self.conn.execute("UPDATE system_config SET value='released',updated_at=datetime('now') WHERE key=?",
                              (authority.KEY,))
            self._append('RELEASED', proof)
            # Verification receipt and release share a commit. On uncertain
            # commit, query the journal; never invoke the installer again.
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        return proof

    def execute(self, installer, verifier):
        self.acquire()
        try:
            self._transition('INSTALL_INTENT')
            observed = installer(self)
            self._transition('INSTALLER_RETURNED')
            return self._verify_and_release(observed, verifier)
        except BaseException:
            # No finally-release. Even process death leaves the durable marker.
            try:
                self._transition('UNKNOWN')
            except BaseException:
                pass
            raise

    def reconcile(self, verifier):
        """Explicit read-only reconciliation, never launch/replay the installer."""
        authority.assert_held(self.conn, self.binding)
        records, _ = self._records()
        if not records:
            raise ValueError('STOP_AND_PRESERVE_MISSING_SESSION')
        try:
            return self._verify_and_release(None, verifier)
        except BaseException:
            try:
                self._transition('UNKNOWN')
            except BaseException:
                pass
            raise

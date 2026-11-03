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
        allowed = {
            'INSTALL_INTENT': {'HELD'},
            'INSTALLER_RETURNED': {'INSTALL_INTENT'},
            'FINAL_VERIFY_INTENT': {'HELD', 'INSTALL_INTENT', 'INSTALLER_RETURNED', 'UNKNOWN', 'FINAL_VERIFY_INTENT'},
            'UNKNOWN': {'HELD', 'INSTALL_INTENT', 'INSTALLER_RETURNED', 'FINAL_VERIFY_INTENT', 'UNKNOWN'},
        }
        try:
            self.conn.execute('BEGIN IMMEDIATE')
            authority.assert_held(self.conn, self.binding)
            records, _ = self._records()
            if not records or records[-1]['phase'] not in allowed.get(phase, set()):
                raise ValueError('STOP_AND_PRESERVE_SESSION_TRANSITION')
            self._append(phase, detail)
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def acquire(self):
        # Marker, tombstone and full session context become durable together.
        try:
            self.conn.execute('BEGIN IMMEDIATE')
            authority.acquire_locked(self.conn, self.binding)
            self._append('HELD')
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def assert_held(self, target_operation_id, source_commit, manifest_sha256, action):
        if (target_operation_id != self.context['target_operation_id'] or
                source_commit != self.binding['source_commit'] or
                manifest_sha256 != self.binding['manifest_sha256'] or action != self.context['action']):
            raise ValueError('STOP_AND_PRESERVE_INSTALL_BINDING_MISMATCH')
        authority.assert_held(self.conn, self.binding)
        records, _ = self._records()
        if not records or records[-1]['phase'] not in ('HELD', 'INSTALL_INTENT', 'INSTALLER_RETURNED', 'FINAL_VERIFY_INTENT'):
            raise ValueError('STOP_AND_PRESERVE_SESSION_NOT_ACTIVE')
        return True

    def process_guard(self):
        """Bind the parent process watchdog to this exact executing session.

        Trusted adapters pass this to process_job.run_tree(assert_live=...).
        It neither launches a command nor grants public install permission.
        Child per-mutation checks remain mandatory.
        """
        expected = canonical(self.context)
        target = self.context['target_operation_id']
        source = self.binding['source_commit']
        manifest = self.binding['manifest_sha256']
        action = self.context['action']
        def check():
            if canonical(self.context) != expected:
                raise ValueError('STOP_AND_PRESERVE_PROCESS_CONTEXT_CHANGED')
            self.assert_held(target, source, manifest, action)
            records, _ = self._records()
            if records[-1]['phase'] != 'INSTALL_INTENT':
                raise ValueError('STOP_AND_PRESERVE_PROCESS_SESSION_NOT_EXECUTING')
            return True
        return check

    def maintenance_handler(self):
        """Private stdio requests are assertions, never installation grants."""
        live = self.process_guard()
        def check(request):
            live()
            return self.assert_held(request['target_operation_id'], request['source_commit'],
                                    request['manifest_sha256'], request['action'])
        return check

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
            records, _ = self._records()
            if not records or records[-1]['phase'] != 'FINAL_VERIFY_INTENT':
                raise ValueError('STOP_AND_PRESERVE_FINAL_SESSION_CHANGED')
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
        return self._execute_held(installer, verifier)

    def _execute_held(self, installer, verifier):
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

    def _compensation_child(self, recovery_id):
        child = InstallMaintenance(self.conn, self.binding,
                                   target_operation_id=self.context['target_operation_id'], action='recover')
        child.key = authority.KEY+':recovery-session:'+self.binding['operation_id']+':'+recovery_id
        child.context.update(parent_context_sha256=hashlib.sha256(canonical(self.context).encode()).hexdigest(),
                             recovery_id=recovery_id)
        return child

    def compensation_session(self, recovery_id):
        """Reopen recorded compensation after restart; never launch anything."""
        child = self._compensation_child(recovery_id)
        records, _ = self._records()
        if (not records or records[-1]['phase'] != 'RECOVERY_ADMITTED' or
                records[-1]['detail']['child_key'] != child.key or not child._records()[0]):
            raise ValueError('STOP_AND_PRESERVE_UNKNOWN_RECOVERY')
        return child

    def compensate(self, recovery_id, installer, verifier, *, confirm_stopped):
        """Explicit compensation under the SAME exclusion, never forward replay.

        The trusted process adapter must establish the previous child is dead
        before calling. A fresh request ID records handoff to action=recover;
        that parent can no longer assert authority or release while it runs.
        """
        if type(recovery_id) is not str or not re.fullmatch('[0-9a-f]{64}', recovery_id):
            raise ValueError('EXACT_RECOVERY_REQUEST_REQUIRED')
        stopped = confirm_stopped(self)
        if (type(stopped) is not dict or set(stopped) != {'context', 'stopped', 'process_identity_sha256'} or
                stopped['context'] != self.context or stopped['stopped'] is not True or
                type(stopped['process_identity_sha256']) is not str or
                not re.fullmatch('[0-9a-f]{64}', stopped['process_identity_sha256'])):
            raise ValueError('STOP_AND_PRESERVE_PREVIOUS_PROCESS_UNVERIFIED')
        child = self._compensation_child(recovery_id)
        try:
            self.conn.execute('BEGIN IMMEDIATE')
            authority.assert_held(self.conn, self.binding)
            records, _ = self._records()
            if (not records or records[-1]['phase'] not in ('HELD', 'UNKNOWN', 'INSTALL_INTENT', 'INSTALLER_RETURNED', 'FINAL_VERIFY_INTENT') or child._records()[0]):
                raise ValueError('STOP_AND_PRESERVE_EXPLICIT_RECOVERY_REQUIRED')
            self._append('RECOVERY_ADMITTED', dict(child_key=child.key, context=child.context, stopped=stopped))
            child._append('HELD')
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        return child._execute_held(installer, verifier)

    def reconcile(self, verifier):
        """Explicit read-only reconciliation, never launch/replay the installer."""
        authority.assert_held(self.conn, self.binding)
        records, _ = self._records()
        if not records:
            raise ValueError('STOP_AND_PRESERVE_MISSING_SESSION')
        if records[-1]['phase'] in ('RELEASED', 'RECOVERY_ADMITTED'):
            raise ValueError('STOP_AND_PRESERVE_SESSION_HANDED_OFF')
        try:
            return self._verify_and_release(None, verifier)
        except BaseException:
            try:
                self._transition('UNKNOWN')
            except BaseException:
                pass
            raise

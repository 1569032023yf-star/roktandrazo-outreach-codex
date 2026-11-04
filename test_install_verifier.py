"""Real coordinator/files and authority; isolated SCM/ACL / 真实文件与维护权，隔离 SCM/ACL。"""
import base64
import json
import sqlite3
import subprocess
import unittest
from unittest.mock import patch

import test_host_install_transaction as fixture
from autonomy import inventory_maintenance as authority
from publisher_channel.install_maintenance import InstallMaintenance
from publisher_channel import install_verifier as v


class InstallVerifierTests(unittest.TestCase):
    def setUp(self):
        self.host=fixture.HostInstallTests();self.host.setUp();self.addCleanup(self.host.doCleanups)
        for key,path in [('CODE',self.host.code),('STATE',self.host.state),('AUDIT',self.host.audit)]:
            p=patch.object(v,key,path);p.start();self.addCleanup(p.stop)
        self.conn=sqlite3.connect(self.host.root/'authority.db');self.addCleanup(self.conn.close)
        self.conn.execute('CREATE TABLE system_config(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT)');self.conn.commit()
        self.number=0;self.stopped=False;self.mutate=lambda snapshot:None

    def session(self,manifest='a',action='install',operation=None):
        self.number+=1
        binding=dict(inventory_id='1784775229336',operation_id=format(self.number,'064x'),
                     source_commit='b'*40,manifest_sha256=manifest*64,lease_nonce='d'*64)
        return InstallMaintenance(self.conn,binding,target_operation_id=operation or manifest*64,action=action)

    def observe(self,operation,nonce):
        sid='S-1-5-80-1-2-3-4-5'
        def ace(identity,rights):return dict(sid=identity,type='Allow',rights=rights,inheritance=3,propagation=0)
        acl_file=self.host.root/'acl-state'
        acl=json.loads(acl_file.read_text(encoding='utf-8-sig')) if acl_file.exists() else dict(code='before-code',state='before-state')
        roots={key:(dict(sddl=acl[key],protected=key=='state',aces=(
            [ace(sid,131241)] if key=='code' else [ace(sid,197055),ace('S-1-5-18',2032127),ace('S-1-5-32-544',2032127)]))
            if path.exists() else None) for key,path in [('code',v.CODE),('state',v.STATE)]}
        service_file=self.host.root/'service.json';service=None
        if service_file.exists():
            raw=json.loads(service_file.read_text(encoding='utf-8-sig'))
            service=dict(name=v.SERVICE,start_mode=raw['StartMode'],state=raw['State'],account=raw['StartName'],image=raw['PathName'])
        journals={key:(v.digest(path.read_bytes()) if path.exists() else None) for key,path in {
            'install':v.AUDIT/f'install-{operation}.jsonl','files':v.AUDIT/f'files-{operation}.jsonl',
            'acl':v.AUDIT/f'acl-{operation}.jsonl','state_create':v.AUDIT/f'acl-{operation}.jsonl.state-create.jsonl'}.items()}
        snapshot=dict(schema='rokt.u1-install-observation.v1',operation_id=operation,nonce=nonce,
                      audit_trusted=True,journals=journals,roots=roots,service=service,service_sid=sid)
        self.mutate(snapshot)
        return snapshot

    def verifier(self,manifest='a',previous=None):
        files={'service/RoktU1Bridge.exe':b'MZ-'+manifest.encode(),'config/host.json':b'{}'}
        files.update({'config/obsolete.json':b'old'} if manifest=='a' else {'runtime/new.json':b'new'})
        def stopped(session):
            return dict(context=session.context,stopped=self.stopped,process_identity_sha256='f'*64)
        return v.InstallVerifier({k:v.digest(raw) for k,raw in files.items()},previous_receipt_sha256=previous,
                                 observe=self.observe,confirm_stopped=stopped)

    def run_host(self,session,**kwargs):
        self.stopped=False
        result=self.host.run_coordinator(maintenance_session=session,**kwargs)
        self.assertTrue(result.cleanup_verified);self.stopped=True
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        return 'UNTRUSTED STDOUT CLAIM'

    def install(self):
        session=self.session()
        proof=session.execute(lambda s:self.run_host(s),self.verifier())
        self.assertEqual(proof['outcome'],'COMMITTED');self.assertFalse(authority.blocked(self.conn))
        records,_=session._records()
        evidence=[r['detail']['terminal_evidence'] for r in records if r['detail'] and 'terminal_evidence' in r['detail']]
        self.assertEqual(len(evidence),1);self.assertEqual(v.digest(v.canonical(evidence[0])),proof['evidence_sha256'])
        return v.digest((v.CODE/v.RECEIPT).read_bytes())

    def test_first_install_upgrade_and_both_rollbacks(self):
        previous=self.install()
        session=self.session('b','upgrade')
        proof=session.execute(lambda s:self.run_host(s,upgrade=True,manifest='b',previous=previous),self.verifier('b',previous))
        self.assertEqual(proof['outcome'],'COMMITTED')
        session=self.session('b','rollback')
        proof=session.execute(lambda s:self.run_host(s,rollback=True,manifest='b'),self.verifier('b',previous))
        self.assertEqual(proof['outcome'],'ROLLED_BACK')
        session=self.session('a','rollback')
        proof=session.execute(lambda s:self.run_host(s,rollback=True),self.verifier())
        self.assertEqual(proof['outcome'],'ROLLED_BACK');self.assertFalse(v.CODE.exists());self.assertFalse(v.STATE.exists())

    def test_terminal_mismatches_preserve_maintenance_and_forbid_replay(self):
        self.install()
        changes={
            'running':lambda s:s['service'].update(state='Running'),
            'inheritance':lambda s:s['roots']['state'].update(protected=False),
            'extra_ace':lambda s:s['roots']['state']['aces'].append(dict(sid='S-1-1-0',rights=2,type='Allow',inheritance=3,propagation=0)),
            'nonce':lambda s:s.update(nonce='0'*64),
            'untrusted_audit':lambda s:s.update(audit_trusted=False),
            'acl_readback':lambda s:s['roots']['code'].update(sddl='changed'),
        }
        # Each refusal owns a new isolated DB; no failed session is reset/replayed.
        for label,change in changes.items():
            with self.subTest(label=label):
                conn=sqlite3.connect(':memory:');self.addCleanup(conn.close)
                conn.execute('CREATE TABLE system_config(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT)');conn.commit()
                session=self.session();session.conn=conn;self.mutate=change
                with self.assertRaises(ValueError):session.execute(lambda s:'COMMITTED',self.verifier())
                self.assertTrue(authority.blocked(conn));self.assertEqual(session._records()[0][-1]['phase'],'UNKNOWN')
                with self.assertRaisesRegex(ValueError,'REPLAY'):session.execute(lambda s:self.fail('replayed'),self.verifier())

    def test_unknown_process_and_changed_file_never_release(self):
        self.install();self.stopped=False
        session=self.session()
        with self.assertRaisesRegex(ValueError,'PROCESS_NOT_QUIESCENT'):session.execute(lambda s:None,self.verifier())
        self.assertTrue(authority.blocked(self.conn))

    def test_actual_file_receipt_staging_and_torn_journal_refuse_release(self):
        self.install()
        exe=v.CODE/'service/RoktU1Bridge.exe';receipt=v.CODE/v.RECEIPT
        journal=v.AUDIT/('install-'+'a'*64+'.jsonl')
        stage=exe.with_name(exe.name+'.u1-new')
        for path,replacement in ((exe,b'changed'),(receipt,b'{}'),(stage,b'unknown'),(journal,journal.read_bytes().rstrip(b'\n'))):
            with self.subTest(path=path.name):
                before=path.read_bytes() if path.exists() else None
                path.write_bytes(replacement)
                try:
                    conn=sqlite3.connect(':memory:');self.addCleanup(conn.close)
                    conn.execute('CREATE TABLE system_config(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT)');conn.commit()
                    session=self.session();session.conn=conn
                    with self.assertRaises(ValueError):session.execute(lambda s:'COMMITTED',self.verifier())
                    self.assertTrue(authority.blocked(conn));self.assertEqual(session._records()[0][-1]['phase'],'UNKNOWN')
                finally:
                    if before is None:path.unlink()
                    else:path.write_bytes(before)

    def test_blob_content_tamper_preserves_original_maintenance(self):
        self.install()
        journal=v.AUDIT/('files-'+'a'*64+'.jsonl')
        header=json.loads(journal.read_bytes().splitlines()[0])
        self.assertIsNotNone(header['blob_store_identity'])
        reference=next(item['content'] for item in header['plan'] if item['content'] is not None)
        blob=journal.with_name(journal.name+'.blobs')/reference['sha256']
        blob.write_bytes(b'tampered isolated backup')
        session=self.session()
        with self.assertRaisesRegex(ValueError,'STOP_AND_PRESERVE_BLOB_CHANGED'):
            session.execute(lambda s:'COMMITTED',self.verifier())
        self.assertTrue(authority.blocked(self.conn))
        self.assertEqual(session._records()[0][-1]['phase'],'UNKNOWN')
        with self.assertRaisesRegex(ValueError,'REPLAY'):
            session.execute(lambda s:self.fail('replayed'),self.verifier())

    def test_complete_runtime_receipt_count_uses_package_admission_bound(self):
        files={f'runtime/file{i}.bin':'a'*64 for i in range(513)}
        verifier=v.InstallVerifier(files,observe=lambda *a:None,confirm_stopped=lambda *a:None)
        self.assertEqual(len(verifier.files),513)
        files={f'runtime/file{i}.bin':'a'*64 for i in range(v.MAX_RELEASE_FILES+1)}
        with self.assertRaisesRegex(ValueError,'EXPECTED_RELEASE'):
            v.InstallVerifier(files,observe=lambda *a:None,confirm_stopped=lambda *a:None)

    def test_early_process_death_explicit_recovery_restores_absent(self):
        result=self.host.run_coordinator(death='CODE_CREATE_VERIFIED')
        self.assertEqual(result.returncode,31)
        session=self.session(action='recover')
        proof=session.execute(lambda s:self.run_host(s,recover=True),self.verifier())
        self.assertEqual(proof['outcome'],'ROLLED_BACK');self.assertFalse(authority.blocked(self.conn))

    def test_real_windows_observer_rejects_untrusted_isolated_audit(self):
        # Windows PowerShell 5, real .NET ACL reads; only temp roots substituted.
        source=__import__('pathlib').Path('autonomy/windows/Observe-HostInstall.ps1').read_text(encoding='utf-8')
        for old,new in ((r'C:\ProgramData\RoktU1InstallAudit',v.AUDIT),(r'C:\Program Files\RoktU1Bridge\v1',v.CODE),(r'C:\ProgramData\RoktU1Bridge',v.STATE)):
            source=source.replace(old,str(new).replace("'","''"))
        command='& {'+source+'} -OperationId '+'a'*64+' -Nonce '+'b'*64
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',
                               base64.b64encode(command.encode('utf-16-le')).decode()],capture_output=True,timeout=15)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'STOP_AND_PRESERVE_OBSERVER_AUDIT_OWNER',result.stderr)
        self.assertFalse(v.CODE.exists());self.assertFalse(v.STATE.exists())

    def test_receipt_and_journal_strict_json(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}'):
            with self.assertRaises(ValueError):v.parse(raw)


if __name__=='__main__':unittest.main()

"""Isolated actual file lifecycle / 隔离真实文件生命周期。"""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from autonomy.host_file_transaction import HostFileTransaction, canonical, digest, read


class FileTransactionTests(unittest.TestCase):
    def test_blob_backed_large_payload_compensates_without_inline_journal(self):
        source=Path(self.temp.name)/'large.dll'
        source.write_bytes(b'x'*(17*1024*1024))
        t=self.tx();t.prepare({'runtime/large.dll':source},manifest_sha256='a'*64,blob_backed=True)
        self.assertLess(t.journal.stat().st_size,4096)
        t.apply()
        self.assertEqual(digest(read(self.root/'runtime/large.dll')),digest(read(source)))
        t.rollback();self.assertFalse((self.root/'runtime/large.dll').exists())

    def test_blob_tampering_stops_before_effect(self):
        source=Path(self.temp.name)/'source';source.write_bytes(b'original')
        t=self.tx();t.prepare({'runtime/lib.dll':source},manifest_sha256='a'*64,blob_backed=True)
        store=t.journal.with_name(t.journal.name+'.blobs')
        next(store.iterdir()).write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'BLOB_CHANGED'):t.apply()
        self.assertFalse((self.root/'runtime/lib.dll').exists())

    def test_blob_backed_interrupted_effect_is_compensated_not_replayed(self):
        source=Path(self.temp.name)/'source';source.write_bytes(b'original')
        def fault(phase,item):
            if phase=='APPLY_EFFECT':raise RuntimeError('power loss fixture')
        t=self.tx(fault=fault);t.prepare({'runtime/lib.dll':source},manifest_sha256='a'*64,blob_backed=True)
        with self.assertRaises(RuntimeError):t.apply()
        fresh=self.tx()
        with self.assertRaisesRegex(ValueError,'NO_FORWARD_REPLAY'):fresh.apply()
        fresh.rollback();self.assertFalse((self.root/'runtime/lib.dll').exists())

    def test_read_rejects_name_swap_before_open(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'target'; other=Path(d)/'other'
            target.write_bytes(b'original'); other.write_bytes(b'replacement')
            original_open=Path.open
            def swapped(path,*args,**kwargs):
                if path==target:
                    os.replace(other,target)
                return original_open(path,*args,**kwargs)
            with patch.object(Path,'open',swapped):
                with self.assertRaisesRegex(ValueError,'FILE_CHANGED'):read(target)

    def test_read_rejects_hardlink_created_before_open(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'target'; alias=Path(d)/'alias'
            target.write_bytes(b'original')
            original_open=Path.open
            def linked(path,*args,**kwargs):
                if path==target:os.link(target,alias)
                return original_open(path,*args,**kwargs)
            with patch.object(Path,'open',linked):
                with self.assertRaisesRegex(ValueError,'FILE_CHANGED'):read(target)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='u1-owned-files-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'code';self.root.mkdir()
        self.audit=Path(self.temp.name)/'audit';self.audit.mkdir()

    def tx(self, n='one', **kw):
        return HostFileTransaction(self.root,self.audit/(n+'.jsonl'),**kw)

    def files(self, **changes):
        files={'service/bridge.exe':b'MZ-first','config/obsolete.json':b'old'}
        files.update(changes)
        receipt=canonical(dict(schema='rokt.disabled-host-install-receipt.v2',files={k:digest(v) for k,v in files.items()}))
        files['config/installation.json']=receipt
        return files

    def install(self):
        t=self.tx();t.prepare(self.files(),manifest_sha256='a'*64);t.apply()
        return t

    def test_first_install_repeat_and_absent_rollback(self):
        t=self.install();self.assertEqual((self.root/'service/bridge.exe').read_bytes(),b'MZ-first')
        self.assertEqual(t.apply(),t.apply())
        with self.assertRaisesRegex(ValueError,'RECONCILE_ONLY'):t.prepare(self.files(),manifest_sha256='a'*64)
        t.rollback();t.rollback()
        self.assertFalse(any(p.is_file() for p in self.root.rglob('*')))
        with self.assertRaisesRegex(ValueError,'VERIFIED_FILE_PHASE'):t.receipt()

    def test_upgrade_new_replace_delete_and_restore_previous_receipt(self):
        self.install();previous=(self.root/'config/installation.json').read_bytes()
        new={'service/bridge.exe':b'MZ-second','runtime/new.json':b'new'}
        new['config/installation.json']=canonical(dict(schema='rokt.disabled-host-install-receipt.v2',files={k:digest(v) for k,v in new.items()}))
        t=self.tx('upgrade');t.prepare(new,manifest_sha256='b'*64,previous_receipt=previous,previous_receipt_sha256=digest(previous));t.apply()
        self.assertFalse((self.root/'config/obsolete.json').exists());self.assertTrue((self.root/'runtime/new.json').exists())
        t.rollback()
        self.assertEqual((self.root/'service/bridge.exe').read_bytes(),b'MZ-first')
        self.assertEqual((self.root/'config/obsolete.json').read_bytes(),b'old')
        self.assertFalse((self.root/'runtime/new.json').exists())
        self.assertEqual((self.root/'config/installation.json').read_bytes(),previous)

    def test_unowned_and_forged_receipt_rejected_before_intent(self):
        (self.root/'config').mkdir();p=self.root/'config/foreign';p.write_bytes(b'foreign')
        with self.assertRaisesRegex(ValueError,'UNOWNED'):self.tx().prepare({'config/foreign':b'x'},manifest_sha256='a'*64)
        forged=canonical(dict(schema='rokt.disabled-host-install-receipt.v2',files={'config/foreign':digest(b'foreign')}))
        with self.assertRaisesRegex(ValueError,'PINNED_OWNERSHIP'):self.tx().prepare({'config/new':b'x'},manifest_sha256='a'*64,previous_receipt=forged,previous_receipt_sha256=digest(forged))
        self.assertFalse((self.audit/'one.jsonl').exists());self.assertEqual(p.read_bytes(),b'foreign')

    def test_receipt_requires_verified_actual_bytes(self):
        t=self.tx();t.prepare(self.files(),manifest_sha256='a'*64)
        with self.assertRaisesRegex(ValueError,'VERIFIED_FILE_PHASE'):t.receipt()
        t.apply();(self.root/'service/bridge.exe').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'VERIFIED_FILE_PHASE'):t.receipt()
        with self.assertRaisesRegex(ValueError,'STOP_AND_PRESERVE'):t.rollback()
        self.assertTrue((self.root/'config/obsolete.json').exists())

    def test_reserved_staging_and_case_collisions_rejected(self):
        for files in ({'config/a':b'a','config/a.u1-new':b'b'},{'config/a':b'a','config/a.u1-new/b':b'b'},{'config/a':b'a','config/A':b'b'},{'config/a':b'a','config/a/b':b'b'},{'config/../x':b'x'}):
            with self.assertRaises(ValueError):self.tx().prepare(files,manifest_sha256='a'*64)
        self.assertFalse((self.audit/'one.jsonl').exists())

    def test_fault_at_every_apply_and_rollback_boundary(self):
        for phase in ('APPLY_INTENT','APPLY_EFFECT'):
            with self.subTest(phase=phase):
                t=self.tx(phase,fault=lambda p,n: (_ for _ in ()).throw(RuntimeError('injected')) if p==phase else None)
                t.prepare(self.files(),manifest_sha256='a'*64)
                with self.assertRaises(RuntimeError):t.apply()
                recovered=self.tx(phase)
                with self.assertRaisesRegex(ValueError,'NO_FORWARD_REPLAY'):recovered.apply()
                recovered.rollback();self.assertFalse(any(p.is_file() for p in self.root.rglob('*')))
        t=self.install()
        for phase in ('ROLLBACK_INTENT','ROLLBACK_EFFECT'):
            t.fault=lambda p,n: (_ for _ in ()).throw(RuntimeError('injected')) if p==phase else None
            with self.assertRaises(RuntimeError):t.rollback()
        self.tx().rollback();self.assertFalse(any(p.is_file() for p in self.root.rglob('*')))

    def test_real_process_exit_after_effect_and_during_rollback(self):
        t=self.tx();t.prepare(self.files(),manifest_sha256='a'*64)
        for action,phase in (('apply','APPLY_EFFECT'),('rollback','ROLLBACK_EFFECT')):
            code='from autonomy.host_file_transaction import HostFileTransaction; import os; t=HostFileTransaction('+repr(str(self.root))+','+repr(str(self.audit/'one.jsonl'))+',fault=lambda p,n: os._exit(29) if p=='+repr(phase)+' else None); t.'+action+'()'
            r=subprocess.run([sys.executable,'-B','-c',code],timeout=15,capture_output=True)
            self.assertEqual(r.returncode,29,r.stderr)
        self.tx().rollback();self.assertFalse(any(p.is_file() for p in self.root.rglob('*')))

    def test_torn_journal_and_unexpected_stage_preserved(self):
        t=self.install();p=self.root/'service/bridge.exe.u1-new';p.write_bytes(b'unknown')
        with self.assertRaisesRegex(ValueError,'STAGING_ARTIFACT'):t.rollback()
        p.unlink()
        with t.journal.open('ab') as f:f.write(b'{')
        before=(self.root/'service/bridge.exe').read_bytes()
        with self.assertRaisesRegex(ValueError,'TORN_JOURNAL'):t.rollback()
        self.assertEqual((self.root/'service/bridge.exe').read_bytes(),before)

    def test_created_roots_prune_process_exit_recovery(self):
        state=Path(self.temp.name)/'state'
        for phase in ('DIRECTORY_REMOVE_INTENT','DIRECTORY_REMOVE_EFFECT','ROOT_REMOVE_INTENT','ROOT_REMOVE_EFFECT','STATE_REMOVE_INTENT','STATE_REMOVE_EFFECT'):
            with self.subTest(phase=phase):
                self.root.mkdir(exist_ok=True);state.mkdir(exist_ok=True)
                t=self.tx(phase);t.prepare(self.files(),manifest_sha256='a'*64,root_created=True,state_root=state);t.apply();t.rollback()
                code='from autonomy.host_file_transaction import HostFileTransaction; import os; t=HostFileTransaction('+repr(str(self.root))+','+repr(str(self.audit/(phase+'.jsonl')))+',fault=lambda p,n: os._exit(29) if p=='+repr(phase)+' else None); t.prune_created_root()'
                r=subprocess.run([sys.executable,'-B','-c',code],timeout=20,capture_output=True)
                self.assertEqual(r.returncode,29,r.stderr)
                recovered=self.tx(phase);recovered.prune_created_root();recovered.prune_created_root()
                self.assertFalse(self.root.exists());self.assertFalse(state.exists())


if __name__=='__main__':unittest.main()

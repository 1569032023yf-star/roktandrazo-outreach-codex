"""Delivery fail-closed checks / 交付验证失败保护，仅临时测试输入。"""
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch

from autonomy.release_store import build_bundle
from tools.verify_u1_delivery import verify, verify_with_report


class DeliveryVerificationTests(unittest.TestCase):
    def test_completed_checks_survive_later_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(report=str(Path(tmp)/'report.json'),source_commit='a'*40,
                                 archive_sha256='b'*64,manifest_sha256='c'*64)
            def fail_after_check(args,progress):
                progress(dict(arguments=['fixture-import'],outcome='RUNNING'))
                progress(dict(arguments=['fixture-import'],outcome='PASSED',returncode=0,stdout='fixture',stderr=''))
                progress(dict(arguments=['fixture-http'],outcome='RUNNING'))
                raise ValueError('fixture failure')
            with patch('tools.verify_u1_delivery.verify',side_effect=fail_after_check):
                with self.assertRaises(ValueError):verify_with_report(args)
            state=json.loads(Path(args.report).read_text(encoding='utf-8'))
            self.assertEqual(state['outcome'],'FAILED')
            self.assertEqual(state['checks'][0]['outcome'],'PASSED')
            self.assertEqual(state['active_check']['arguments'],['fixture-http'])
            self.assertNotIn('offline_entrypoint_imports_verified',state)

    def test_failure_timeout_and_existing_report_preserve_false_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            for n,error in enumerate((ValueError('bad'),subprocess.TimeoutExpired('fixture',1))):
                args=SimpleNamespace(report=str(Path(tmp)/f'{n}.json'),source_commit='a'*40,
                                     archive_sha256='b'*64,manifest_sha256='c'*64)
                with patch('tools.verify_u1_delivery.verify',side_effect=error):
                    with self.assertRaises(type(error)):verify_with_report(args)
                state=json.loads(Path(args.report).read_text(encoding='utf-8'))
                self.assertEqual(state['outcome'],'UNKNOWN' if n else 'FAILED')
                for key in ('allow_install','allow_dispatch','allow_cancel_dispatch','smtp_enabled','production_ready'):
                    self.assertIs(state[key],False)
                with patch('tools.verify_u1_delivery.verify') as operation:
                    with self.assertRaises(FileExistsError):verify_with_report(args)
                    operation.assert_not_called()

    def test_source_and_gate_rejected_before_runtime_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            for n in range(2):
                root=Path(tmp)/str(n)
                delivery=dict(source_commit='a'*40,python_runtime_bundled=True,
                              allow_install=n==1,allow_dispatch=False,allow_cancel_dispatch=False,
                              smtp_enabled=False,production_ready=False)
                digest=build_bundle(root,{'DELIVERY.json':json.dumps(delivery).encode()},'a'*40)
                args=SimpleNamespace(archive='unused',archive_sha256='b'*64,output='unused',
                                     manifest_sha256=digest,source_commit='c'*40 if n==0 else 'a'*40)
                with patch('tools.verify_u1_delivery.extract_checked',return_value=root),patch('tools.verify_u1_delivery.subprocess.run') as run:
                    with self.assertRaisesRegex(ValueError,'SOURCE_MISMATCH' if n==0 else 'DELIVERY_BINDING_OR_GATE'):verify(args)
                    run.assert_not_called()

    def test_report_distinguishes_pin_and_final_integrity_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'bundle';(root/'payload').mkdir(parents=True)
            delivery=dict(source_commit='a'*40,python_runtime_bundled=True,
                          runtime_manifest_sha256='d'*64,allow_install=False,
                          allow_dispatch=False,allow_cancel_dispatch=False,
                          smtp_enabled=False,production_ready=False)
            (root/'payload/DELIVERY.json').write_text(json.dumps(delivery),encoding='utf-8')
            manifest=dict(source_commit='a'*40,files={'host/manifest.json':'e'*64})
            host=dict(files=[dict(path='runtime/python/U1_RUNTIME_CONTENT.json',sha256='d'*64)])
            for failure in ('FINAL_PIN_REVALIDATION','FINAL_MANIFEST_AND_PAYLOAD'):
                with self.subTest(failure=failure):
                    args=SimpleNamespace(report=str(Path(tmp)/(failure+'.json')),archive='unused',
                                         archive_sha256='b'*64,output='unused',
                                         manifest_sha256='c'*64,source_commit='a'*40)
                    store=MagicMock()
                    store._verify.side_effect=[manifest,ValueError('final failure')] if failure.startswith('FINAL_MANIFEST') else [manifest]
                    pins=MagicMock()
                    if failure=='FINAL_PIN_REVALIDATION':pins.revalidate.side_effect=ValueError('pin failure')
                    pin_context=MagicMock();pin_context.__enter__.return_value=pins
                    result=SimpleNamespace(returncode=0,stdout='ok',stderr='')
                    with patch('tools.verify_u1_delivery.extract_checked',return_value=root), \
                         patch('tools.verify_u1_delivery.ReleaseStore',return_value=store), \
                         patch('tools.verify_u1_delivery.InstallInputPins',return_value=pin_context), \
                         patch('tools.verify_u1_delivery.pin_package',return_value=host), \
                         patch('tools.verify_u1_delivery.pin_python_runtime'), \
                         patch('tools.verify_u1_delivery.subprocess.run',return_value=result):
                        with self.assertRaises(ValueError):verify_with_report(args)
                    state=json.loads(Path(args.report).read_text(encoding='utf-8'))
                    self.assertEqual(state['outcome'],'FAILED')
                    self.assertEqual(state['active_phase']['phase'],failure)
                    self.assertEqual(state['active_phase']['outcome'],'RUNNING')
                    self.assertEqual(len(state['checks']),4)
                    self.assertTrue(all(item['outcome']=='PASSED' for item in state['checks']))
                    self.assertIs(state['production_ready'],False)
                    completed=[item['phase'] for item in state['phases']]
                    self.assertIn('HOST_AND_RUNTIME_PINNING',completed)
                    self.assertEqual('FINAL_PIN_REVALIDATION' in completed,
                                     failure=='FINAL_MANIFEST_AND_PAYLOAD')


if __name__=='__main__':unittest.main()

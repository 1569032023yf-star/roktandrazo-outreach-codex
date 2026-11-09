"""Delivery fail-closed checks / 交付验证失败保护，仅临时测试输入。"""
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from autonomy.release_store import build_bundle
from tools.verify_u1_delivery import (BOOTSTRAP_STAGES, bootstrap_stage_timings,
                                      verify, verify_with_report)


class DeliveryVerificationTests(unittest.TestCase):
    def test_bootstrap_markers_accept_only_ordered_fixed_bounded_values(self):
        raw = (b'U1_BOOTSTRAP_STAGE init 0.000001\n'
               b'SECRET arbitrary child output\n'
               b'U1_BOOTSTRAP_STAGE stage 1.000000\n'
               b'U1_BOOTSTRAP_STAGE activate 121.000000\n'
               b'U1_BOOTSTRAP_STAGE SECRET 2.000000\n'
               b'U1_BOOTSTRAP_STAGE resolve 2.000000\n')
        self.assertEqual(bootstrap_stage_timings(raw), [
            dict(stage='init', elapsed_seconds=0.000001),
            dict(stage='stage', elapsed_seconds=1.0)])
        self.assertEqual(bootstrap_stage_timings(None), [])

    def probe_fixture(self, tmp, bootstrap_result):
        root=Path(tmp)/'extracted'; (root/'payload').mkdir(parents=True)
        delivery=dict(source_commit='a'*40,python_runtime_bundled=True,
                      runtime_manifest_sha256='d'*64,allow_install=False,
                      allow_dispatch=False,allow_cancel_dispatch=False,
                      smtp_enabled=False,production_ready=False)
        (root/'payload'/'DELIVERY.json').write_text(json.dumps(delivery),encoding='utf-8')
        args=SimpleNamespace(report=str(Path(tmp)/'report.json'),archive='fixture',
            archive_sha256='b'*64,manifest_sha256='c'*64,source_commit='a'*40,output='unused')
        pins=MagicMock(); pins.__enter__.return_value=pins
        store=MagicMock(); store._verify.return_value=dict(source_commit='a'*40,
                                                           files={'host/manifest.json':'e'*64})
        manifest=dict(files=[dict(path='runtime/python/U1_RUNTIME_CONTENT.json',sha256='d'*64)])
        ok=SimpleNamespace(returncode=0,stdout='',stderr='')
        with patch('tools.verify_u1_delivery.extract_checked',return_value=root), \
             patch('tools.verify_u1_delivery.ReleaseStore',return_value=store), \
             patch('tools.verify_u1_delivery.InstallInputPins',return_value=pins), \
             patch('tools.verify_u1_delivery.pin_package',return_value=manifest), \
             patch('tools.verify_u1_delivery.pin_python_runtime'), \
             patch('tools.verify_u1_delivery.subprocess.run',side_effect=[ok,ok,ok,ok,bootstrap_result]) as run:
            try:
                verify_with_report(args)
            except (subprocess.TimeoutExpired, ValueError):
                pass
            self.assertEqual([call.kwargs['timeout'] for call in run.call_args_list], [120]*5)
        return json.loads(Path(args.report).read_text(encoding='utf-8'))

    def test_bootstrap_timeout_records_only_safe_stage_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            error=subprocess.TimeoutExpired('SECRET_COMMAND',120,output=b'SECRET_STDOUT',
                stderr=b'U1_BOOTSTRAP_STAGE init 0.000001\n'
                       b'U1_BOOTSTRAP_STAGE stage 3.500000\nSECRET_STDERR\n')
            state=self.probe_fixture(tmp,error)
            self.assertEqual(state['outcome'],'UNKNOWN')
            self.assertEqual(state['error'],'BOOTSTRAP_PROBE_ERROR')
            self.assertEqual(state['checks'][-1]['outcome'],'UNKNOWN')
            self.assertEqual(state['checks'][-1]['stage_timings'][-1]['stage'],'stage')
            self.assertNotIn('SECRET',json.dumps(state))
            for key in ('allow_install','allow_dispatch','allow_cancel_dispatch','smtp_enabled','production_ready'):
                self.assertIs(state[key],False)

    def test_bootstrap_success_requires_cleanup_marker_and_hides_child_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            markers=''.join(f'U1_BOOTSTRAP_STAGE {stage} {n}.000000\n'
                            for n,stage in enumerate(BOOTSTRAP_STAGES))
            result=SimpleNamespace(returncode=0,stdout='SECRET_STDOUT',
                                   stderr=markers+'SECRET_STDERR\n')
            state=self.probe_fixture(tmp,result)
            self.assertEqual(state['outcome'],'VERIFIED')
            self.assertTrue(state['packaged_startup_preflight_verified'])
            self.assertEqual(state['checks'][-1]['stage_timings'][-1]['stage'],'complete')
            self.assertNotIn('SECRET',json.dumps(state))

    def test_bootstrap_zero_exit_without_cleanup_completion_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            markers=''.join(f'U1_BOOTSTRAP_STAGE {stage} {n}.000000\n'
                            for n,stage in enumerate(BOOTSTRAP_STAGES[:-1]))
            state=self.probe_fixture(tmp,SimpleNamespace(returncode=0,stdout='',stderr=markers))
            self.assertEqual(state['outcome'],'FAILED')
            self.assertEqual(state['checks'][-1]['outcome'],'FAILED')
            self.assertNotIn('packaged_startup_preflight_verified',state)

    def test_extraction_interruption_records_stage_before_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(report=str(Path(tmp)/'report.json'),source_commit='a'*40,
                archive='fixture',archive_sha256='b'*64,manifest_sha256='c'*64,output='unused')
            with patch('tools.verify_u1_delivery.extract_checked',side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt): verify_with_report(args)
            state=json.loads(Path(args.report).read_text(encoding='utf-8'))
            self.assertEqual(state['outcome'],'UNKNOWN')
            self.assertEqual(state['active_check']['stage'],'extract_archive')
            self.assertEqual(state['checks'],[])

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


if __name__=='__main__':unittest.main()

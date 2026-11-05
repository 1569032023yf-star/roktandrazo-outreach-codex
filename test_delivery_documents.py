"""Delivery document inclusion / 交付说明入包；宿主编译为测试替身。"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from autonomy.build_u1_delivery import build, DISCOVERY_ROOT_SOURCES


class DeliveryDocumentsTests(unittest.TestCase):
    def test_fixed_git_documents_in_both_archives(self):
        source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        def host_fixture(destination,source):
            destination.mkdir();(destination/'fixture.txt').write_bytes(b'not a compiled host')
            return {'manifest_sha256':'a'*64}
        with tempfile.TemporaryDirectory() as tmp,patch('autonomy.build_u1_delivery.build_development',side_effect=host_fixture):
            out=Path(tmp)/'delivery';result=build(out,source)
            manifest=json.loads((out/'install/manifest.json').read_bytes())
            documents={'README.md':'autonomy/windows/U1-OFFLINE-DELIVERY.md',
                       'dependencies/cpython-input.lock.json':'autonomy/windows/cpython-input.lock.json',
                       'dependencies/business-wheels.lock.json':'autonomy/windows/business-wheels.lock.json'}
            for name,path in documents.items():
                expected=subprocess.check_output(['git','show',source+':'+path])
                self.assertEqual(manifest['files'][name],hashlib.sha256(expected).hexdigest())
                with zipfile.ZipFile(out/'install.zip') as z:self.assertEqual(z.read('payload/'+name),expected)
                with zipfile.ZipFile(out/'rollback-tools.zip') as z:
                    self.assertEqual(z.read('OFFLINE-DELIVERY.md' if name=='README.md' else name),expected)
            for path in ('discovery/providers/contracts.py', 'discovery/providers/base.py',
                         'discovery/providers/google_places.py', 'discovery/providers/browser_maps.py',
                         'discovery/providers/serpapi_maps.py', *DISCOVERY_ROOT_SOURCES):
                expected=subprocess.check_output(['git','show',source+':'+path])
                with zipfile.ZipFile(out/'install.zip') as z:
                    self.assertEqual(z.read('payload/python/'+path),expected)
            self.assertFalse(result['package_complete'])
            self.assertFalse(result['python_runtime_bundled'])
            self.assertEqual(set(result['artifacts']),{'install.zip','rollback-tools.zip'})

    def test_build_phase_arguments_refuse_missing_binding_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'not-created'
            for args in [dict(prepare_only=True),dict(prepared_host=tmp),
                         dict(prepared_host=tmp,prepared_host_manifest_sha256='a'*64)]:
                with self.assertRaises(ValueError):build(out,'a'*40,**args)
                self.assertFalse(out.exists())

    def test_prepared_host_orchestration_pins_until_finalization(self):
        # Explicit orchestration fixture, not real host/runtime acceptance.
        source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);host=root/'host';host.mkdir()
            runtime=host/'runtime/python';runtime.mkdir(parents=True)
            content=runtime/'U1_RUNTIME_CONTENT.json';content.write_bytes(b'fixture runtime')
            digest=hashlib.sha256(content.read_bytes()).hexdigest()
            manifest=dict(schema='rokt.disabled-host-package.v2',files=[dict(path='runtime/python/U1_RUNTIME_CONTENT.json',sha256=digest,size=15)],scripts=[])
            (host/'manifest.json').write_text(json.dumps(manifest))
            from unittest.mock import MagicMock
            pins=MagicMock();pins.__enter__.return_value=pins
            pins.add.side_effect=lambda path,digest,limit: Path(path).read_bytes()
            with patch('publisher_channel.install_inputs.InstallInputPins',return_value=pins),patch('publisher_channel.install_inputs.pin_package',return_value=manifest):
                out=root/'delivery'
                result=build(out,source,python_runtime=runtime,runtime_manifest_sha256=digest,prepared_host=host,prepared_host_manifest_sha256='a'*64)
                pins.revalidate.assert_called_once()
                with zipfile.ZipFile(out/'install.zip') as z:
                    self.assertEqual(z.read('payload/host/runtime/python/U1_RUNTIME_CONTENT.json'),b'fixture runtime')
                self.assertTrue((out/'BUILD.json').exists())
                self.assertFalse((out/'install').exists())
                pins.revalidate.side_effect=ValueError('IDENTITY_CHANGED')
                failed=root/'failed'
                with self.assertRaisesRegex(ValueError,'IDENTITY_CHANGED'):
                    build(failed,source,python_runtime=runtime,runtime_manifest_sha256=digest,prepared_host=host,prepared_host_manifest_sha256='a'*64)
                self.assertFalse((failed/'BUILD.json').exists())
                self.assertTrue((failed/'install.zip').exists())


if __name__=='__main__':unittest.main()

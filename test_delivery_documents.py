"""Delivery document inclusion / 交付说明入包；宿主编译为测试替身。"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from autonomy.build_u1_delivery import build


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
            self.assertFalse(result['package_complete'])
            self.assertFalse(result['python_runtime_bundled'])
            self.assertEqual(set(result['artifacts']),{'install.zip','rollback-tools.zip'})


if __name__=='__main__':unittest.main()

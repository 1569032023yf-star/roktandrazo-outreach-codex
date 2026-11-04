"""Rollback parity fixtures / 回滚对应关系测试输入，不执行回滚。"""
from pathlib import Path
import tempfile
import unittest

from autonomy.release_store import build_bundle
from tools.verify_u1_rollback_archive import verify_parity


class RollbackArchiveParityTests(unittest.TestCase):
    def test_exact_component_set_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);install=root/'install';rollback=root/'rollback';rollback.mkdir()
            files={'host/runtime/python/empty.py':b'',
                   'host/service/fixture.exe':b'not executable',
                   'python/autonomy/release_store.py':b'# fixture',
                   'README.md':b'bilingual fixture',
                   'dependencies/fixture.json':b'{}'}
            digest=build_bundle(install,files,'a'*40)
            for name,raw in files.items():
                target=rollback/('release_store.py' if name.startswith('python/') else 'OFFLINE-DELIVERY.md' if name=='README.md' else name)
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
            (rollback/'README.md').write_bytes(b'archive-specific fixture instructions')
            result=verify_parity(install,digest,'a'*40,rollback)
            self.assertTrue(result['rollback_archive_parity_verified']);self.assertFalse(result['rollback_verified'])
            with self.assertRaisesRegex(ValueError,'SOURCE_MISMATCH'):verify_parity(install,digest,'b'*40,rollback)
            (rollback/'extra.pth').write_bytes(b'unlisted')
            with self.assertRaisesRegex(ValueError,'FILE_SET'):verify_parity(install,digest,'a'*40,rollback)
            (rollback/'extra.pth').unlink()
            (rollback/'host/runtime/python/empty.py').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'COMPONENT_MISMATCH'):verify_parity(install,digest,'a'*40,rollback)


if __name__=='__main__':unittest.main()

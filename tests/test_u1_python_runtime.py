"""Offline archive admission / 离线归档准入；no installation."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.prepare_u1_python_runtime import prepare
from tools.assemble_u1_runtime import wheel_requirements


class RuntimeAdmissionTests(unittest.TestCase):
    def check_rejected(self, entries, reason, wrong_hash=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root/'input.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                for name, data in entries:
                    item = zipfile.ZipInfo('placeholder')
                    item.filename = name  # Preserve hostile bytes on Windows too.
                    z.writestr(item, data)
            digest = '0'*64 if wrong_hash else hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, reason):
                prepare(archive, digest, root/'runtime')
            self.assertFalse((root/'runtime').exists())
            self.assertFalse((root/'escape').exists())

    def test_wrong_archive_hash_never_extracts(self):
        self.check_rejected([('python.exe', b'untrusted')], 'ARCHIVE_HASH_MISMATCH', True)

    def test_windows_path_attacks_never_extract(self):
        for name in ('../escape', '/escape', 'C:/escape', 'a\\escape',
                     'a/../escape', 'NUL.txt', 'python.exe:stream', 'a./escape'):
            with self.subTest(name=name):
                self.check_rejected([(name, b'bad')], 'ARCHIVE_PATH')

    def test_case_collision_never_extracts(self):
        self.check_rejected([('Python.exe', b'a'), ('python.exe', b'b')], 'ARCHIVE_COLLISION')

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root/'input.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('python.exe', b'x')
            output = root/'runtime'
            output.mkdir()
            (output/'keep').write_bytes(b'original')
            with self.assertRaisesRegex(ValueError, 'NEW_OUTPUT_REQUIRED'):
                prepare(archive, hashlib.sha256(archive.read_bytes()).hexdigest(), output)
            self.assertEqual((output/'keep').read_bytes(), b'original')

    def test_wheel_lock_rejects_tampering_and_injection(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = Path(tmp)/'demo-1.0-py3-none-any.whl'
            wheel.write_bytes(b'locked bytes')
            row = dict(name='demo',version='1.0',wheel=wheel.name,
                       sha256=hashlib.sha256(wheel.read_bytes()).hexdigest())
            lock = dict(schema='rokt.u1-business-wheel-input.v1',wheels=[row])
            self.assertIn('demo==1.0 --hash=sha256:',wheel_requirements(lock,tmp))
            for key, value in (('name','demo\n--index-url evil'),
                               ('version','1.0\n--trusted-host evil'),
                               ('wheel','../escape.whl'),('sha256','0'*64)):
                with self.subTest(key=key):
                    bad = dict(lock,wheels=[dict(row,**{key:value})])
                    with self.assertRaisesRegex(ValueError,'WHEEL_LOCK_VALUE|WHEEL_HASH'):
                        wheel_requirements(bad,tmp)
            with self.assertRaisesRegex(ValueError,'DUPLICATE_WHEEL_PROJECT'):
                wheel_requirements(dict(lock,wheels=[row,dict(row,name='DEMO')]),tmp)


if __name__ == '__main__':
    unittest.main()

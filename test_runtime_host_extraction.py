"""Archive boundary checks / 压缩包边界检查，纯临时文件。"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

from tools.verify_u1_runtime_host import extract_checked,verify_with_report


class RuntimeHostExtractionTests(unittest.TestCase):
    def test_failure_and_timeout_reports_never_claim_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            for number,error in enumerate((ValueError('bad archive'),subprocess.TimeoutExpired('fixture',1))):
                path=Path(tmp)/f'{number}.json'
                args=SimpleNamespace(report=str(path),source_commit='a'*40,archive_sha256='b'*64,
                                     manifest_sha256='c'*64,archive='fixture',output='unused')
                with patch('tools.verify_u1_runtime_host.verify',side_effect=error):
                    with self.assertRaises(type(error)):verify_with_report(args)
                report=json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(report['outcome'],'UNKNOWN' if number else 'FAILED')
                self.assertFalse(report['extracted_runtime_verified'])
                with patch('tools.verify_u1_runtime_host.verify') as operation:
                    with self.assertRaises(FileExistsError):verify_with_report(args)
                    operation.assert_not_called()

    def test_exact_archive_empty_file_and_timezone_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'host.zip'
            with zipfile.ZipFile(archive,'x') as z:
                z.writestr('runtime/python/Lib/empty.py',b'')
                z.writestr('runtime/python/Lib/GMT+0',b'timezone fixture')
            output=root/'out';digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            extract_checked(archive,digest,output)
            self.assertEqual((output/'runtime/python/Lib/empty.py').read_bytes(),b'')
            with self.assertRaisesRegex(ValueError,'NEW_EXTRACTION_REQUIRED'):extract_checked(archive,digest,output)

    def test_wrong_hash_and_unsafe_members_leave_output_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for number,names in enumerate((['../outside'],['A','a'],['a','a/b'],['runtime\\outside'])):
                archive=root/f'{number}.zip'
                with zipfile.ZipFile(archive,'x') as z:
                    for name in names:
                        info=zipfile.ZipInfo(name)
                        # Preserve raw backslashes rather than letting the
                        # Windows writer normalize this attack fixture first.
                        info.filename=name;info.orig_filename=name
                        z.writestr(info,b'fixture')
                digest=hashlib.sha256(archive.read_bytes()).hexdigest();output=root/f'out{number}'
                with self.assertRaises(ValueError):extract_checked(archive,digest,output)
                self.assertFalse(output.exists())
            with self.assertRaisesRegex(ValueError,'ARCHIVE_HASH_MISMATCH'):extract_checked(archive,'0'*64,root/'wrong')
            self.assertFalse((root/'wrong').exists())

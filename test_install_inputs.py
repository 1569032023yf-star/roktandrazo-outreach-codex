"""Real Windows input handles, isolated files only / 真实Windows输入句柄，仅临时文件。"""
import hashlib
import ctypes
import json
import os
from pathlib import Path
import tempfile
import unittest

from autonomy.disabled_host_package import build_package,canonical,RUNTIME_PATHS
from publisher_channel.install_inputs import InstallInputPins,pin_package


class InstallInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='u1-input-pins-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.artifacts={'service/RoktU1Bridge.exe':b'MZ-isolated',
            'config/host.json':canonical(dict(schema='rokt.disabled-host-config.v1',inventory_id='1784775229336',service_name='RoktU1Bridge',allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False,scheduler_created=False)),
            'runtime/dependencies.json':canonical(dict(schema='rokt.disabled-host-runtime.v1',framework='.NET Framework 4 x64',files={k:dict(path=v,sha256='a'*64,version='4.8.0.0') for k,v in RUNTIME_PATHS.items()}))}
        self.package=self.root/'package'
        self.result=build_package(self.package,self.artifacts,{k:self.sha(v) for k,v in self.artifacts.items()},source_commit='a'*40)

    @staticmethod
    def sha(raw):return hashlib.sha256(raw).hexdigest()

    def test_mutable_reference_rejects_links_and_missing_files_without_creation(self):
        path=self.root/'original.sqlite';path.write_bytes(b'fixture')
        alias=self.root/'alias.sqlite';os.link(path,alias)
        with InstallInputPins() as pins:
            with self.assertRaisesRegex(ValueError,'MUTABLE_REFERENCE_CHANGED'):pins.add_mutable_reference(path)
        with InstallInputPins() as pins:
            missing=self.root/'absent.sqlite'
            with self.assertRaises(OSError):pins.add_mutable_reference(missing)
            self.assertFalse(missing.exists())
        alias.unlink()
        with InstallInputPins() as pins:
            pins.add_mutable_reference(path)
            with self.assertRaisesRegex(ValueError,'CONFLICTING_PIN'):pins.add(path,self.sha(b'fixture'))

    def test_package_pins_deny_file_write_delete_and_ancestor_rename_until_closed(self):
        path=self.package/'service/RoktU1Bridge.exe'
        with InstallInputPins() as pins:
            manifest=pin_package(pins,self.package,self.result['manifest_sha256'],'a'*40)
            self.assertFalse(manifest['allow_install'])
            with self.assertRaises(OSError):path.write_bytes(b'changed')
            with self.assertRaises(OSError):path.unlink()
            with self.assertRaises(OSError):self.package.rename(self.root/'moved')
            with self.assertRaises(OSError):path.parent.rename(self.package/'other')
            self.assertTrue(pins.revalidate())
        path.write_bytes(b'after-close');self.assertEqual(path.read_bytes(),b'after-close')
        with self.assertRaisesRegex(ValueError,'PINS_NOT_ACTIVE'):pins.revalidate()
        with self.assertRaisesRegex(ValueError,'SINGLE_USE'):pins.__enter__()

    def test_independent_manifest_and_source_approval_required(self):
        with InstallInputPins() as pins:
            with self.assertRaisesRegex(ValueError,'DIGEST_MISMATCH'):pin_package(pins,self.package,'f'*64,'a'*40)
        with InstallInputPins() as pins:
            with self.assertRaisesRegex(ValueError,'MANIFEST_CONTRACT'):pin_package(pins,self.package,self.result['manifest_sha256'],'b'*40)

    def test_hardlink_and_writer_already_open_refuse_pinning(self):
        path=self.root/'file';path.write_bytes(b'known');alias=self.root/'alias';os.link(path,alias)
        with InstallInputPins() as pins:
            with self.assertRaisesRegex(ValueError,'LINKS_OR_SIZE'):pins.add(path,self.sha(b'known'))
        alias.unlink()
        with path.open('r+b'):
            with InstallInputPins() as pins:
                with self.assertRaises(OSError):pins.add(path,self.sha(b'known'))

    def test_system_component_policy_cannot_admit_arbitrary_path_and_alias_cannot_write(self):
        path=self.root/'ordinary';path.write_bytes(b'known');alias=self.root/'alias';os.link(path,alias)
        with InstallInputPins() as pins:
            with self.assertRaisesRegex(ValueError,'FIXED_SYSTEM_COMPONENT_REQUIRED'):pins.add_system_component(path,self.sha(b'known'))
            # Probe the underlying Windows sharing contract in writable temp
            # storage, without changing the closed production component paths.
            pins._add(path,self.sha(b'known'),limit=256,system_component=True)
            with self.assertRaises(OSError) as caught:alias.write_bytes(b'changed')
            self.assertEqual(caught.exception.errno,13)
            handle=pins.api.CreateFileW(str(alias),0x40000000,7,None,3,0x00200000,None)
            self.assertEqual(handle,ctypes.c_void_p(-1).value)
            self.assertEqual(ctypes.get_last_error(),32)
            # Removing a different hardlink may be allowed by Windows. It
            # cannot remove/replace the pinned name or change its bytes.
            alias.unlink()
            with self.assertRaises(OSError):path.unlink()
            self.assertEqual(path.read_bytes(),b'known')
            self.assertTrue(pins.revalidate())

    def test_reparse_ancestor_refused(self):
        import subprocess
        target=self.root/'target';target.mkdir();(target/'data').write_bytes(b'known')
        link=self.root/'junction'
        # Isolated junction creation only; native cmd has no PowerShell pipeline.
        result=subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(link),str(target)],capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.addCleanup(lambda:link.rmdir() if link.exists() else None)
        with InstallInputPins() as pins:
            with self.assertRaisesRegex(ValueError,'REPARSE_OR_TYPE'):pins.add(link/'data',self.sha(b'known'))

    def test_unknown_script_and_unsafe_config_rejected_even_with_updated_manifest_hash(self):
        original=self.result['manifest']
        for change in ('script','config'):
            manifest=json.loads(json.dumps(original))
            if change=='script':manifest['scripts'][0]['path']='unapproved.ps1'
            else:
                raw=canonical(dict(json.loads(self.artifacts['config/host.json']),smtp_enabled=True))
                (self.package/'config/host.json').write_bytes(raw)
                row=next(r for r in manifest['files'] if r['path']=='config/host.json');row.update(sha256=self.sha(raw),size=len(raw))
            raw=canonical(manifest);(self.package/'manifest.json').write_bytes(raw)
            with InstallInputPins() as pins:
                with self.assertRaisesRegex(ValueError,'EXACT_SCRIPT_SET|UNSAFE_HOST_CONFIG'):pin_package(pins,self.package,self.sha(raw),'a'*40)


if __name__=='__main__':unittest.main()

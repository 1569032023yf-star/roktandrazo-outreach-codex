"""Smoke-test pinned Git bytes in an isolated temporary package, never production."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent
MANIFEST=ROOT/'autonomy/evidence/unattended_20261026/SOURCE_CANDIDATE_MANIFEST.json'


class ManifestClosureTests(unittest.TestCase):
    def stage(self,target,omit=None):
        manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
        self.assertFalse(manifest['RELEASE_READY'])
        modules=[]
        for entry in manifest['files']:
            relative=Path(entry['path'])
            self.assertFalse(relative.is_absolute())
            self.assertNotIn('..',relative.parts)
            blob=subprocess.check_output(['git','show',manifest['source_commit']+':'+entry['path']],cwd=ROOT)
            self.assertEqual(hashlib.sha256(blob).hexdigest(),entry['sha256'])
            if entry['path']==omit:continue
            path=target/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(blob)
            if path.suffix=='.py':modules.append('.'.join(relative.with_suffix('').parts))
        return modules

    def probe(self,target,modules):
        script='''import sys,importlib,json,sqlite3
from pathlib import Path
root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root))
for name in json.loads(sys.argv[2]):
 module=importlib.import_module(name)
 assert Path(module.__file__).resolve().is_relative_to(root)
from autonomy.growth_ledger import day_start,business_day
assert business_day(day_start('2026-10-26'))=='2026-10-26'
assert hasattr(sqlite3.Connection,'deserialize')
for name,module in list(sys.modules.items()):
 if name.startswith('autonomy.') and getattr(module,'__file__',None):
  assert Path(module.__file__).resolve().is_relative_to(root)
print('ISOLATED_SOURCE_CLOSURE_OK')
'''
        return subprocess.run([sys.executable,'-I','-B','-c',script,str(target),json.dumps(modules)],
                              cwd=target,capture_output=True,text=True,timeout=30)

    def test_pinned_manifest_imports_without_checkout(self):
        with tempfile.TemporaryDirectory(prefix='u1-package-') as temp:
            root=Path(temp);result=self.probe(root,self.stage(root))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),'ISOLATED_SOURCE_CLOSURE_OK')

    def test_missing_local_dependency_does_not_fall_back_to_checkout(self):
        with tempfile.TemporaryDirectory(prefix='u1-package-') as temp:
            root=Path(temp);result=self.probe(root,self.stage(root,'autonomy/unattended_policy.py'))
            self.assertNotEqual(result.returncode,0)
            self.assertIn('ModuleNotFoundError',result.stderr)


if __name__=='__main__':unittest.main()

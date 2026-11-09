"""Large runtime manifest parity / 大运行时清单一致性，纯离线临时文件。"""
import json
import os
from pathlib import Path
import tempfile
import unittest

from autonomy.release_store import ReleaseStore,build_bundle_from_paths,canonical,checked_manifest
from autonomy.windows.u1_bootstrap import resolve_release


@unittest.skipUnless(os.name=='nt','Windows bootstrap attributes')
class LargeRuntimeReleaseTests(unittest.TestCase):
    def test_large_file_count_empty_files_and_timezone_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'empty';source.write_bytes(b'')
            files={f'runtime/python/Lib/file{i}.py':source for i in range(520)}
            files.update({f'python/autonomy/{n}.py':source for n in ('u1_host_runtime','host_readonly_http','release_store')})
            files['runtime/python/Lib/tzdata/GMT+0']=source
            store=root/'store';store.mkdir();versions=store/'versions';versions.mkdir()
            stage=root/'package';version=build_bundle_from_paths(stage,files,'a'*40)
            folder=versions/version;stage.rename(folder)
            (store/'active.json').write_bytes(canonical(dict(schema='rokt.release-store.v1',inventory_id='1784775229336',version=version)))
            self.assertEqual(len(ReleaseStore(store)._verify(folder,version)['files']),524)
            self.assertEqual(resolve_release(store),folder/'payload/python')
            legacy=json.loads((folder/'manifest.json').read_bytes());legacy['schema']='rokt.release-store.v1'
            with self.assertRaisesRegex(ValueError,'INVALID_MANIFEST'):checked_manifest(canonical(legacy))
            (folder/'payload/runtime/python/Lib/extra.pth').write_bytes(b'unlisted')
            with self.assertRaisesRegex(ValueError,'UNMANAGED_FILES'):ReleaseStore(store)._verify(folder,version)
            with self.assertRaisesRegex(ValueError,'UNMANAGED_FILES'):resolve_release(store)

    def test_case_collision_and_traversal_rejected_before_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.write_bytes(b'fixture')
            for names in ({'A':source,'a':source},{'../escape':source}):
                with self.assertRaises(ValueError):build_bundle_from_paths(root/'out',names,'a'*40)
                self.assertFalse((root/'out').exists())


class ManifestNamespaceTests(unittest.TestCase):
    def manifest(self, names):
        return canonical(dict(schema='rokt.release-manifest.v2',
            inventory_id='1784775229336',source_commit='a'*40,
            files={name:'b'*64 for name in names}))

    def test_ancestors_collide_in_both_orders_and_case(self):
        for names in [('A','a/b'),('a/b','A'),('a/b/c','A/B'),
                      ('a','a+suffix','a/b'),('A','a')]:
            with self.subTest(names=names):
                with self.assertRaisesRegex(ValueError,'PATH_COLLISION'):
                    checked_manifest(self.manifest(names))

    def test_siblings_maximum_count_and_deep_path(self):
        names=['a','a+suffix','ab/c','dir/a','dir/ab']
        self.assertEqual(len(checked_manifest(self.manifest(names))['files']),5)
        names=[f'runtime/python/Lib/module{i}.py' for i in range(8192)]
        self.assertEqual(len(checked_manifest(self.manifest(names))['files']),8192)
        deep='/'.join(['a']*10000)
        self.assertEqual(len(checked_manifest(self.manifest([deep,'sibling']))['files']),2)
        with self.assertRaisesRegex(ValueError,'PATH_COLLISION'):
            checked_manifest(self.manifest([deep,deep+'/child']))

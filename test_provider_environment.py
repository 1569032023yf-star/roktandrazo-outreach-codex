import hashlib
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
from autonomy.provider_environment import load_pinned_provider_environment, pinned_provider_environment


class ProviderEnvironmentTests(unittest.TestCase):
    def config(self, root, environment=None, raw=None):
        raw = raw or json.dumps(dict(schema='rokt.provider-environment.v1', environment=environment or {
            'WORKBUDDY_DISCOVERY_PROVIDER':'google_places', 'GOOGLE_MAPS_API_KEY':'fixture-only'})).encode()
        path = root / 'provider.json'
        path.write_bytes(raw)
        return path, hashlib.sha256(raw).hexdigest()

    def test_real_windows_pins_accept_exact_file_and_reject_hash_or_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,digest=self.config(root)
            self.assertEqual(load_pinned_provider_environment(path,digest)['GOOGLE_MAPS_API_KEY'],'fixture-only')
            with self.assertRaises(ValueError):load_pinned_provider_environment(path,'0'*64)
            os.link(path,root/'alias.json')
            with self.assertRaises(ValueError):load_pinned_provider_environment(path,digest)

    def test_lifetime_pin_blocks_mutation_and_releases_without_environment_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,digest=self.config(root)
            before=dict(os.environ)
            with pinned_provider_environment(path,digest) as environment:
                self.assertEqual(environment['WORKBUDDY_DISCOVERY_PROVIDER'],'google_places')
                with self.assertRaises(OSError):path.write_bytes(b'changed')
                with self.assertRaises(OSError):path.unlink()
                self.assertEqual(dict(os.environ),before)
            path.write_bytes(b'released')
            self.assertEqual(path.read_bytes(),b'released')

    def test_no_security_switch_or_mock_provider_or_duplicate_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for env in ({'WORKBUDDY_DISCOVERY_PROVIDER':'mock'},
                        {'WORKBUDDY_DISCOVERY_PROVIDER':'serpapi_maps'},
                        {'WORKBUDDY_DISCOVERY_PROVIDER':'google_places','smtp_enabled':'true'}):
                path,digest=self.config(root,env)
                with self.assertRaises(ValueError):load_pinned_provider_environment(path,digest)
            path,digest=self.config(root,raw=b'{"schema":"rokt.provider-environment.v1","environment":{},"environment":{}}')
            with self.assertRaisesRegex(ValueError,'DUPLICATE'):load_pinned_provider_environment(path,digest)

    def test_browser_file_paths_are_independent_of_launch_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for key,values in {
                'BROWSER_MAPS_CACHE_DIR':['','cache','../cache','D:cache'],
                'BROWSER_MAPS_JSON_FILE':['input.json','../input.json','D:input.json'],
            }.items():
                for value in values:
                    with self.subTest(key=key,value=value):
                        path,digest=self.config(root,{'WORKBUDDY_DISCOVERY_PROVIDER':'browser_maps',key:value})
                        with self.assertRaisesRegex(ValueError,'PROVIDER_ABSOLUTE_PATH_REQUIRED'):
                            load_pinned_provider_environment(path,digest)
            from autonomy.provider_environment import pinned_provider_adapter
            missing_cache=root/'absent-cache';missing_input=root/'absent.json'
            path,digest=self.config(root,{'WORKBUDDY_DISCOVERY_PROVIDER':'browser_maps',
                'BROWSER_MAPS_CACHE_DIR':str(missing_cache),'BROWSER_MAPS_JSON_FILE':str(missing_input)})
            with pinned_provider_adapter(path,digest) as adapter:
                self.assertEqual(adapter._cache_dir,missing_cache)
                self.assertEqual(adapter._json_file,str(missing_input))
            self.assertFalse(missing_cache.exists());self.assertFalse(missing_input.exists())
            path,digest=self.config(root,{'WORKBUDDY_DISCOVERY_PROVIDER':'browser_maps','BROWSER_MAPS_JSON_FILE':''})
            self.assertEqual(load_pinned_provider_environment(path,digest)['BROWSER_MAPS_JSON_FILE'],'')

    def test_real_loader_needs_no_code_root_env_and_replaces_inherited_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,digest=self.config(root)
            entry=root/'env_loader.py'
            entry.write_bytes(Path(__file__).with_name('env_loader.py').read_bytes())
            with patch.dict(os.environ,{'ROKT_U1_PROVIDER_CONFIG':str(path),
                 'ROKT_U1_PROVIDER_CONFIG_SHA256':digest,'GOOGLE_MAPS_API_KEY':'unapproved',
                 'DISCOVERY_PROVIDER':'mock'},clear=True):
                runpy.run_path(str(entry))
                self.assertEqual(os.environ['GOOGLE_MAPS_API_KEY'],'fixture-only')
                self.assertNotIn('DISCOVERY_PROVIDER',os.environ)
                self.assertFalse((root/'.env').exists())
            (root/'.development-copy').touch()
            with patch.dict(os.environ,{'ROKT_U1_PROVIDER_CONFIG':str(path),
                 'ROKT_U1_PROVIDER_CONFIG_SHA256':digest},clear=True):
                with patch.dict('sys.modules',{'development_safety':type('Safety',(),{'install':staticmethod(lambda:None)})}):
                    with self.assertRaisesRegex(ValueError,'DEVELOPMENT_EXTERNAL_CREDENTIALS_REJECTED'):
                        runpy.run_path(str(entry))

    def test_invalid_config_does_not_mutate_inherited_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,digest=self.config(root)
            entry=root/'env_loader.py';entry.write_bytes(Path(__file__).with_name('env_loader.py').read_bytes())
            for extra in ({'ROKT_U1_PROVIDER_CONFIG':str(path)},
                          {'ROKT_U1_PROVIDER_CONFIG':str(path),'ROKT_U1_PROVIDER_CONFIG_SHA256':'0'*64}):
                with patch.dict(os.environ,dict(extra,GOOGLE_MAPS_API_KEY='original'),clear=True):
                    with self.assertRaises(ValueError):runpy.run_path(str(entry))
                    self.assertEqual(os.environ['GOOGLE_MAPS_API_KEY'],'original')


if __name__=='__main__':unittest.main()

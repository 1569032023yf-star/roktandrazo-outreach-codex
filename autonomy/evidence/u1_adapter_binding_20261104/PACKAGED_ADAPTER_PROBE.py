"""真实包内适配器探针 / Actual packaged-adapter probe; no network."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,sys.argv[1])
from autonomy.provider_environment import pinned_provider_adapter
import autonomy.provider_environment as module
assert Path(module.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)
    config=root/'provider.json'
    raw=json.dumps({'schema':'rokt.provider-environment.v1','environment':{
      'WORKBUDDY_DISCOVERY_PROVIDER':'browser_maps','BROWSER_MAPS_CACHE_DIR':str(root/'cache')}}).encode()
    config.write_bytes(raw)
    os.environ['BROWSER_MAPS_MODE']='direct'
    os.environ['BROWSER_MAPS_JSON_FILE']=str(root/'unapproved.json')
    with pinned_provider_adapter(config,hashlib.sha256(raw).hexdigest()) as provider:
        assert provider.search_places('fixture','City','ST').status=='no_data_available'
        assert not (root/'cache').exists()
        assert provider.contract.status=='CONTRACT_MISSING'
        try:config.write_bytes(b'changed')
        except OSError:pass
        else:raise AssertionError('CONFIG_NOT_PINNED')
print(json.dumps({'packaged_adapter':True,'inherited_direct_mode_ignored':True,'readonly_cache_construction':True,'config_lifetime_pinned':True,'provider_accepted':False,'allow_dispatch':False}))

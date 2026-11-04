"""Bootstrap argument boundary / Bootstrap参数边界；入口捕获替身，不是真实服务。"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from autonomy.windows import u1_bootstrap as bootstrap


class BootstrapArgumentTests(unittest.TestCase):
    def test_optional_owner_modes_forward_exact_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config=root/'runtime.json';app=root/'app'
            base=dict(schema='rokt.u1-python-runtime.v1',inventory_id='1784775229336',
                      release_root=str(root/'release'),state_root=str(root/'state'),
                      token_file=str(root/'token'),credential_expires_at=12345,
                      snapshot=str(root/'snapshot'),snapshot_sha256='a'*64,
                      allow_dispatch=False,allow_cancel_dispatch=False,smtp_enabled=False)
            for optional in (None,'event_runtime','original_owner_db'):
                data=dict(base)
                if optional:data[optional]=str(root/'owner-reference')
                config.write_text(json.dumps(data),encoding='utf-8')
                captured=[]
                def intercept(name,run_name):captured.append((name,run_name,list(sys.argv),list(sys.path)))
                with patch.object(sys,'argv',list(sys.argv)),patch.object(sys,'path',list(sys.path)),patch.object(bootstrap,'resolve_release',return_value=app),patch.object(bootstrap.runpy,'run_module',side_effect=intercept):
                    bootstrap.main(str(config))
                expected=['autonomy.u1_host_runtime','--release-root',base['release_root'],
                          '--state-root',base['state_root'],'--token-file',base['token_file'],
                          '--credential-expires-at','12345','--snapshot',base['snapshot'],
                          '--snapshot-sha256','a'*64]
                if optional:expected+=['--'+optional.replace('_','-'),data[optional]]
                self.assertEqual(captured[0][:3],('autonomy.u1_host_runtime','__main__',expected))
                self.assertEqual(captured[0][3][0],str(app))

    def test_enabled_gates_and_conflicting_owner_modes_reject_before_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/'runtime.json'
            base=dict(schema='rokt.u1-python-runtime.v1',inventory_id='1784775229336',
                      release_root=tmp,state_root=tmp,token_file=tmp,credential_expires_at=12345,
                      snapshot=tmp,snapshot_sha256='a'*64,allow_dispatch=False,
                      allow_cancel_dispatch=False,smtp_enabled=False)
            cases=[dict(base,**{key:True}) for key in ('allow_dispatch','allow_cancel_dispatch','smtp_enabled')]
            cases.append(dict(base,event_runtime=tmp,original_owner_db=tmp))
            for data in cases:
                config.write_text(json.dumps(data),encoding='utf-8')
                with patch.object(bootstrap,'resolve_release') as release,patch.object(bootstrap.runpy,'run_module') as run:
                    with self.assertRaisesRegex(ValueError,'RUNTIME_CONFIG_REJECTED'):bootstrap.main(str(config))
                    release.assert_not_called();run.assert_not_called()


if __name__=='__main__':unittest.main()

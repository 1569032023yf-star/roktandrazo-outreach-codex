from pathlib import Path
import hashlib,json,subprocess,tempfile,time,unittest

class ProvisionTests(unittest.TestCase):
 def test_generated_configs_and_tamper(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); files={}
   for key in ('python','token_file','snapshot'):
    p=root/(key+'.bin');p.write_bytes(b'isolated fixture '+key.encode());files[key]=str(p)
   plan=dict(schema='rokt.u1-provision-plan.v1',inventory_id='1784775229336',**files,release_root=str(root),credential_expires_at=int(time.time())+3600)
   for key in files:plan['token_sha256' if key=='token_file' else key+'_sha256']=hashlib.sha256(Path(files[key]).read_bytes()).hexdigest()
   path=root/'plan.json';path.write_text(json.dumps(plan));sha=hashlib.sha256(path.read_bytes()).hexdigest()
   source=Path('autonomy/windows/Install-DisabledHost.ps1').read_text()
   block=source[source.index('# Generate exact supervisor'):source.index('if (Get-CimInstance Win32_Service -Filter')]
   script=root/'check.ps1'
   pre="param($RuntimePlan,$ApprovedRuntimePlanSha256)\n$ErrorActionPreference='Stop'\nfunction Assert-NoReparseAncestors($p) {}\n$code='C:\\Program Files\\RoktU1Bridge\\v1'\n$state='C:\\ProgramData\\RoktU1Bridge'\n$m=@{files=@(@{path='service/u1_bootstrap.py';sha256=('a'*64)})}\n"
   script.write_text(pre+block+"\n[Text.Encoding]::UTF8.GetString($generated['config/runtime.json'])\n[Text.Encoding]::UTF8.GetString($generated['config/supervisor.json'])",encoding='utf-8-sig')
   def run(digest):return subprocess.run(['pwsh','-NoProfile','-Command', '& { '+script.read_text(encoding='utf-8-sig')+" } '"+str(path).replace("'","''")+"' '"+digest+"'"],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=15)
   good=run(sha);self.assertEqual(good.returncode,0,good.stderr)
   runtime,supervisor=map(json.loads,good.stdout.strip().splitlines())
   self.assertFalse(runtime['allow_dispatch']);self.assertFalse(runtime['smtp_enabled'])
   encoded=good.stdout.strip().splitlines()[0].encode();self.assertEqual(supervisor['runtime_config_sha256'],hashlib.sha256(encoded).hexdigest())
   Path(files['snapshot']).write_bytes(b'changed')
   self.assertNotEqual(run(sha).returncode,0)
   self.assertNotEqual(run('0'*64).returncode,0)

if __name__=='__main__':unittest.main()


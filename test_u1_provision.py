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
   source=Path('autonomy/windows/Host-PackagePreparation.ps1').read_text()
   block=source[source.index('# Generate exact supervisor'):source.index('# The helper is manifest-hashed')]
   script=root/'check.ps1'
   pre="param($RuntimePlan,$ApprovedRuntimePlanSha256)\n$ErrorActionPreference='Stop'\nfunction Assert-NoReparseAncestors($p) {}\n$code='C:\\Program Files\\RoktU1Bridge\\v1'\n$state='C:\\ProgramData\\RoktU1Bridge'\n$m=@{files=@(@{path='service/u1_bootstrap.py';sha256=('a'*64)})}\n"
   helper=source[source.index('$dependencyPins='):source.index("try {\n$name=")]
   script.write_text(pre+helper+block+"\n[Text.Encoding]::UTF8.GetString($generated['config/runtime.json'])\n[Text.Encoding]::UTF8.GetString($generated['config/supervisor.json'])\n$blocked=$false; try {[IO.File]::WriteAllBytes($plan.snapshot,[byte[]]@(1))} catch [IO.IOException] {$blocked=$true}; if (-not $blocked) {throw 'PIN_WRITE_NOT_BLOCKED'}\nforeach ($pin in $dependencyPins) {$pin.Dispose()}",encoding='utf-8-sig')
   def run(digest):return subprocess.run(['pwsh','-NoProfile','-Command', '& { '+script.read_text(encoding='utf-8-sig')+" } '"+str(path).replace("'","''")+"' '"+digest+"'"],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=15)
   good=run(sha);self.assertEqual(good.returncode,0,good.stderr)
   runtime,supervisor=map(json.loads,good.stdout.strip().splitlines())
   self.assertFalse(runtime['allow_dispatch']);self.assertFalse(runtime['smtp_enabled'])
   encoded=good.stdout.strip().splitlines()[0].encode();self.assertEqual(supervisor['runtime_config_sha256'],hashlib.sha256(encoded).hexdigest())
   Path(files['snapshot']).write_bytes(b'changed')
   self.assertNotEqual(run(sha).returncode,0)
   self.assertNotEqual(run('0'*64).returncode,0)

class OwnershipReceiptTests(unittest.TestCase):
 def test_actual_receipt_writer_and_rollback_pins(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); (root/'config').mkdir(); wrapper=root/'wrapper.exe'; wrapper.write_bytes(b'isolated wrapper')
   from autonomy.host_file_transaction import HostFileTransaction
   audit=root/'audit';audit.mkdir()
   transaction=HostFileTransaction(root,audit/'files.jsonl')
   transaction.prepare({'config/installation.json':b'{"schema":"isolated"}'},manifest_sha256='a'*64)
   transaction.apply()
   rollback=Path('autonomy/windows/Rollback-DisabledHost.ps1').read_text()
   reader=rollback[rollback.index('$ownershipPins='):rollback.index('function Assert-OwnedRegistration')]
   quote=lambda x: "'"+str(x).replace("'","''")+"'"
   code="$ErrorActionPreference='Stop'; function Assert-NoReparseAncestors($p) {}; $code="+quote(root)+";"
   code+=reader+"; $path=Join-Path $code 'config/installation.json'; $bytes=Read-PinnedOwnership $path; $w=Read-PinnedOwnership "+quote(wrapper)+";"
   code+="foreach ($p in @($path,"+quote(wrapper)+")) {$blocked=$false; try {[IO.File]::WriteAllText($p,'changed')} catch [IO.IOException] {$blocked=$true}; if (-not $blocked) {throw 'WRITE_NOT_BLOCKED'}}; foreach ($pin in $ownershipPins) {$pin.Dispose()};"
   run=subprocess.run(['pwsh','-NoProfile','-Command',code],capture_output=True,text=True,timeout=15)
   self.assertEqual(run.returncode,0,run.stderr)
   self.assertEqual(json.loads((root/'config/installation.json').read_text()),{'schema':'isolated'})
   self.assertIn("$receiptPath='C:\\Program Files\\RoktU1Bridge\\v1\\config\\installation.json'",rollback)
   self.assertNotIn("$receiptPath='C:\\ProgramData",rollback)

if __name__=='__main__':unittest.main()


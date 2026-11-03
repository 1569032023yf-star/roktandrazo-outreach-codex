"""验证隔离补丁字节 / Verify companion bytes only in a temporary directory."""
from pathlib import Path
import hashlib,json,subprocess,tempfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def main():
    binding=json.loads((HERE/'COMPANION_BINDING.json').read_text(encoding='utf-8'))
    patch=(HERE/'ORIGINAL_INVENTORY_ADMISSION.patch').read_bytes()
    assert hashlib.sha256(patch).hexdigest()==binding['patch_sha256']
    with tempfile.TemporaryDirectory(prefix='u1-owner-transport-') as tmp:
        dest=Path(tmp)
        for row in binding['files']:
            assert row['path'] in ('bd_db.py','bd_orchestrator.py')
            raw=subprocess.check_output(['git','show',binding['baseline']+':'+row['path']],cwd=ROOT)
            assert hashlib.sha256(raw).hexdigest()==row['before_git_blob_sha256']
            (dest/row['path']).write_bytes(raw)
        args=['git','-c','core.autocrlf=false','-c','core.eol=lf','apply','--unidiff-zero']
        subprocess.run(args+['--check','-'],input=patch,cwd=dest,check=True,capture_output=True)
        subprocess.run(args+['-'],input=patch,cwd=dest,check=True,capture_output=True)
        for row in binding['files']:
            raw=(dest/row['path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest()==row['after_git_blob_sha256']
            assert raw==subprocess.check_output(['git','show',binding['source_commit']+':'+row['path']],cwd=ROOT)
    result=dict(source_commit=binding['source_commit'],baseline=binding['baseline'],patch_sha256=binding['patch_sha256'],files_verified=2,byte_policy='Exact Git blob LF; site bytes not asserted',applied_only_in_temporary_directory=True,production_applied=False,passed=True)
    (HERE/'COMPANION_TRANSPORT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
if __name__=='__main__':main()

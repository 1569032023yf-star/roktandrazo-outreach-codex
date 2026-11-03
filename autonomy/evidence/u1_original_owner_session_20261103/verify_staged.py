"""核验暂存制品字节 / Verify actual staged artifact bytes, not filenames only."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
manifest=json.loads((HERE/'ARTIFACT_MANIFEST.json').read_text(encoding='utf-8'))
paths=[]
for row in manifest['files']:
    path=HERE/row['path']
    path.resolve(strict=True).relative_to(HERE.resolve(strict=True))
    assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
    paths.append(path.relative_to(ROOT).as_posix())
subprocess.run(['git','add','-f','--',*paths],cwd=ROOT,check=True)
for row,name in zip(manifest['files'],paths):
    raw=subprocess.check_output(['git','show',':'+name],cwd=ROOT)
    assert hashlib.sha256(raw).hexdigest()==row['sha256'],name
result=dict(source_commit=manifest['source_commit'],files_verified=len(paths),
            passed=True,verification='Actual staged Git blob SHA256 equals artifact manifest',
            description_zh='实际暂存Git字节与制品清单逐项一致',production_applied=False)
(HERE/'STAGED_ARTIFACT_VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))

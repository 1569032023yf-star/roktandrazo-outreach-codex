"""Offline proposal builder; never contacts production or installs a release.

Read an already approved source snapshot. Rehearse forward/reverse exact byte
patches in a temporary directory; publish diffs and hashes, never source secrets.
"""
from pathlib import Path
import difflib
import hashlib
import json
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BEFORE = {
    'bd_template.py': '00ab0d45e376da0590ea540881c37ea5fce7bce3b7a94e766002e72e8f7e9c49',
    'bd_sender.py': '002d68a1e76d5f96af6fdbabdce54da0af3a93077d8a504ddd106a41fd018280',
    'preflight_gate.py': '2cd286f201430fb9a48c68ead512671f398732e50e768c2fd69031f127f52622',
    'final_send_plan.py': '26de2f017390eda767beddfe8fbd6bc438b78ddb430eeebc4b96c72aa41d327f',
}
NEW = ('v6_outreach.py', 'v6_bestseller_evidence.py', 'send_resumption.py', 'controlled_v6_test.py')
BINARY = ('assets/v6/evidence/tiktok_jigsaw_bestsellers_original.png',)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def build(snapshot):
    dest = ROOT / 'patches/production/phase5a'
    dest.mkdir(parents=True, exist_ok=True)
    patch, files, originals = [], [], {}
    for name, expected in BEFORE.items():
        before = (snapshot / name).read_bytes()
        if sha(before) != expected:
            raise ValueError('SOURCE_FINGERPRINT_MISMATCH:' + name)
        after = (ROOT / name).read_text(encoding='utf-8').encode('utf-8')
        if b'\r\n' in before:
            after = after.replace(b'\n', b'\r\n')
        originals[name] = before
        patch.extend(difflib.unified_diff(before.decode().splitlines(True), after.decode().splitlines(True),
            fromfile='a/' + name, tofile='b/' + name))
        files.append({'file':name, 'action':'patch', 'before_sha256':expected,'after_sha256':sha(after)})
    for name in NEW:
        after = (ROOT / name).read_text(encoding='utf-8').encode('utf-8')
        patch.extend(difflib.unified_diff([],after.decode().splitlines(True),fromfile='/dev/null',tofile='b/'+name))
        files.append({'file':name,'action':'create_if_absent','before_sha256':None,'after_sha256':sha(after)})
    payload = ''.join(patch).encode('utf-8')
    for name in BINARY:
        data = (ROOT / name).read_bytes()
        files.append({'file': name, 'action': 'create_if_absent', 'before_sha256': None,
            'after_sha256': sha(data), 'artifact': name, 'encoding': 'binary_original'})
    patch_path = dest / 'proposed-v6.patch'
    patch_path.write_bytes(payload)
    with tempfile.TemporaryDirectory(prefix='phase5a-rehearsal-') as directory:
        temp = Path(directory)
        for name, data in originals.items():
            (temp / name).write_bytes(data)
        for options in (['--check'], []):
            subprocess.run(['git','-c','core.autocrlf=false','apply',*options,str(patch_path)],cwd=temp,check=True,capture_output=True)
        for name in BINARY:
            target = temp / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        for item in files:
            if sha((temp/item['file']).read_bytes()) != item['after_sha256']:
                raise ValueError('AFTER_SHA_MISMATCH:' + item['file'])
        for options in (['--reverse','--check'], ['--reverse']):
            subprocess.run(['git','-c','core.autocrlf=false','apply',*options,str(patch_path)],cwd=temp,check=True,capture_output=True)
        for name in BINARY:
            (temp / name).unlink()
        for name, data in originals.items():
            if (temp/name).read_bytes() != data:
                raise ValueError('ROLLBACK_BYTES_MISMATCH:' + name)
        if any((temp/name).exists() for name in NEW):
            raise ValueError('ROLLBACK_NEW_FILE_REMAINS')
    result = {
        'description_zh':'仅供审查的 V6 发布提案；未注册、未部署，不可复用 SAFE50 release。',
        'description_en':'Review-only V6 proposal; unregistered and undeployed. Never reuse the SAFE50 release.',
        'release_id':'phase5a-v6-controlled-send-resumption',
        'registered':False,'production_ready':False,
        'baseline_commit':'72bdd70a13dd959264a3137fc546334249b48be1',
        'patch_sha256':sha(payload),'files':files,
        'offline_forward_and_byte_exact_reverse_passed':True,
        'runtime_rollback_verified':False,
        'excluded':['bd_orchestrator.py','daily_session.py','production databases','.env','credentials','automations','phase4b1g'],
        'notes_zh':'当前通道仅接受已注册 SAFE50 单文件发布。本提案需新的多文件发布登记、互斥及失败恢复验证。回滚保留发送审计和预算预留，不恢复历史客户状态。',
        'notes_en':'Current channel supports only its registered SAFE50 single-file release. New multi-file registration, exclusion and failure recovery validation are required. Rollback preserves send audits/reservations and never rewinds customer history.',
    }
    (dest/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    qa_names = ('v6_outreach.py', 'v6_bestseller_evidence.py', 'controlled_v6_test.py') + BINARY
    qa = {'description_zh': '独立内部 QA 登记申请；不是可执行授权。',
        'description_en': 'Independent internal-QA registration request; not executable authority.',
        'release_id': 'phase5a1-v6-four-template-internal-qa', 'registered': False,
        'operation_requested': 'internal_qa_once', 'maximum_messages': 4,
        'customer_smtp_enabled': False, 'customer_fsp_created': False,
        'files': [item for item in files if item['file'] in qa_names],
        'existing_dependency': {'bd_sender.py': BEFORE['bd_sender.py']},
        'notes_zh': '原图是独立哈希工件，不在文本补丁中；必须在同一受控发布中登记和备份。内部未核实排名只显示待核实文字，不嵌图。',
        'notes_en': 'Original image is a separately hashed artifact outside the text patch; register/back up in the same controlled release. Unverified internal ranking previews contain pending text and no image.'}
    (dest/'internal-qa-request.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'files':len(files),'offline_rehearsal':True,'registered':False,'deployed':False}))

if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--approved-snapshot',type=Path,required=True)
    build(parser.parse_args().approved_snapshot)

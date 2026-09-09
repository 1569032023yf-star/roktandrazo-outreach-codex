"""标准库静态审计；不导入项目模块。Standard-library static audit, no project imports."""
import ast
import hashlib
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'audit_evidence'
OUT.mkdir(exist_ok=True)
FROZEN = ['bd_sender.py', 'daily_session.py', 'preflight_gate.py', 'campaign_eligible_v2.py', 'final_send_plan.py']
hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FROZEN}
hashfile = OUT / 'frozen_sha256.json'
if hashfile.exists():
    assert json.loads(hashfile.read_text()) == hashes, 'Frozen file changed'
else:
    hashfile.write_text(json.dumps(hashes, indent=2), encoding='utf-8')
rows = []
for p in sorted(ROOT.rglob('*')):
    if not p.is_file() or p.suffix != '.py' or p.name in ('audit_static.py', 'sitecustomize.py'):
        continue
    rel = p.relative_to(ROOT).as_posix()
    s = p.read_text(encoding='utf-8-sig', errors='replace')
    try:
        tree = ast.parse(s)
    except SyntaxError as e:
        rows.append(dict(path=rel, parse_error=str(e)))
        continue
    hits = {k: [] for k in ['entry', 'sql_write', 'db_connect', 'smtp', 'process', 'production_path']}
    imports = set()
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append([node.name, node.lineno])
        if isinstance(node, ast.Import):
            imports.update(n.name for n in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if re.search(r'\b(?:INSERT\s+(?:OR\s+\w+\s+)?INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|CREATE\s+TABLE|ALTER\s+TABLE|DROP\s+TABLE)\b', node.value, re.I):
                hits['sql_write'].append(node.lineno)
            if 'WorkBuddy' in node.value or 'D:\\CODEX' in node.value:
                hits['production_path'].append(node.lineno)
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            if name in ('sqlite3.connect', 'get_db', 'bd_db.get_db'):
                hits['db_connect'].append(node.lineno)
            if re.search(r'(SMTP|sendmail|send_message|send_email|send_single|send_outreach)', name):
                hits['smtp'].append([node.lineno, name])
            if re.search(r'(subprocess\.|os\.system|Popen|schtasks)', name):
                hits['process'].append([node.lineno, name])
        if isinstance(node, ast.If) and '__name__' in ast.unparse(node.test) and '__main__' in ast.unparse(node.test):
            hits['entry'].append(node.lineno)
    rows.append(dict(path=rel, **hits, imports=sorted(imports), functions=functions))
(OUT/'static_inventory.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding='utf-8')
lines=['# 静态入口与写入候选清单 / Static entrypoint and mutation candidate inventory', '',
       '仅为 AST 候选，不等于可达生产行为；历史副本与测试也包含在内。 / AST candidates only, not proof of production reachability; includes historical copies and tests.', '',
       '| 文件 / File | CLI 行 / Lines | SQL 写入行 / Write lines | DB 连接行 / Connect lines | SMTP/发送调用 / Send calls | 进程调用 / Process calls | 生产路径行 / Production path lines |',
       '|---|---|---|---|---|---|---|']
for r in rows:
    if 'parse_error' in r:
        lines.append(f"| {r['path']} | PARSE ERROR | | | | | |")
    elif any(r[k] for k in ['entry','sql_write','db_connect','smtp','process','production_path']):
        cells=[r['path']] + [str(r[k]) for k in ['entry','sql_write','db_connect','smtp','process','production_path']]
        lines.append('| '+' | '.join(cells)+' |')
(OUT/'STATIC_ENTRYPOINT_WRITER_INDEX.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
db=ROOT/'data'/'bd_leads_dev_snapshot.db'
assert db.is_relative_to(ROOT)
con=sqlite3.connect(db.as_uri()+'?mode=ro&immutable=1', uri=True)
con.execute('PRAGMA query_only=ON')
tables=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
stats={'integrity_check': con.execute('PRAGMA integrity_check').fetchone()[0],
       'tables': {t: {'count':con.execute('SELECT COUNT(*) FROM "'+t+'"').fetchone()[0], 'columns':[r[1] for r in con.execute('PRAGMA table_info("'+t+'")')]} for t in tables}}
queries={
 'lead_status': 'SELECT status,COUNT(*) FROM leads GROUP BY status',
 'lead_sources': 'SELECT email_source_type,COUNT(*) FROM leads GROUP BY email_source_type',
 'missing_website_email': "SELECT SUM(COALESCE(official_website,'')=''), SUM(COALESCE(email,'')=''),SUM(COALESCE(official_website,'')<>'' AND COALESCE(email,'')='') FROM leads",
 'send_status': 'SELECT status,COUNT(*) FROM send_log GROUP BY status',
 'recent_jobs': 'SELECT stage,business_date,status,target,actual,gap,stop_reason,started_at FROM job_runs ORDER BY started_at DESC LIMIT 20',
 'fsp_status': 'SELECT outreach_batch_date,status,COUNT(*) FROM final_send_plan GROUP BY outreach_batch_date,status ORDER BY outreach_batch_date DESC LIMIT 20',
 'discovery_status': 'SELECT provider,validation_status,COUNT(*),SUM(COALESCE(website,\'\')=\'\') FROM lead_discovery_results GROUP BY provider,validation_status',
 'inventory_submissions': "SELECT final_status,failure_reason,COUNT(*) FROM manual_email_submission WHERE submitted_by='inventory_lane' GROUP BY final_status,failure_reason",
 'discovery_requests': 'SELECT provider,status,COUNT(*) FROM provider_request_audit GROUP BY provider,status',
 'review_reasons': 'SELECT review_reason_code,COUNT(*) FROM leads WHERE status=\'manual_review_needed\' GROUP BY review_reason_code',
 'active_state': "SELECT key,value FROM system_config WHERE key IN ('active_discovery_state','daily_run_target','inventory_target','send_pause','manual_pause','scheduler_enabled')",
 'inventory_duplicate_days': "SELECT business_date,COUNT(*) FROM job_runs WHERE stage='inventory' GROUP BY business_date HAVING COUNT(*)>1 ORDER BY business_date DESC LIMIT 10",
 'recent_fsp': "SELECT outreach_batch_date,status,COUNT(*) FROM final_send_plan WHERE outreach_batch_date GLOB '2026-09-*' GROUP BY outreach_batch_date,status",
}
for k,q in queries.items():
    try: stats[k]=con.execute(q).fetchall()
    except sqlite3.Error as e: stats[k]={'error':str(e)}
con.close()
env_path=ROOT/'_audit_quarantine'/'.env.production-disabled'
env_summary={}
allowed={'WORKBUDDY_DISCOVERY_PROVIDER','DISCOVERY_PROVIDER','BROWSER_MAPS_MODE','WORKBUDDY_DISCOVERY_MAX_PAGES','WORKBUDDY_STAGING_POSTPROCESS_MAX','BD_TEST_MODE'}
for line in env_path.read_text(encoding='utf-8-sig').splitlines():
    if '=' not in line or line.lstrip().startswith('#'): continue
    k,v=line.split('=',1)
    k=k.strip()
    env_summary[k]=v.strip() if k in allowed else '<present; value not exported>'
(OUT/'env_key_inventory.json').write_text(json.dumps(env_summary,indent=2),encoding='utf-8')
(OUT/'snapshot_summary.json').write_text(json.dumps(stats, indent=2, ensure_ascii=False),encoding='utf-8')
print(json.dumps({'python_files':len(rows),'parse_errors':[r['path'] for r in rows if 'parse_error' in r], 'snapshot_integrity':stats['integrity_check'], **{k:v for k,v in stats.items() if k!='tables' and k!='integrity_check'}},ensure_ascii=False,indent=2))

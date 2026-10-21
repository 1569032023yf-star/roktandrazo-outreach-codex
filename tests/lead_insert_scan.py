"""Lead-write gate with a byte-pinned local discovery artifact exception.

线索直写门禁；仅豁免已审计字节的独立本地采集产物。
"""
import hashlib
import re

# This standalone collector creates its own state.sqlite3 schema (id/name/maps_url),
# not the customer DB schema. Pin both path and bytes; never ignore runtime trees.
LOCAL_ARTIFACTS = {
    'autonomy/runtime/dual_source_import/collector.py':
        '5ad7a32e501d302fd909d3641521e4554bd3eca1e8b11962fbc7c9396b2e784d',
}
NON_PRODUCTION_DIRS = {
    'tests', 'backup', 'backups', 'data', 'migrations', 'output',
    '_archived_scripts', '_audit_quarantine', '_retired', 'audit_evidence',
    '.workbuddy', 'discovery',
}
INSERT = re.compile(r'INSERT\s+(?:OR\s+IGNORE\s+|OR\s+REPLACE\s+)?INTO\s+leads\b(?!_)', re.I)


def unauthorized_lead_inserts(root):
    unauthorized = []
    for path in root.rglob('*.py'):
        rel = path.relative_to(root)
        if rel.parts[0] in NON_PRODUCTION_DIRS or path.name == 'bd_db.py':
            continue
        raw = path.read_bytes()
        text = raw.decode('utf-8', errors='replace')
        if INSERT.search(text) and 'require_legacy_lead_insert_approval' not in text:
            if hashlib.sha256(raw).hexdigest() != LOCAL_ARTIFACTS.get(rel.as_posix()):
                unauthorized.append(str(rel))
    return sorted(unauthorized)

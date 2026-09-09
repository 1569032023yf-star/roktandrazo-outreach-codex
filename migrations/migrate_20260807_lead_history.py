#!/usr/bin/env python3
"""
Migration: 2026-08-07 — sync lead.status='new' -> 'sent' for leads whose email
already has a real sent record in send_log. Does NOT modify send_log.
Readonly dry-run first, then --apply.
"""
import sqlite3, os, sys, json
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, 'data', 'bd_leads.db')
ASIA_SH = timezone(timedelta(hours=8))
NOW = datetime.now(ASIA_SH).isoformat()

def main():
    apply = '--apply' in sys.argv
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # 找出 status='new' 但 email 在 send_log 有 sent 记录的 lead
    rows = c.execute("""
        SELECT l.id, l.store_name, l.email, l.organization_key, l.status,
               (SELECT MAX(sl.sent_at) FROM send_log sl WHERE LOWER(sl.email)=LOWER(l.email) AND sl.status='sent') AS sent_at
        FROM leads l
        WHERE l.status='new'
          AND l.email IS NOT NULL AND l.email != ''
          AND EXISTS (SELECT 1 FROM send_log sl WHERE LOWER(sl.email)=LOWER(l.email) AND sl.status='sent')
    """).fetchall()
    print(f"找到 {len(rows)} 条 status='new' 但 email 已 sent 的 lead:")
    for r in rows:
        print(f"  [{r['id']}] {r['store_name'][:30]:30s} | {r['email'][:40]} | org={r['organization_key']} | sent_at={r['sent_at']}")

    if not apply:
        print("\n[dry-run] 未修改。使用 --apply 应用。")
        conn.close()
        return

    # 应用：只更新 lead 状态，不动 send_log
    updated = 0
    skipped = 0
    for r in rows:
        # 若该 email 也出现在 suppression/bounce 上下文则按实际情况处理：仍标 sent（历史事实）
        cur = c.execute("UPDATE leads SET status='sent', sent_at=? WHERE id=? AND status='new'", (r['sent_at'] or NOW, r['id']))
        if cur.rowcount:
            updated += 1
        else:
            skipped += 1
    conn.commit()

    # 统计
    c.execute("SELECT status, COUNT(*) FROM leads GROUP BY status ORDER BY COUNT(*) DESC")
    dist = {r[0]: r[1] for r in c.fetchall()}
    c.execute("SELECT COUNT(*) FROM send_log WHERE status='sent'")
    sl_sent = c.fetchone()[0]

    result = {"applied_at": NOW, "updated_leads": updated, "skipped": skipped,
              "lead_status_dist": dist, "send_log_sent_unchanged": sl_sent}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    with open(os.path.join(BASE, 'output', 'migration_20260807_lead_history.json'), 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    conn.close()

if __name__ == '__main__':
    main()

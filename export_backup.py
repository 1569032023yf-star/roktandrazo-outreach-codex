"""Export CSV backups and final report"""
import sqlite3, sys, io, os, csv
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DB_PATH = 'data/bd_leads.db'
BACKUP_DIR = 'backup'
os.makedirs(BACKUP_DIR, exist_ok=True)
ts = datetime.now().strftime('%Y%m%d_%H%M%S')

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def export_csv(query, filename):
    path = f'{BACKUP_DIR}/{filename}_{ts}.csv'
    cur.execute(query)
    rows = cur.fetchall()
    if not rows: return
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(rows[0].keys())
        for r in rows:
            writer.writerow([str(v) if v else '' for v in r])
    return path

# 1. All leads
p1 = export_csv('SELECT * FROM leads ORDER BY id', 'all_leads')
# 2. A-grade sendable
p2 = export_csv('SELECT * FROM leads WHERE confidence_score="A" AND status="new" AND email IS NOT NULL AND email != "" ORDER BY store_name', 'a_grade_sendable')
# 3. B-grade
p3 = export_csv('SELECT * FROM leads WHERE confidence_score="B" AND status="new" ORDER BY store_name', 'b_grade')
# 4. Suppression list
p4 = export_csv('SELECT * FROM suppression_list', 'suppression_list')
# 5. Bounce log
p5 = export_csv('SELECT * FROM bounce_log', 'bounce_log')

# Final totals
cur.execute('SELECT COUNT(*) FROM leads')
total = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM leads WHERE confidence_score="A"')
a_all = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM leads WHERE confidence_score="B"')
b_all = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM leads WHERE confidence_score="C"')
c_all = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM leads WHERE confidence_score="A" AND status="new" AND email IS NOT NULL AND email != ""')
a_ready = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ""')
with_email = cur.fetchone()[0]

print(f'CSV backups saved to {BACKUP_DIR}/')
print(f'  {p1}')
print(f'  {p2}')
print(f'  {p3}')
print(f'  {p4}')
print(f'  {p5}')
print()
print(f'FINAL DATABASE STATE')
print(f'  Total leads: {total}')
print(f'  A-grade (all): {a_all}')
print(f'  B-grade (all): {b_all}')
print(f'  C-grade (all): {c_all}')
print(f'  A-grade new+email: {a_ready}')
print(f'  With email: {with_email}')

conn.close()

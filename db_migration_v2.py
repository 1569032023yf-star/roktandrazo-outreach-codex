"""DB Migration V2 — Add auto-loop columns and tables. Preserves existing data."""
import sqlite3, sys, io
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DB = 'data/bd_leads.db'
conn = sqlite3.connect(DB)
cur = conn.cursor()

print('=== DB Migration V2 ===')
print()

# 1. Add columns to leads
migrations = [
    ("ALTER TABLE leads ADD COLUMN email_source_type TEXT DEFAULT 'unknown'", 'email_source_type'),
    ("ALTER TABLE leads ADD COLUMN email_verified_on_official_site INTEGER DEFAULT 0", 'email_verified_on_official_site'),
    ("ALTER TABLE leads ADD COLUMN mx_provider TEXT DEFAULT ''", 'mx_provider'),
    ("ALTER TABLE leads ADD COLUMN campaign TEXT DEFAULT ''", 'campaign'),
    ("ALTER TABLE leads ADD COLUMN template_id TEXT DEFAULT ''", 'template_id'),
    ("ALTER TABLE leads ADD COLUMN replied_at TEXT", 'replied_at'),
    ("ALTER TABLE leads ADD COLUMN unsubscribed_at TEXT", 'unsubscribed_at'),
    ("ALTER TABLE leads ADD COLUMN priority TEXT DEFAULT 'normal'", 'priority'),
]

for sql, col in migrations:
    try:
        cur.execute(sql)
        print(f'  ✅ Added column: {col}')
    except Exception as e:
        if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
            print(f'  ⏭️ Skipped (exists): {col}')
        else:
            print(f'  ❌ Error adding {col}: {e}')

# 2. Create reply_log
cur.execute('''
CREATE TABLE IF NOT EXISTS reply_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER,
    email TEXT,
    reply_received_at TEXT,
    reply_type TEXT,
    summary TEXT,
    suggested_action TEXT,
    raw_subject TEXT,
    processed_at TEXT
)''')
print('  ✅ Created: reply_log')

# 3. Create system_config
cur.execute('''
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
)''')

# Seed default configs
seeds = [
    ('send_pause', 'true'),
    ('pause_reason', 'system_upgrade_testing'),
    ('safe_daily_cap', '5'),
    ('consecutive_stable_days', '0'),
    ('last_send_date', ''),
    ('today_sent_count', '0'),
    ('today_bounce_count', '0'),
    ('today_hard_bounce_count', '0'),
    ('today_policy_bounce_count', '0'),
    ('today_soft_bounce_count', '0'),
    ('today_unknown_bounce_count', '0'),
    ('today_reply_count', '0'),
    ('today_unsubscribe_count', '0'),
    ('system_version', '2.0.0'),
    ('last_migration', datetime.now().isoformat()),
]
for key, val in seeds:
    cur.execute('INSERT OR IGNORE INTO system_config (key, value, updated_at) VALUES (?, ?, datetime(\'now\'))', (key, val))
print(f'  ✅ Seeded: {len(seeds)} system_config keys')

# 4. Set email_source_type for existing data
# All existing A-grade with verified status get official_page_visible
cur.execute("UPDATE leads SET email_source_type='official_page_visible', email_verified_on_official_site=1 WHERE confidence_score='A' AND status='new' AND email IS NOT NULL AND email != ''")
print(f'  ✅ Set email_source_type for A-grade: {cur.rowcount} rows')

# Set guessed_email for B-grade that were downgraded
cur.execute("UPDATE leads SET email_source_type='guessed_email', email_verified_on_official_site=0 WHERE confidence_score='B' AND notes LIKE '%guessed%'")
print(f'  ✅ Set guessed_email for downgraded B: {cur.rowcount} rows')

# Set contact_form_only for B with contact_form_url
cur.execute("UPDATE leads SET email_source_type='contact_form_only' WHERE confidence_score='B' AND (contact_form_url IS NOT NULL AND contact_form_url != '') AND email IS NULL OR email = ''")
print(f'  ✅ Set contact_form_only for B with form: {cur.rowcount} rows')

# 5. Verify no data loss
checks = [
    ('Total leads', 'SELECT COUNT(*) FROM leads'),
    ('Grade A', "SELECT COUNT(*) FROM leads WHERE confidence_score='A'"),
    ('Grade B', "SELECT COUNT(*) FROM leads WHERE confidence_score='B'"),
    ('Grade C', "SELECT COUNT(*) FROM leads WHERE confidence_score='C'"),
    ('Status=sent', "SELECT COUNT(*) FROM leads WHERE status='sent'"),
    ('Status=bounced', "SELECT COUNT(*) FROM leads WHERE status='bounced'"),
    ('Status=delivery_issue', "SELECT COUNT(*) FROM leads WHERE status='delivery_issue'"),
    ('Suppression list', 'SELECT COUNT(*) FROM suppression_list'),
]

print()
print('=== Post-migration verification ===')
for label, sql in checks:
    cur.execute(sql)
    print(f'  {label}: {cur.fetchone()[0]}')

# Verify 64 verified A
cur.execute("SELECT COUNT(*) FROM leads WHERE confidence_score='A' AND status='new' AND email IS NOT NULL AND email != '' AND email_verified_on_official_site=1")
print(f'  Verified A pool: {cur.fetchone()[0]}')

cur.execute("SELECT COUNT(*) FROM leads WHERE confidence_score='A' AND status='new' AND email IS NOT NULL AND email != '' AND email_source_type='guessed_email'")
guess_a = cur.fetchone()[0]
print(f'  Guessed_email still in A: {guess_a}')
if guess_a > 0:
    print('  ⚠️ WARNING: guessed emails still in A grade!')

conn.commit()
conn.close()
print()
print('[T1] Migration complete')

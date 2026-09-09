# BD Auto Closed-Loop System — Upgrade Plan

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Supervisor Agent                              │
│  (Risk Control — send_pause / daily cap / emergency stop)       │
└──────┬──────────────┬──────────────┬───────────────┬────────────┘
       │              │              │               │
       ▼              ▼              ▼               ▼
┌──────────┐  ┌──────────┐  ┌────────────┐  ┌──────────────┐
│  Lead    │  │  Sender  │  │   Reply    │  │   Bounce     │
│ Collector│──▶│  Agent   │──▶│  Monitor   │──▶│   Auditor   │
│  Agent   │  │          │  │   Agent    │  │   Agent      │
└──────────┘  └──────────┘  └────────────┘  └──────────────┘
                   │              │                │
                   ▼              ▼                ▼
              ┌─────────────────────────────────────────┐
              │           Daily Report Agent             │
              │  (Generate daily summary at end of day)  │
              └─────────────────────────────────────────┘
```

## Schedule / Automation Design

Using WorkBuddy automation (`automation_update` tool) with the following jobs:

### Job 1: Lead Collector — Daily 08:00 UTC
- Trigger: every day at 08:00 UTC (16:00 CST / 4:00 AM ET)
- Action: run `import_phase4.py`-style collection script
- Checks a pool of un-searched cities, collects 10-20 new verified leads

### Job 2: Sender — Daily 10:00 ET / 14:00 UTC
- Trigger: every day at 14:00 UTC (22:00 CST / 10:00 AM ET)
- Action:
  1. Load verified A leads (email_verified_on_official_site=true)
  2. Exclude: Exchange MX, suppression, sent, bounced, delivery_issue
  3. Send up to safe_daily_cap (dynamic, starts at 5)
  4. 3-5 min intervals
  5. Record sent_at, campaign, template_id

### Job 3: Reply+Bounce Monitor — 3x daily
- Trigger: at 15:00, 19:00, 23:00 UTC
- Action:
  1. Scan INBOX + Junk for new messages since last scan
  2. Classify: reply / bounce / unsubscribe / auto_reply
  3. Update leads table
  4. Update suppression_list
  5. Log to reply_log / bounce_log

### Job 4: Daily Report — 23:30 UTC
- Trigger: at 23:30 UTC daily
- Action:
  1. Aggregate today's stats
  2. Generate structured daily report
  3. Output to user

---

## File Changes Required

### 1. Existing files to modify

| File | Changes |
|------|---------|
| `bd_db.py` | Add `email_source_type`, `email_verified_on_official_site`, `mx_provider` columns |
| | Add `reply_log` table creation |
| | Add `verified_a_pool()` query method |
| | Add `safe_daily_cap` read/write |
| `scorer_v2.py` | Remove guessed_email allowance from scoring |
| | Add `email_source_type` validation to A-grade conditions |
| | `email_verified_on_official_site` must be true for grade A |
| `bd_sender.py` | Add Exchange MX pre-check before sending |
| | Add campaign tracking parameter |
| | Add `batch_send_v2()` with interval + cap + exclusion |
| `bd_template.py` | Keep as-is (template is good) |
| `.env` | Add `BD_SAFE_DAILY_CAP=5`, `BD_SEND_PAUSE=true` |

### 2. New files to create

| File | Purpose |
|------|---------|
| `agent_lead_collector.py` | Lead Collector Agent — automated verified email collection |
| `agent_sender.py` | Sender Agent — daily scheduled verified A sending |
| `agent_reply_monitor.py` | Reply+Bounce Monitor Agent — IMAP scan + classification |
| `agent_bounce_auditor.py` | Bounce Auditor Agent — parse + classify bounces |
| `agent_supervisor.py` | Supervisor Agent — risk control + send_pause logic |
| `agent_daily_report.py` | Daily Report Agent — generate end-of-day summary |
| `pipeline_orchestrator.py` | Master orchestrator — coordinate all agents |
| `db_migration_v2.py` | One-time DB schema migration script |

---

## Database Migration Plan

### Migration: `db_migration_v2.py`

```sql
-- leads table additions
ALTER TABLE leads ADD COLUMN email_source_type TEXT DEFAULT 'unknown';
ALTER TABLE leads ADD COLUMN email_verified_on_official_site INTEGER DEFAULT 0;
ALTER TABLE leads ADD COLUMN mx_provider TEXT DEFAULT '';
ALTER TABLE leads ADD COLUMN campaign TEXT DEFAULT '';
ALTER TABLE leads ADD COLUMN template_id TEXT DEFAULT '';
ALTER TABLE leads ADD COLUMN replied_at TEXT;
ALTER TABLE leads ADD COLUMN unsubscribed_at TEXT;
ALTER TABLE leads ADD COLUMN priority TEXT DEFAULT 'normal';

-- Create reply_log
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
);

-- Create system_config (for dynamic caps, pause state)
CREATE TABLE IF NOT EXISTS system_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
);

-- Seed default configs
INSERT OR IGNORE INTO system_config VALUES ('send_pause', 'true', datetime('now'));
INSERT OR IGNORE INTO system_config VALUES ('pause_reason', 'initial_setup', datetime('now'));
INSERT OR IGNORE INTO system_config VALUES ('safe_daily_cap', '5', datetime('now'));
INSERT OR IGNORE INTO system_config VALUES ('consecutive_stable_days', '0', datetime('now'));
INSERT OR IGNORE INTO system_config VALUES ('last_send_date', '', datetime('now'));
INSERT OR IGNORE INTO system_config VALUES ('today_sent_count', '0', datetime('now'));
INSERT OR IGNORE INTO system_config VALUES ('today_bounce_count', '0', datetime('now'));
```

---

## Agent Module Design

### 1. Lead Collector Agent (`agent_lead_collector.py`)

```
Input:  pool of un-searched cities (from city_selector.py or manual list)
Process:
  For each city:
    - Build search queries for target store types
    - For each candidate store:
      1. Verify official_website exists
      2. Find contact_page, email on page (NOT guessed)
      3. Save email_source_page (the exact URL where email was found)
      4. Save evidence_url
      5. Check MX for domain
      6. Check if email appears on website (visible text / mailto)
      7. Score: A if email_verified_on_official_site, B if contact_form_only, C if no_MX
    - Deduplicate against existing
    - Insert into leads table
Output: N new leads inserted, summary report
```

**Hard rules enforced in code:**
- `info@domain.com` is NEVER generated — email must be parsed from page
- If email cannot be found on page → grade B (contact_form_only) or C (no info)
- `evidence_url` must point to the page where email was extracted
- `email_source_type` is set based on extraction method

### 2. Sender Agent (`agent_sender.py`)

```
Pre-send checks:
  1. Supervisor says send_pause == false
  2. verified A pool has candidates
  3. today_sent_count < safe_daily_cap

Process:
  - Query: SELECT * FROM leads
    WHERE email_verified_on_official_site = 1
      AND grade = 'A'
      AND status = 'new'
      AND mx_provider NOT LIKE '%outlook%'
      AND mx_provider NOT LIKE '%protection.outlook%'
      AND email NOT IN (SELECT email FROM suppression_list)
      AND email NOT IN (SELECT email FROM send_log WHERE status = 'sent')
    LIMIT cap
  - For each lead:
    - Check MX one more time (live check)
    - Generate email using bd_template
    - Send via SMTP
    - Update status = 'sent', sent_at, campaign, template_id
    - Log to send_log
    - Wait 3-5 min interval
  - Update system_config.today_sent_count
  - Return results

Exchange MX exclusion:
  After MX lookup, if mx_provider contains:
    - outlook.com, protection.outlook.com, microsoft.com
  → Skip this lead, do NOT attempt to send
  → Mark as status = 'new', notes = 'exchange_mx_skip'
```

### 3. Reply Monitor Agent (`agent_reply_monitor.py`)

```
IMAP Scan:
  1. Connect to imap.exmail.qq.com
  2. Check INBOX, Junk for messages since last scan timestamp
  3. For each new message:
    - Extract From, Subject, body preview
    - Match to sent emails by looking up send_log
    - Classify using keyword rules
    
Classification (priority ordered):
  1. Bounce: check From contains PostMaster / Mailer-Daemon
     → Forward to Bounce Auditor Agent
  2. Unsubscribe: check Subject/Body for unsubscribe keywords
     → status=unsubscribed, add to suppression_list
  3. Hot reply: check for pricing/catalog/order/sample/Zoom
     → status=hot_reply, priority=hot, log to reply_log
  4. Warm reply: check for maybe/later/details
     → status=warm_reply, priority=warm, log to reply_log
  5. Negative: check for not interested / no thanks
     → status=not_interested, add to suppression_list
  6. Auto-reply: check for out of office / vacation
     → notes only, no status change
```

### 4. Bounce Auditor Agent (`agent_bounce_auditor.py`)

```
Input: bounce notification from Reply Monitor
Process:
  1. Parse MIME for delivery-status parts
  2. Extract:
     - Final-Recipient (the original email)
     - Status (SMTP code like 5.1.1)
     - Diagnostic-Code
     - Remote-MTA
     - Action (failed/delayed)
  3. Classify bounce type:
     - 5.1.0/5.1.1 → hard
     - DNS/MX error → domain
     - 5.4.1/5.7.1 → policy
     - 4.x.x → soft
     - unknown → bounce_review
  4. Execute action:
     - Hard/Domain: status=bounced, add to suppression_list
     - Policy: status=delivery_issue, do NOT suppress
     - Soft: status=soft_bounce, do NOT suppress
     - Unknown: status=bounce_review
  5. Log to bounce_log
```

### 5. Supervisor Agent (`agent_supervisor.py`)

```
Pre-send check (called by Sender Agent before each batch):
  1. Read system_config:
     - send_pause
     - pause_reason
     - safe_daily_cap
     - today_sent_count
     - consecutive_stable_days
  2. If send_pause == true → BLOCK, report reason
  3. If today_sent_count >= safe_daily_cap → BLOCK, daily cap reached
  4. Check last 24h stats:
     - hard_bounce_rate = hard_bounce_count / sent_count
     - If hard_bounce_rate > 10% → BLOCK, pause
     - If total_bounce_rate > 20% → BLOCK, pause
  
Post-send check (called after each send):
  5. Update today_sent_count
  6. If any bounce detected, update today_bounce_count

Emergency pause triggers:
  - 2+ hard bounces in same batch
  - Unsubscribe without suppression write
  - Template variable unreplaced
  - Duplicate send detected
  - SPF/DKIM/DMARC check fails
```

### 6. Daily Report Agent (`agent_daily_report.py`)

```
Query:
  - today_sent_count
  - today_bounce_count (by type: hard/policy/soft/unknown)
  - today_reply_count (by type: hot/warm/negative)
  - today_unsubscribe_count
  - suppression_list additions today
  - verified A pool remaining

Output structured report to user.
```

---

## Dry-Run Test Plan

Before enabling automation, run these tests:

| Test | What to verify | Pass criteria |
|------|---------------|---------------|
| T1: DB Migration | Run `db_migration_v2.py` | All columns created, existing data preserved |
| T2: Collector dry-run | `agent_lead_collector.py` with 1 city | No guessed emails generated, email_source_type set correctly |
| T3: Sender dry-run | `agent_sender.py --dry-run` | Correct leads selected, Exchange excluded, template rendered |
| T4: Monitor scan | `agent_reply_monitor.py --scan` | IMAP connect, classify existing messages correctly |
| T5: Bounce parse | `agent_bounce_auditor.py --sample` | Parse a known bounce, extract all fields |
| T6: Supervisor logic | `agent_supervisor.py --check` | send_pause=true blocks, cap logic works |
| T7: Full pipeline | Run all agents sequentially | End-to-end passes without data corruption |
| T8: Automation config | Create WorkBuddy automations | Jobs created with correct schedules |

---

## Automation Setup (using `automation_update`)

After agent modules are tested, create 4 automations:

1. **bd-sender-daily** — Sender Agent, 10:00 ET daily
2. **bd-monitor** — Reply+Bounce Monitor, 3x daily
3. **bd-collector** — Lead Collector, daily
4. **bd-report** — Daily Report, end of day

Each automation calls its agent via Python CLI.
Prefer `cwds` pointing to the project directory.

---

## Migration Steps Order

```
Step 1: Run DB migration (db_migration_v2.py)
Step 2: Test each agent module individually (T1-T6)
Step 3: Run full pipeline test (T7)
Step 4: Create automations (T8)
Step 5: Enable Day 1 auto-send (5 leads)
Step 6: Monitor Day 1 results via Daily Report
Step 7: If Day 1 passes → Day 2 (10 leads)
Step 8: Escalate cap per stability rules
```

---

## Current Blockers

| Blocker | Status | Action needed |
|---------|--------|---------------|
| send_pause | true | Hold until user approves automation |
| verified A pool | 64 remaining | Used by Sender Agent |
| Exchange MX exclusion | Not yet coded | Add to agent_sender.py |
| Daily cap system | Not yet built | system_config table |
| Automation schedule | Not yet created | After user approval |

## Output Files Summary

| File | Status | 
|------|--------|
| `db_migration_v2.py` | To be created |
| `agent_lead_collector.py` | To be created |
| `agent_sender.py` | To be created |
| `agent_reply_monitor.py` | To be created |
| `agent_bounce_auditor.py` | To be created |
| `agent_supervisor.py` | To be created |
| `agent_daily_report.py` | To be created |
| `pipeline_orchestrator.py` | To be created |

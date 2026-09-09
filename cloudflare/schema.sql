CREATE TABLE IF NOT EXISTS tracking_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  token_hash TEXT NOT NULL UNIQUE,
  tracking_message_id TEXT DEFAULT '',
  plan_entry_id TEXT DEFAULT '',
  lead_id INTEGER DEFAULT 0,
  organization_key TEXT DEFAULT '',
  send_log_id INTEGER DEFAULT 0,
  smtp_message_id TEXT DEFAULT '',
  status TEXT DEFAULT 'prepared',
  created_at TEXT DEFAULT '',
  activated_at TEXT DEFAULT '',
  disabled_at TEXT DEFAULT '',
  first_open_signal_at TEXT DEFAULT '',
  last_open_signal_at TEXT DEFAULT '',
  open_signal_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_token_hash ON tracking_messages(token_hash);
CREATE INDEX IF NOT EXISTS idx_tracking_status ON tracking_messages(status);

CREATE TABLE IF NOT EXISTS tracking_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tracking_message_id INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  event_at TEXT NOT NULL,
  source_classification TEXT DEFAULT 'direct_or_unknown',
  user_agent_family TEXT DEFAULT '',
  ip_hash TEXT DEFAULT '',
  dedupe_key TEXT UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_events_msg_id ON tracking_events(tracking_message_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON tracking_events(event_type);

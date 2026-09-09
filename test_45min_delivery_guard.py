"""BD Delivery Guard 45-minute unattended test monitor."""
import json, hashlib, time, os, sqlite3, urllib.request
from datetime import datetime, timezone, timedelta

ASIA_SH = timezone(timedelta(hours=8))
BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "data", "bd_leads.db")
BASELINE_PATH = os.path.join(BASE, "output", "45min_test_baseline.json")
RESULT_PATH = os.path.join(BASE, "output", "45min_test_result.json")

def now_iso():
    return datetime.now(ASIA_SH).isoformat()

def db_sha256():
    with open(DB_PATH, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

# ── Record baseline ──
baseline = {
    "test_start_at": now_iso(),
    "test_start_epoch": time.time(),
    "db_sha256": db_sha256(),
    "db_size": os.path.getsize(DB_PATH),
}

db = sqlite3.connect(DB_PATH)
baseline["send_log_count"] = db.execute("SELECT COUNT(*) FROM send_log").fetchone()[0]
baseline["planned_count"] = db.execute("SELECT COUNT(*) FROM final_send_plan WHERE status='planned'").fetchone()[0]
db.close()

# Worker HTTP
try:
    r = urllib.request.urlopen("https://roktandrazo-email-tracker.1569032023yf.workers.dev/health", timeout=10)
    baseline["worker_http"] = r.status
except Exception as e:
    baseline["worker_http"] = f"ERROR:{e}"

# Guard status
try:
    with open(os.path.join(BASE, "output", "bd_delivery_guard_status.json")) as f:
        baseline["guard_status"] = json.load(f)
except:
    baseline["guard_status"] = {"error": "not_found"}

# Poller status
try:
    with open(os.path.join(BASE, "output", "bd_ops_poller_status.json")) as f:
        baseline["poller_status"] = json.load(f)
except:
    baseline["poller_status"] = {"error": "not_found"}

# Save baseline
os.makedirs(os.path.dirname(BASELINE_PATH), exist_ok=True)
with open(BASELINE_PATH, "w") as f:
    json.dump(baseline, f, indent=2, default=str)

print("BASELINE:", json.dumps({
    "test_start_at": baseline["test_start_at"],
    "db_sha256": baseline["db_sha256"][:16],
    "send_log_count": baseline["send_log_count"],
    "planned_count": baseline["planned_count"],
    "worker_http": baseline["worker_http"],
    "guard_mode": baseline["guard_status"].get("current_mode", "?")
}))

# ── Monitor loop (45 min = 90 x 30s) ──
print(f"Starting 45-min monitor at {now_iso()}")
print("DO NOT move mouse or press keys during test.")
print("Heartbeat every 30s, checkpoints every 5 min...")

results = {
    "started_at": now_iso(),
    "heartbeats": [],
    "checkpoints": [],
    "modern_standby_events": 0,
    "guard_interruptions": 0,
    "poller_interruptions": 0,
}

INTERVAL = 30
CHECKPOINT_INTERVAL = 10  # every 10 intervals = 5 min
TOTAL_INTERVALS = 90  # 45 min

last_guard_hb = baseline["guard_status"].get("last_heartbeat_at", "")
for i in range(TOTAL_INTERVALS):
    time.sleep(INTERVAL)
    
    # Heartbeat
    now = now_iso()
    guard_hb = ""
    poller_hb = ""
    
    try:
        with open(os.path.join(BASE, "output", "bd_delivery_guard_status.json")) as f:
            gs = json.load(f)
            guard_hb = gs.get("last_heartbeat_at", "")
            if guard_hb == last_guard_hb and i > 2:
                results["guard_interruptions"] += 1
            last_guard_hb = guard_hb
            if i % CHECKPOINT_INTERVAL == 0:
                results["heartbeats"].append({"i": i, "time": now, "guard_mode": gs.get("current_mode"), "guard_hb": guard_hb[:19]})
    except:
        results["guard_interruptions"] += 1
    
    try:
        with open(os.path.join(BASE, "output", "bd_ops_poller_status.json")) as f:
            ps = json.load(f)
            poller_hb = ps.get("last_heartbeat_at", "")
    except:
        results["poller_interruptions"] += 1
    
    if i % CHECKPOINT_INTERVAL == 0:
        results["checkpoints"].append({
            "i": i, "time": now, "guard_hb": guard_hb[:19] if guard_hb else "MISSING",
            "poller_hb": poller_hb[:19] if poller_hb else "MISSING"
        })
        print(f"[{i}/{TOTAL_INTERVALS}] Guard: {guard_hb[:19] if guard_hb else '✗'} | Poller: {poller_hb[:19] if poller_hb else '✗'}")

# ── Final checks ──
results["ended_at"] = now_iso()
results["final_db_sha256"] = db_sha256()
results["db_unchanged"] = results["final_db_sha256"] == baseline["db_sha256"]

# Check for new Modern Standby events in last 45 min
# (Cannot do from non-admin Python; will be checked post-hoc)

# Final guard status
try:
    with open(os.path.join(BASE, "output", "bd_delivery_guard_status.json")) as f:
        results["final_guard_status"] = json.load(f)
except:
    results["final_guard_status"] = {"error": "not_found"}

# Final worker HTTP
try:
    r = urllib.request.urlopen("https://roktandrazo-email-tracker.1569032023yf.workers.dev/health", timeout=10)
    results["final_worker_http"] = r.status
except Exception as e:
    results["final_worker_http"] = f"ERROR:{e}"

# Save results
with open(RESULT_PATH, "w") as f:
    json.dump(results, f, indent=2, default=str)

print(f"\n45-MIN TEST COMPLETE at {now_iso()}")
print(f"DB unchanged: {results['db_unchanged']}")
print(f"Guard interruptions: {results['guard_interruptions']}")
print(f"Poller interruptions: {results['poller_interruptions']}")
print(f"Final Worker HTTP: {results['final_worker_http']}")
print(f"Results saved to: {RESULT_PATH}")

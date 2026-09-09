"""
BD Delivery Guard — Unattended Reliability Test (v2)
======================================================
Robust harness: checkpoint every 60s, try/finally, crash-recoverable.
Separates guard_result from test_harness_result.
NEVER calls SMTP.
"""
import json, hashlib, os, sys, time, sqlite3, urllib.request, traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

ASIA_SH = timezone(timedelta(hours=8))
BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "data" / "bd_leads.db"
OUT_DIR = BASE / "output"
BASELINE_PATH = OUT_DIR / "unattended_test_baseline.json"
RESULT_PATH = OUT_DIR / "unattended_test_result.json"
GUARD_STATUS_PATH = OUT_DIR / "bd_delivery_guard_status.json"
POLLER_STATUS_PATH = OUT_DIR / "bd_ops_poller_status.json"
CHECKPOINT_PATH = OUT_DIR / "unattended_test_checkpoint.json"

INTERVAL = 60  # checkpoint every 60s
DURATION_MINUTES = 45
TOTAL_CHECKPOINTS = DURATION_MINUTES  # 45 checkpoints
HB_GAP_THRESHOLD = 120  # seconds

OUT_DIR.mkdir(parents=True, exist_ok=True)


def now_iso():
    return datetime.now(ASIA_SH).isoformat()


def db_sha256():
    with open(DB_PATH, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def read_json(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            pass
    return None


def write_checkpoint(data):
    """Atomic checkpoint write — survives crashes."""
    tmp = CHECKPOINT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CHECKPOINT_PATH)


# ── Execute test ──
def run_test():
    test_harness_result = {
        "harness": "v2",
        "started_at": now_iso(),
        "ended_at": None,
        "crashed": False,
        "checkpoints_written": 0,
        "error": None,
    }
    guard_result = {
        "modern_standby_events_during_test": None,
        "hb_interruptions": 0,
        "max_hb_gap_seconds": 0,
        "ops_center_http": None,
        "poller_all_jobs_ok": None,
        "dry_run_executed": False,
    }
    checkpoints = []

    try:
        # ── Baseline ──
        baseline = {
            "test_start_at": now_iso(),
            "db_sha256": db_sha256(),
            "db_size": os.path.getsize(DB_PATH),
        }
        db = sqlite3.connect(str(DB_PATH))
        baseline["send_log_count"] = db.execute("SELECT COUNT(*) FROM send_log").fetchone()[0]
        baseline["planned_count"] = db.execute(
            "SELECT COUNT(*) FROM final_send_plan WHERE status='planned'").fetchone()[0]
        db.close()

        # Worker
        try:
            r = urllib.request.urlopen(
                "https://roktandrazo-email-tracker.1569032023yf.workers.dev/health", timeout=10)
            baseline["worker_http"] = r.status
        except Exception as e:
            baseline["worker_http"] = f"ERROR:{type(e).__name__}"

        gs = read_json(GUARD_STATUS_PATH)
        baseline["guard_heartbeat"] = gs.get("last_heartbeat_at") if gs else None

        ps = read_json(POLLER_STATUS_PATH)
        baseline["poller_heartbeat"] = ps.get("last_heartbeat_at") if ps else None

        BASELINE_PATH.write_text(json.dumps(baseline, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[BASELINE] {baseline['test_start_at']} | DB={baseline['db_sha256'][:12]} | send_log={baseline['send_log_count']} | planned={baseline['planned_count']}")

        # ── Checkpoints ──
        last_guard_hb = baseline.get("guard_heartbeat", "")
        last_poller_hb = baseline.get("poller_heartbeat", "")
        print(f"Starting {DURATION_MINUTES}min unattended test ({TOTAL_CHECKPOINTS} checkpoints at {INTERVAL}s intervals)")

        for i in range(1, TOTAL_CHECKPOINTS + 1):
            time.sleep(INTERVAL)

            t = now_iso()
            cp = {"i": i, "time": t}
            hb_gap = 0

            # Guard check
            gs = read_json(GUARD_STATUS_PATH)
            if gs:
                gh = gs.get("last_heartbeat_at", "")
                if gh and last_guard_hb:
                    try:
                        prev = datetime.fromisoformat(last_guard_hb)
                        curr = datetime.fromisoformat(gh)
                        gap = (curr - prev).total_seconds()
                        if gap > HB_GAP_THRESHOLD:
                            guard_result["hb_interruptions"] += 1
                        if gap > guard_result["max_hb_gap_seconds"]:
                            guard_result["max_hb_gap_seconds"] = int(gap)
                        hb_gap = int(gap)
                    except (ValueError, TypeError):
                        pass
                last_guard_hb = gh
                cp["guard_mode"] = gs.get("current_mode")
                cp["guard_system_required"] = gs.get("system_required")
                cp["guard_hb"] = gh[:19] if gh else "MISSING"

            # Poller check
            ps = read_json(POLLER_STATUS_PATH)
            if ps:
                ph = ps.get("last_heartbeat_at", "")
                last_poller_hb = ph
                jobs = ps.get("jobs", {})
                cp["poller_ok"] = all(j.get("consecutive_failures", 0) == 0 for j in jobs.values())
                cp["poller_hb"] = ph[:19] if ph else "MISSING"

            checkpoints.append(cp)
            write_checkpoint({
                "last_checkpoint": i,
                "total": TOTAL_CHECKPOINTS,
                "time": t,
                "guard_hb_gap_s": hb_gap,
                "data": cp,
            })

            if i % 5 == 0 or i == 1:
                print(f"[{i}/{TOTAL_CHECKPOINTS}] {t[:19]} | guard={cp.get('guard_mode','?')} hb_gap={hb_gap}s | poller_ok={cp.get('poller_ok','?')}")

        test_harness_result["checkpoints_written"] = len(checkpoints)

        # ── Dry-run ──
        print("Running safe dry-run...")
        import subprocess
        dr = subprocess.run(
            [sys.executable, str(BASE / "bd_orchestrator.py"), "--stage", "outreach", "--dry-run"],
            cwd=str(BASE), capture_output=True, text=True, timeout=30)
        guard_result["dry_run_executed"] = (dr.returncode == 0)
        guard_result["dry_run_output"] = (dr.stdout + dr.stderr)[:500]
        print(f"Dry-run: {'OK' if guard_result['dry_run_executed'] else 'FAILED'}")

        # ── Post-test analysis ──
        final_db = db_sha256()
        guard_result["db_unchanged"] = (final_db == baseline["db_sha256"])
        guard_result["final_db_sha256"] = final_db

        # Ops Center
        try:
            r = urllib.request.urlopen("http://127.0.0.1:8765/api/dashboard", timeout=5)
            guard_result["ops_center_http"] = r.status
        except Exception as e:
            guard_result["ops_center_http"] = f"ERROR:{type(e).__name__}"

        # Poller final
        ps_final = read_json(POLLER_STATUS_PATH)
        if ps_final:
            jobs = ps_final.get("jobs", {})
            guard_result["poller_all_jobs_ok"] = all(
                j.get("consecutive_failures", 0) == 0 for j in jobs.values())

    except Exception as e:
        test_harness_result["crashed"] = True
        test_harness_result["error"] = f"{type(e).__name__}: {e}"
        traceback.print_exc()

    finally:
        # ── ALWAYS write result, even on crash ──
        test_harness_result["ended_at"] = now_iso()

        # Reconstruct from external sources if harness crashed
        if test_harness_result["crashed"]:
            print("[RECOVERY] Harness crashed, reconstructing from external sources...")
            # Read current guard status
            gs = read_json(GUARD_STATUS_PATH)
            if gs:
                guard_result["guard_heartbeat_at_end"] = gs.get("last_heartbeat_at")
                guard_result["guard_mode_at_end"] = gs.get("current_mode")
            # Re-read DB
            guard_result["final_db_sha256"] = db_sha256()
            guard_result["db_unchanged"] = (guard_result["final_db_sha256"] ==
                                             json.loads(BASELINE_PATH.read_text(encoding="utf-8")).get("db_sha256", ""))

        # Modern Standby events (requires PowerShell — may fail in sandbox)
        guard_result["modern_standby_events_during_test"] = "check_via_event_log_manually"

        # Final DB counts
        try:
            db = sqlite3.connect(str(DB_PATH))
            guard_result["final_send_log_count"] = db.execute("SELECT COUNT(*) FROM send_log").fetchone()[0]
            guard_result["final_planned_count"] = db.execute(
                "SELECT COUNT(*) FROM final_send_plan WHERE status='planned'").fetchone()[0]
            db.close()
        except Exception:
            pass

        result = {
            "test_started_at": baseline.get("test_start_at") if 'baseline' in dir() else now_iso(),
            "test_ended_at": test_harness_result["ended_at"],
            "guard_result": guard_result,
            "test_harness_result": test_harness_result,
            "checkpoints_count": len(checkpoints),
            "baseline": baseline if 'baseline' in dir() else {},
        }
        RESULT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

        print("\n" + "=" * 60)
        print(f"TEST ENDED at {test_harness_result['ended_at']}")
        print(f"Harness: {'CRASHED' if test_harness_result['crashed'] else 'OK'} ({test_harness_result['checkpoints_written']} checkpoints)")
        print(f"Guard: interruptions={guard_result.get('hb_interruptions',0)} max_gap={guard_result.get('max_hb_gap_seconds',0)}s")
        print(f"DB unchanged: {guard_result.get('db_unchanged', False)}")
        print(f"Ops Center: {guard_result.get('ops_center_http', 'N/A')}")
        print(f"Poller OK: {guard_result.get('poller_all_jobs_ok', 'N/A')}")
        print(f"Dry-run: {guard_result.get('dry_run_executed', False)}")
        print(f"Result saved: {RESULT_PATH}")
        print("=" * 60)


if __name__ == "__main__":
    run_test()

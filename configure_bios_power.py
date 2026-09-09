"""HP BIOS Auto-Configuration via WMI — Export + Write + Verify."""
import json, os, sys
from datetime import datetime, timezone, timedelta

ASIA_SH = timezone(timedelta(hours=8))
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "power_diagnostics")
os.makedirs(OUT_DIR, exist_ok=True)

def now_iso():
    return datetime.now(ASIA_SH).isoformat()

def read_bios_setting(name):
    """Read a BIOS setting via HP WMI. Returns (value, is_readonly) or None."""
    import subprocess
    ps = f'$s = Get-WmiObject -Namespace root/hp/instrumentedbios -Class HP_BIOSSetting -Filter "Name=\'{name}\'" -ErrorAction SilentlyContinue; if($s) {{Write-Output "$($s.Value)|$($s.IsReadOnly)"}} else {{Write-Output "NOT_FOUND"}}'
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=15)
    out = r.stdout.strip()
    if out and "NOT_FOUND" not in out and "|" in out:
        parts = out.split("|", 1)
        return parts[0], parts[1] == "0"
    return None, None

def write_bios_setting(name, value):
    """Write a BIOS setting via HP WMI SetBIOSSetting. Returns success bool."""
    import subprocess
    # Use empty password (no BIOS password assumed)
    ps = (
        f'$iface = Get-WmiObject -Namespace root/hp/instrumentedbios -Class HP_BIOSSettingInterface -ErrorAction SilentlyContinue; '
        f'if($iface) {{ try {{ $r = $iface.SetBIOSSetting(\'{name}\', \'{value}\', \'\'); '
        f'Write-Output "OK:$r" }} catch {{ Write-Output "ERROR:$($_.Exception.Message)" }} }} '
        f'else {{ Write-Output "NO_INTERFACE" }}'
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=30)
    out = r.stdout.strip()
    return out, "OK:" in out

# ── 1. Export current values ──
settings_to_set = {
    "BIOS Power-On Hour": "14",
    "BIOS Power-On Minute": "40",
    "Sunday": "Enable",
    "Monday": "Enable",
    "Tuesday": "Enable",
    "Wednesday": "Enable",
    "Thursday": "Enable",
    "Friday": "Enable",
    "Saturday": "Enable",
    "After Power Loss": "Power On",
}

snapshot_before = {}
print(f"=== BIOS SNAPSHOT (before) at {now_iso()} ===")
for name in settings_to_set:
    val, ro = read_bios_setting(name)
    snapshot_before[name] = {"value": val, "is_readonly": ro}
    print(f"  {name} = {val} (readonly={ro})")

# Save snapshot
snapshot_before["_timestamp"] = now_iso()
with open(os.path.join(OUT_DIR, "bios_snapshot_before.json"), "w") as f:
    json.dump(snapshot_before, f, indent=2)

# ── 2. Write settings ──
print(f"\n=== WRITING BIOS SETTINGS at {now_iso()} ===")
results = {}
any_failed = False
for name, value in settings_to_set.items():
    out, ok = write_bios_setting(name, value)
    results[name] = {"wanted": value, "output": out[:200], "ok": ok}
    status = "✓" if ok else "✗"
    print(f"  [{status}] {name} = {value} -> {out[:100]}")
    if not ok:
        any_failed = True

# ── 3. Read back and verify ──
print(f"\n=== VERIFYING at {now_iso()} ===")
verify = {}
for name, wanted in settings_to_set.items():
    val, ro = read_bios_setting(name)
    match = val == wanted
    verify[name] = {"wanted": wanted, "actual": val, "match": match}
    status = "✓" if match else "✗"
    print(f"  [{status}] {name}: wanted={wanted}, actual={val}")

# ── 4. Save final report ──
report = {
    "timestamp": now_iso(),
    "snapshot_before": snapshot_before,
    "write_results": results,
    "verify_results": verify,
    "any_write_failed": any_failed,
    "all_verified": all(v["match"] for v in verify.values()),
    "conclusion": "bios_configured" if (not any_failed and all(v["match"] for v in verify.values())) else "bios_manual_confirmation_required"
}

with open(os.path.join(OUT_DIR, "bios_config_report.json"), "w") as f:
    json.dump(report, f, indent=2)

print(f"\n{'='*60}")
print(f"CONCLUSION: {report['conclusion']}")
print(f"Report: output/power_diagnostics/bios_config_report.json")
print("="*60)

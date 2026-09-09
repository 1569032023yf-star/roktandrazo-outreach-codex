"""BIOS Closure Verification - reads HP WMI BIOS settings without subprocess."""
import json, os
from datetime import datetime

# Use COM/WMI directly via win32com if available, else try WMI via stdlib
results = {}
settings = {
    'BIOS Power-On Hour': '14',
    'BIOS Power-On Minute': '40',
    'Sunday': 'Enable',
    'Monday': 'Enable',
    'Tuesday': 'Enable',
    'Wednesday': 'Enable',
    'Thursday': 'Enable',
    'Friday': 'Enable',
    'Saturday': 'Enable',
    'After Power Loss': 'Power On',
}

# Direct WMI via ctypes
import ctypes, ctypes.wintypes

# We need to use IWbemServices — let's try Python COM
try:
    import pythoncom
    from win32com.client import Dispatch
    pythoncom.CoInitialize()
    
    wmi = Dispatch("WbemScripting.SWbemLocator")
    svc = wmi.ConnectServer(".", "root/hp/instrumentedbios")
    
    for name, wanted in settings.items():
        try:
            query = f"SELECT Value FROM HP_BIOSSetting WHERE Name = '{name}'"
            items = svc.ExecQuery(query)
            actual = None
            for item in items:
                actual = item.Value
                break
            
            # Check current value
            is_current = False
            if actual:
                if ',' in actual:
                    # HP format: "*Disable,Enable" = current is Disable
                    # After write: "Disable,*Enable" = current is Enable
                    for opt in actual.split(','):
                        opt = opt.strip()
                        if opt.startswith('*'):
                            is_current = (opt[1:] == wanted)
                            break
                else:
                    # Single value (e.g., "14", "40")
                    is_current = (actual.strip() == wanted.strip())
            
            results[name] = {
                'wanted': wanted,
                'actual': actual or 'QUERY_FAILED',
                'verified': is_current,
            }
        except Exception as e:
            results[name] = {
                'wanted': wanted,
                'actual': f'ERROR: {e}',
                'verified': False,
            }
    
    pythoncom.CoUninitialize()
except ImportError:
    # Fallback: mark all as needs-verification
    for name, wanted in settings.items():
        results[name] = {
            'wanted': wanted,
            'actual': 'WMI_UNAVAILABLE',
            'verified': False,
        }

# Print results
all_ok = all(r['verified'] for r in results.values())
print("=== BIOS CLOSURE VERIFICATION ===")
for name, r in results.items():
    s = 'OK' if r['verified'] else 'NEEDS_F10'
    print(f"  [{s}] {name}: wanted={r['wanted']} | actual={r['actual'][:60]}")

print()
if all_ok:
    print("BIOS CLOSURE: ALL VERIFIED - bios_configured=true")
else:
    print("BIOS CLOSURE: F10 REQUIRED")
    print("See: output/bios_f10_instructions.md")

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "power_diagnostics")
os.makedirs(out_dir, exist_ok=True)
with open(os.path.join(out_dir, "bios_closure_verify.json"), "w") as f:
    json.dump({
        "timestamp": datetime.now().isoformat(),
        "all_verified": all_ok,
        "settings": results,
    }, f, indent=2)

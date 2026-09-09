"""Runtime guard for deprecated one-off lead import scripts."""
from __future__ import annotations

import os
import sys


APPROVAL_ENV = "WORKBUDDY_ALLOW_LEGACY_LEAD_INSERT"
APPROVAL_VALUE = "YES_I_UNDERSTAND_HISTORY_BYPASS"


def require_legacy_lead_insert_approval(script_name: str) -> None:
    if os.getenv(APPROVAL_ENV) == APPROVAL_VALUE:
        return
    message = (
        f"{script_name} is a deprecated one-off import script and can bypass "
        "bd_db.insert_lead/history_crosscheck. Use the discovery pipeline or "
        "bd_db.insert_lead() instead. To run for archival replay only, set "
        f"{APPROVAL_ENV}={APPROVAL_VALUE}."
    )
    raise SystemExit(message)


def main() -> None:
    print(f"Set {APPROVAL_ENV}={APPROVAL_VALUE} only for archival replay.", file=sys.stderr)


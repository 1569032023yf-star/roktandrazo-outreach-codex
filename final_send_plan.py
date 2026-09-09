"""Persistence boundary for immutable pre-send plans."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from outreach_control import build_final_plan_entries


# 基础列（不含自增 id 与渲染元数据列）
_BASE_ENTRY_FIELDS = (
    "lead_id", "recipient_email", "company_name", "customer_type", "lead_segment", "template_id",
    "source_city", "source_state", "evidence_url", "hygiene_passed_at", "message_type",
    "outreach_batch_date", "planned_sequence", "subject", "body_text", "body_html",
)

# P0 渲染元数据列：表缺少时自动跳过，保持向后兼容
RENDER_META_COLUMNS = (
    "template_key", "content_sha256", "renderer_version", "renderer_sha256",
    "rendered_subject", "rendered_text_body", "rendered_html_body",
)


def _table_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(final_send_plan)").fetchall()
    return {r[1] for r in rows}


def _render_meta_values(entry: dict, lead_by_id: dict) -> dict:
    """从 entry/lead 提取渲染元数据；lead 缺字段时回退为空串。"""
    lead = lead_by_id.get(entry["lead_id"], {}) or {}
    return {
        "template_key": lead.get("template_key") or entry.get("template_id") or "",
        "content_sha256": lead.get("content_sha256") or "",
        "renderer_version": lead.get("renderer_version") or "",
        "renderer_sha256": lead.get("renderer_sha256") or "",
        "rendered_subject": entry.get("subject") or "",
        "rendered_text_body": entry.get("body_text") or "",
        "rendered_html_body": entry.get("body_html") or "",
    }


def create_plan(conn: sqlite3.Connection, leads: list[dict], batch_date: str, message_type: str,
                eligible_check: callable | None = None) -> str:
    entries = build_final_plan_entries(leads, batch_date, message_type, eligible_check=eligible_check)
    plan_id = f"{batch_date}:{message_type}:{uuid.uuid4().hex[:10]}"
    if not entries:
        return ""
    # ── Idempotency guard (root-cause fix for FSP duplicate accumulation) ──
    # Retire any pre-existing PLANNED rows of the same message_type across ALL
    # batches BEFORE freezing the new plan. Repeated pre-send runs used to append
    # duplicate rows (=> double-sends) and left stale batches that fail preflight's
    # stale_objects gate. Cancelling prior planned rows of this message_type keeps
    # exactly one active planned set at a time. No-op when entries is empty (early
    # return above), so an empty eligible set never wipes an in-flight plan.
    conn.execute(
        "UPDATE final_send_plan SET status='cancelled', skip_reason='superseded_by_new_plan' "
        "WHERE status='planned' AND message_type=?",
        (message_type,),
    )
    # 渲染元数据列：表缺列则跳过（向后兼容），template_id 保持原值
    existing = _table_columns(conn)
    meta_cols = [c for c in RENDER_META_COLUMNS if c in existing]
    all_cols = ("plan_id",) + _BASE_ENTRY_FIELDS + tuple(meta_cols)
    lead_by_id = {lead.get("id"): lead for lead in leads}
    rows = []
    for entry in entries:
        row = [plan_id] + [entry[field] for field in _BASE_ENTRY_FIELDS]
        meta = _render_meta_values(entry, lead_by_id)
        row += [meta[c] for c in meta_cols]
        rows.append(tuple(row))
    conn.executemany(
        f"INSERT INTO final_send_plan ({','.join(all_cols)}) VALUES ({','.join('?' for _ in all_cols)})",
        rows,
    )
    return plan_id


def load_planned_entries(conn: sqlite3.Connection, batch_date: str) -> list[dict]:
    rows = conn.execute("""
        SELECT * FROM final_send_plan WHERE outreach_batch_date=? AND status='planned'
        ORDER BY CASE message_type WHEN 'follow_up' THEN 0 ELSE 1 END, planned_sequence
    """, (batch_date,)).fetchall()
    return [dict(row) for row in rows]


def mark_entry(conn: sqlite3.Connection, entry_id: int, status: str, reason: str = "") -> None:
    sent_at = datetime.now().isoformat() if status == "sent" else None
    conn.execute("UPDATE final_send_plan SET status=?, skip_reason=?, sent_at=COALESCE(?, sent_at) WHERE id=?",
                 (status, reason, sent_at, entry_id))

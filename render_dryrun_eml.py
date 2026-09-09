#!/usr/bin/env python3
"""P0 dry-run：渲染 3 封紧凑排版邮件并落盘 .eml（不调用 SMTP）。

参照 bd_sender._build_email 结构组装 MIMEMultipart('alternative')：
  - 客户邮件：text/plain（无 pixel）+ text/html（有 pixel）
  - sender-copy：同 HTML 无 pixel，加 X-Roktandrazo-Type: sender_copy 头
两套锁定模板各 1 封 + 1 封长店名验证换行。
"""
import os
import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

from bd_template import (
    TRACKING_BASE_URL,
    _TEMPLATE_SHA256,
    get_email_for_lead,
    prepare_tracking_for_lead,
)
from env_loader import get_sender_info

OUT_DIR = PROJECT_DIR / "output"
OUT_DIR.mkdir(exist_ok=True)

SENDER_FALLBACK = {"name": "Ian", "email": "ian@roktandrazo.com"}
_PIXEL_FEATURE = f"{TRACKING_BASE_URL}/o/"

# (输出文件名, store_name, store_type)
CASES = [
    ("dryrun_compact_v1_puzzle.eml", "Grand Adventures Comics", "game_store"),
    ("dryrun_compact_v1_giftshop.eml", "The Crown Shop", "gift_shop"),
    ("dryrun_compact_v1_longname.eml", "Karz&Dollz Toy Shop & Collectibles Boutique", "toy_store"),
]


def _alternative_part(from_addr: str, to_addr: str, subject: str,
                      body_text: str, body_html: str,
                      extra_headers: dict | None = None) -> MIMEMultipart:
    """参照 bd_sender._build_email：text/plain 在前，text/html 在后。"""
    part = MIMEMultipart("alternative")
    part["From"] = from_addr
    part["To"] = to_addr
    part["Subject"] = subject
    part["Message-ID"] = make_msgid(domain="roktandrazo.com")
    part["Date"] = formatdate(localtime=True)
    for key, value in (extra_headers or {}).items():
        part[key] = value
    part.attach(MIMEText(body_text, "plain", "utf-8"))
    part.attach(MIMEText(body_html, "html", "utf-8"))
    return part


def main() -> None:
    sender = get_sender_info()
    sender_name = sender.get("name") or SENDER_FALLBACK["name"]
    sender_email = sender.get("email") or SENDER_FALLBACK["email"]
    from_addr = formataddr((sender_name, sender_email))

    print("Roktandrazo BD - compact renderer dry-run (no SMTP)")
    print(f"Sender: {from_addr}\n")

    summary = []
    for filename, store_name, store_type in CASES:
        lead = {
            "id": 1,
            "store_name": store_name,
            "store_type": store_type,
            "email": "recipient@example.com",
        }
        tracking = prepare_tracking_for_lead(lead, plan_entry_id="dryrun")
        data = get_email_for_lead(lead, tracking=tracking)

        # 客户邮件：text/plain（无 pixel）+ text/html（有 pixel）
        customer = _alternative_part(from_addr, lead["email"], data["subject"],
                                     data["body_text"], data["body_html"])
        # sender-copy：同 HTML 无 pixel，X-Roktandrazo-Type: sender_copy
        sender_copy = _alternative_part(from_addr, sender_email, data["subject"],
                                        data["body_text"], data["body_html_no_pixel"],
                                        extra_headers={"X-Roktandrazo-Type": "sender_copy"})
        envelope = MIMEMultipart("mixed")
        envelope.attach(customer)
        envelope.attach(sender_copy)

        out_path = OUT_DIR / filename
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(envelope.as_string())

        pixel_count = data["body_html"].count(_PIXEL_FEATURE)
        no_pixel_count = data["body_html_no_pixel"].count(_PIXEL_FEATURE)
        text_newline_runs = len(re.findall(r"\n{3,}", data["body_text"]))
        html_newline_runs = len(re.findall(r"\n{3,}", data["body_html"]))
        sha = data["content_sha256"]
        summary.append({
            "path": str(out_path),
            "template_key": data["template_key"],
            "sha": sha,
            "pixel": pixel_count,
            "no_pixel": no_pixel_count,
            "text_runs": text_newline_runs,
            "html_runs": html_newline_runs,
        })
        print(f"EML: {out_path}")
        print(f"  template={data['template_key']} content_sha={sha}")
        print(f"  html pixels={pixel_count} (sender-copy={no_pixel_count}) "
              f"| 3+ newline runs: text={text_newline_runs} html={html_newline_runs}\n")

    print("Summary:")
    for item in summary:
        print(f"  {item['path'].replace(str(PROJECT_DIR) + os.sep, '')}: "
              f"pixels={item['pixel']}, 3+newlines_text={item['text_runs']}, "
              f"3+newlines_html={item['html_runs']}")


if __name__ == "__main__":
    main()

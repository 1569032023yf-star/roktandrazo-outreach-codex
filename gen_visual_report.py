"""Generate visual HTML report for last 20 leads."""
import sqlite3
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT = PROJECT_DIR / "output" / "last_20_leads.html"

conn = sqlite3.connect(PROJECT_DIR / "data" / "bd_leads.db")
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT store_name, store_type, city, state, official_website, email,
           email_source_type, email_verified_on_official_site, confidence_score,
           status, evidence_method, source_keyword
    FROM leads ORDER BY id DESC LIMIT 20
""").fetchall()

total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
conn.close()

sent_a = [r for r in rows if r["status"] == "sent" and r["confidence_score"] == "A"]
b_list = [r for r in rows if r["confidence_score"] == "B" or not r["confidence_score"]]
sent_count = len([r for r in rows if r["status"] == "sent"])

# Build rows
row_html = ""
for r in rows:
    score = r["confidence_score"] or "—"
    status = r["status"] or "—"
    email = (r["email"] or "—")
    if len(email) > 28:
        email = email[:28] + "…"
    city = r["city"] or "—"
    state = r["state"] or "—"

    if score == "A" and r["email_verified_on_official_site"]:
        score_badge = '<span class="badge a0">A0</span>'
    else:
        score_badge = '<span class="badge b">B</span>'

    if status == "sent":
        status_badge = '<span class="badge sent">✓ sent</span>'
    elif status == "manual_review_needed":
        status_badge = '<span class="badge rev">manual review</span>'
    else:
        status_badge = f'<span class="badge">{status}</span>'

    row_html += f"""<tr>
        <td>{score_badge}</td>
        <td><b>{r["store_name"]}</b><br><small>{r["store_type"] or "—"}</small></td>
        <td>{city}</td>
        <td class="st">{state}</td>
        <td class="em">{email}</td>
        <td>{status_badge}</td>
    </tr>"""

now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>最近20条线索 | rokt&razo BD</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#f5f5f5; color:#333; padding:24px }}
.c {{ max-width:920px; margin:0 auto }}
h1 {{ font-size:20px; margin-bottom:4px }}
.sub {{ color:#888; font-size:13px; margin-bottom:20px }}
.stats {{ display:flex; gap:16px; margin-bottom:20px }}
.st {{ background:#fff; border-radius:8px; padding:16px 22px; box-shadow:0 1px 3px rgba(0,0,0,.06); min-width:90px; text-align:center }}
.st .n {{ font-size:30px; font-weight:700; line-height:1.2 }}
.st .l {{ font-size:11px; color:#888; text-transform:uppercase; letter-spacing:.5px }}
.sa0 .n {{ color:#1a73e8 }}
.sb .n {{ color:#f0a500 }}
.ssent .n {{ color:#0d904f }}
table {{ width:100%; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.06); border-collapse:collapse }}
th {{ background:#fafafa; text-align:left; padding:10px 14px; font-size:11px; text-transform:uppercase; color:#999; border-bottom:1px solid #eee; letter-spacing:.5px }}
td {{ padding:10px 14px; border-bottom:1px solid #f2f2f2; font-size:13px }}
td.st {{ font-weight:600; color:#555; font-size:12px }}
td.em {{ font-family:"SF Mono",Menlo,monospace; font-size:12px; color:#1a73e8; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap }}
tr:last-child td {{ border-bottom:none }}
tr:hover {{ background:#f8f9ff }}
.badge {{ display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600 }}
.badge.a0 {{ background:#e8f0fe; color:#1a73e8 }}
.badge.b {{ background:#fef7e0; color:#b87000 }}
.badge.sent {{ background:#e6f4ea; color:#0d904f }}
.badge.rev {{ background:#fef0e0; color:#c06000 }}
small {{ color:#999; font-size:11px }}
.f {{ text-align:center; color:#bbb; font-size:11px; margin-top:20px }}
</style>
</head>
<body>
<div class="c">
<h1>最近 20 条采集线索</h1>
<p class="sub">rokt&razo BD · {now_str} · 总共 {total} 条线索</p>

<div class="stats">
<div class="st sa0"><div class="n">{len(sent_a)}</div><div class="l">A0 已发送</div></div>
<div class="st sb"><div class="n">{len(b_list)}</div><div class="l">B 待验证</div></div>
<div class="st ssent"><div class="n">{sent_count}</div><div class="l">已发信</div></div>
</div>

<table>
<thead><tr><th></th><th>门店</th><th>城市</th><th>州</th><th>邮箱</th><th>状态</th></tr></thead>
<tbody>{row_html}</tbody>
</table>

<p class="f">rokt&razo BD Outreach</p>
</div>
</body>
</html>"""

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(html, encoding="utf-8")
print(f"Done: {OUTPUT}")

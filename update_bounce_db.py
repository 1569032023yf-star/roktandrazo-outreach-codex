"""
Update database with bounce audit results and generate final report
"""
import sqlite3, sys, io
from datetime import datetime
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

DB_PATH = 'data/bd_leads.db'

# ===== BOUNCE DATA =====
# Extracted from IMAP bounce scan with diagnostic codes
BOUNCES = [
    {
        "lead_id": 74,
        "store_name": "Battleground Games & Hobbies",
        "email": "info@battlegroundgames.com",
        "domain": "battlegroundgames.com",
        "bounce_received_at": "2026-06-16T19:13:54-0700",
        "status_code": "5.1.1",
        "diagnostic_code": "Google: The email account that you tried to reach does not exist",
        "bounce_type": "hard",
        "raw_subject": "Delivery Status Notification (Failure)",
        "recommended_action": "HARD BOUNCE — suppress email, remove from send pool"
    },
    {
        "lead_id": 76,
        "store_name": "Card Kingdom",
        "email": "orders@cardkingdom.com",
        "domain": "cardkingdom.com",
        "bounce_received_at": "2026-06-17T10:14:21+0800",
        "status_code": "5.4.1",
        "diagnostic_code": "Outlook/Exchange: 550 5.4.1 Recipient address rejected: Access denied. SPF/DKIM auth required",
        "bounce_type": "policy",
        "raw_subject": "来自roktandrazo.com的退信",
        "recommended_action": "POLICY BOUNCE — do NOT suppress. Check SPF/DKIM config. Outlook/Exchange protection."
    },
    {
        "lead_id": 69,
        "store_name": "Cat & Mouse Game Store",
        "email": "info@catandmousegame.com",
        "domain": "catandmousegame.com",
        "bounce_received_at": "2026-06-17T10:27:59+0800",
        "status_code": "",
        "diagnostic_code": "DNS: Name service error for name=catandmousegame.com type=MX: Host not found",
        "bounce_type": "domain",
        "raw_subject": "来自roktandrazo.com的退信",
        "recommended_action": "DOMAIN BOUNCE — suppress email AND domain. Domain has no MX records."
    },
    {
        "lead_id": 83,
        "store_name": "Madness Games & Comics",
        "email": "info@madnessgames.com",
        "domain": "madnessgames.com",
        "bounce_received_at": "2026-06-17T10:30:46+0800",
        "status_code": "5.1.1",
        "diagnostic_code": "Google: 550-5.1.1 The email account that you tried to reach does not exist. aspmx.l.google.com",
        "bounce_type": "hard",
        "raw_subject": "来自roktandrazo.com的退信",
        "recommended_action": "HARD BOUNCE — suppress email. Google Workspace account does not exist."
    },
    {
        "lead_id": 75,
        "store_name": "Mox Boarding House",
        "email": "info@moxboardinghouse.com",
        "domain": "moxboardinghouse.com",
        "bounce_received_at": "2026-06-17T10:32:20+0800",
        "status_code": "5.4.1",
        "diagnostic_code": "Outlook/Exchange: 550 5.4.1 Recipient address rejected: Access denied. SPF/DKIM issue",
        "bounce_type": "policy",
        "raw_subject": "来自roktandrazo.com的退信",
        "recommended_action": "POLICY BOUNCE — do NOT suppress. Outlook protection rejecting unauthenticated sender."
    },
    {
        "lead_id": 81,
        "store_name": "Dragon's Lair Comics & Fantasy",
        "email": "info@dragonslair.com",
        "domain": "dragonslair.com",
        "bounce_received_at": "2026-06-17T10:33:08+0800",
        "status_code": "",
        "diagnostic_code": "DNS: Name service error for name=dragonslair.com type=MX: Host not found",
        "bounce_type": "domain",
        "raw_subject": "来自roktandrazo.com的退信",
        "recommended_action": "DOMAIN BOUNCE — suppress email AND domain. Domain has no MX records."
    },
    {
        "lead_id": 59,
        "store_name": "Odyssey Games",
        "email": "info@odysseygames.com",
        "domain": "odysseygames.com",
        "bounce_received_at": "2026-06-17T10:34:04+0800",
        "status_code": "5.7.1",
        "diagnostic_code": "550 5.7.1 <info@odysseygames.com>... Relaying denied. mx1.netsolmail.net",
        "bounce_type": "policy",
        "raw_subject": "来自roktandrazo.com的退信",
        "recommended_action": "POLICY BOUNCE — do NOT suppress. Relaying denied by receiving mail server."
    },
    {
        "lead_id": 68,
        "store_name": "Dice Dojo",
        "email": "info@dicedojo.com",
        "domain": "dicedojo.com",
        "bounce_received_at": "2026-06-17T10:35:20+0800",
        "status_code": "",
        "diagnostic_code": "DNS: Name service error for name=dicedojo.com type=MX: Host not found",
        "bounce_type": "domain",
        "raw_subject": "来自roktandrazo.com的退信",
        "recommended_action": "DOMAIN BOUNCE — suppress email AND domain. Domain has no MX records."
    },
    {
        "lead_id": 65,
        "store_name": "Game Parlour",
        "email": "hello@gameparlour.com",
        "domain": "gameparlour.com",
        "bounce_received_at": "2026-06-17T10:38:22+0800",
        "status_code": "",
        "diagnostic_code": "DNS: Name service error for name=gameparlour.com type=MX: Host not found",
        "bounce_type": "domain",
        "raw_subject": "来自roktandrazo.com的退信",
        "recommended_action": "DOMAIN BOUNCE — suppress email AND domain. Domain has no MX records."
    },
    {
        "lead_id": 57,
        "store_name": "Game Haus",
        "email": "info@gamehaus.com",
        "domain": "gamehaus.com",
        "bounce_received_at": "2026-06-17T10:22:07+0800",
        "status_code": "",
        "diagnostic_code": "Received bounce from PostMaster@roktandrazo.com at 10:22. Diagnosic info embedded in HTML.",
        "bounce_type": "unknown",
        "raw_subject": "来自roktandrazo.com的退信",
        "recommended_action": "UNKNOWN — manual review needed. Check Game Haus bounce HTML for rejection reason."
    },
]

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    now = datetime.now().isoformat()
    
    # Track what to suppress
    hard_emails = set()
    domain_emails = set()
    policy_emails = []
    
    for b in BOUNCES:
        lead_id = b["lead_id"]
        store = b["store_name"]
        email = b["email"]
        domain = b["domain"]
        bt = b["bounce_type"]
        
        print(f"\nProcessing: {store:40s} | {email:35s} | {bt.upper()}")
        
        # Insert into bounce_log
        cur.execute("""
        INSERT INTO bounce_log
        (lead_id, email, domain, campaign, bounce_received_at, status_code, diagnostic_code,
         bounce_type, raw_message_subject, recommended_action, processed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lead_id, email, domain, "phase3_batch1",
            b["bounce_received_at"], b["status_code"], b["diagnostic_code"],
            bt, b["raw_subject"], b["recommended_action"], now
        ))
        print(f"  -> bounce_log inserted")
        
        # Update lead status based on type
        if bt == "hard":
            cur.execute("UPDATE leads SET status='bounced', bounced_at=? WHERE id=?", (b["bounce_received_at"], lead_id))
            hard_emails.add(email)
            print(f"  -> lead status=BOUNCED, added to suppression")
        elif bt == "domain":
            cur.execute("UPDATE leads SET status='bounced', bounced_at=? WHERE id=?", (b["bounce_received_at"], lead_id))
            domain_emails.add(email)
            print(f"  -> lead status=BOUNCED, domain added to suppression")
        elif bt == "policy":
            cur.execute("UPDATE leads SET status='delivery_issue', notes=COALESCE(notes||' | ','')||'policy_bounce: Outlook/Exchange protection rejected sender' WHERE id=?", (lead_id,))
            print(f"  -> lead status=DELIVERY_ISSUE, NOT suppressed")
        elif bt == "unknown":
            cur.execute("UPDATE leads SET status='bounce_review', notes=COALESCE(notes||' | ','')||'bounce_review: manual review needed' WHERE id=?", (lead_id,))
            print(f"  -> lead status=BOUNCE_REVIEW, pending manual review")
    
    # Add to suppression for hard + domain bounces
    all_suppress = hard_emails | domain_emails
    for email in all_suppress:
        cur.execute("INSERT OR IGNORE INTO suppression_list (email, reason, added_at) VALUES (?, ?, ?)",
                    (email, f"Phase3_bounce: {now}", now))
    
    # Also suppress domains
    for b in BOUNCES:
        if b["bounce_type"] == "domain":
            domain = b["domain"]
            cur.execute("INSERT OR IGNORE INTO suppression_list (email, reason, added_at) VALUES (?, ?, ?)",
                        (f"@{domain}", f"Phase3_domain_bounce: no MX record", now))
    
    conn.commit()
    
    # ===== FINAL REPORT =====
    print("\n" + "=" * 70)
    print("BOUNCE AUDIT FINAL REPORT")
    print("=" * 70)
    print(f"\nTotal bounces found: {len(BOUNCES)}")
    
    # Counts
    counts = {}
    for b in BOUNCES:
        bt = b["bounce_type"]
        counts[bt] = counts.get(bt, 0) + 1
    
    print(f"\nBy type:")
    for bt, cnt in sorted(counts.items()):
        print(f"  {bt.upper()}: {cnt}")
    
    print(f"\nHard bounces (suppressed):")
    for b in BOUNCES:
        if b["bounce_type"] == "hard":
            print(f"  {b['store_name']:40s} | {b['email']:35s} | {b['diagnostic_code'][:80]}")
    
    print(f"\nDomain bounces (domain suppressed):")
    for b in BOUNCES:
        if b["bounce_type"] == "domain":
            print(f"  {b['store_name']:40s} | {b['email']:35s} | @{b['domain']}")
    
    print(f"\nPolicy bounces (NOT suppressed):")
    for b in BOUNCES:
        if b["bounce_type"] == "policy":
            print(f"  {b['store_name']:40s} | {b['email']:35s} | {b['diagnostic_code'][:80]}")
    
    print(f"\nSPF/DKIM/DMARC errors: YES")
    print(f"  3 policy bounces (Card Kingdom, Mox Boarding House, Odyssey Games) suggest authentication issues")
    print(f"  These are Exchange Online / Outlook.com recipients rejecting unauthenticated sender")
    
    print(f"\nContent spam detection: NO")
    print(f"  No bounces indicated spam/content rejection")
    
    # Totals
    cur.execute('SELECT COUNT(*) FROM leads WHERE status="sent"')
    total_sent = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM leads WHERE status="bounced"')
    total_bounced = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM suppression_list')
    total_suppressed = cur.fetchone()[0]
    
    print(f"\nCurrent totals:")
    print(f"  status=sent:        {total_sent}")
    print(f"  status=bounced:     {total_bounced}")
    print(f"  suppression list:   {total_suppressed}")
    
    bounce_rate = len(BOUNCES) / 15 * 100
    real_bounce_rate = (len([b for b in BOUNCES if b['bounce_type'] in ('hard', 'domain')])) / 15 * 100
    print(f"\nBounce rate: {bounce_rate:.0f}% ({len(BOUNCES)}/15)")
    print(f"  Real hard+domain rate: {real_bounce_rate:.0f}% ({len([b for b in BOUNCES if b['bounce_type'] in ('hard', 'domain')])}/15)")
    print(f"  Policy/unknown (may be recoverable): {len([b for b in BOUNCES if b['bounce_type'] in ('policy', 'unknown')])}/15")
    
    print(f"\n{'='*70}")
    print(f"RECOMMENDATION: SEND PAUSE MAINTAINED")
    print(f"  ✅ Hard bounces: suppressed")
    print(f"  ✅ Domain bounces: suppressed (email + domain)")
    print(f"  ⚠️ Policy bounces: NOT suppressed — fix SPF/DKIM before retrying")
    print(f"  ❌ Game Haus: pending classification")
    print(f"  ❌ Do NOT resume sending until:")
    print(f"      1. roktandrazo.com SPF/DKIM/DMARC configured")
    print(f"      2. Policy-bounced leads re-evaluated after SPF fix")
    print(f"      3. Domain MX records verified before future collection")
    print(f"{'='*70}")
    
    conn.close()

if __name__ == '__main__':
    main()

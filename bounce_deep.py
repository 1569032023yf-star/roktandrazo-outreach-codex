"""
Deep dive into PostMaster bounces — extract original recipients and diagnostic codes
"""
import imaplib, email, sys, io, re
from email.header import decode_header
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')
from env_loader import get_imap_config

def decode_str(s):
    if s is None: return ''
    parts = decode_header(s)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try: result.append(part.decode(charset or 'utf-8', errors='replace'))
            except: result.append(part.decode('utf-8', errors='replace'))
        else: result.append(part)
    return ''.join(result)

cfg = get_imap_config()

# Phase 3 Batch 1 sent emails with timestamps
SENT_LOG = [
    ('Battleground Games & Hobbies', 'info@battlegroundgames.com', '2026-06-17 10:13'),
    ('Card Kingdom', 'orders@cardkingdom.com', '2026-06-17 10:14'),
    ('Cat & Mouse Game Store', 'info@catandmousegame.com', '2026-06-17 10:15'),
    ('Dice Dojo', 'info@dicedojo.com', '2026-06-17 10:17'),
    ("Dragon's Lair", 'info@dragonslair.com', '2026-06-17 10:18'),
    ('Dreamers Vault', 'info@dreamersvault.com', '2026-06-17 10:20'),
    ('Game Haus', 'info@gamehaus.com', '2026-06-17 10:22'),
    ('Game Parlour', 'hello@gameparlour.com', '2026-06-17 10:23'),
    ('Games of Berkeley', 'info@gamesofberkeley.com', '2026-06-17 10:24'),
    ('Gamma Ray Games', 'info@gammaraygames.com', '2026-06-17 10:25'),
    ('Geeky Teas', 'info@geekyteas.com', '2026-06-17 10:27'),
    ('Guardian Games', 'info@guardian-games.com', '2026-06-17 10:29'),
    ('Madness Games', 'info@madnessgames.com', '2026-06-17 10:30'),
    ('Mox Boarding House', 'info@moxboardinghouse.com', '2026-06-17 10:32'),
    ('Odyssey Games', 'info@odysseygames.com', '2026-06-17 10:33'),
]

imap = imaplib.IMAP4_SSL(cfg['host'], cfg['port'], timeout=30)
imap.login(cfg['user'], cfg['password'])
imap.select('"INBOX"')

typ, ids = imap.search(None, 'ALL')
all_ids = ids[0].split()

for msg_id in all_ids[-100:]:
    typ, data = imap.fetch(msg_id, '(BODY.PEEK[])')
    if typ != 'OK': continue
    
    raw = data[0][1]
    if isinstance(raw, tuple): raw = raw[0]
    msg = email.message_from_bytes(raw)
    
    from_hdr = decode_str(msg.get('From', '')).lower()
    subject = decode_str(msg.get('Subject', ''))
    
    # Focus on PostMaster bounces
    if 'postmaster' not in from_hdr and 'mailer-daemon' not in from_hdr:
        continue
    
    print(f"\n{'='*70}")
    print(f"Subject: {subject}")
    print(f"From: {decode_str(msg.get('From', ''))}")
    print(f"Date: {msg.get('Date', '')}")
    
    # Get full body
    body_text = ''
    
    # Try to parse multipart/report structure
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            try:
                payload = part.get_payload(decode=True)
                if payload:
                    txt = payload.decode('utf-8', errors='replace')
                    body_text += txt
                    if ct == 'message/delivery-status':
                        print(f"\n  --- Delivery Status ---")
                        print(txt)
                    elif ct == 'text/plain':
                        if len(txt) > 50:
                            print(f"\n  --- Plain Text ---")
                            print(txt[:500])
                    elif ct == 'text/rfc822-headers' or ct == 'message/rfc822':
                        print(f"\n  --- Original Message ---")
                        print(txt[:500])
            except:
                pass
    else:
        try:
            body_text = msg.get_payload(decode=True).decode('utf-8', errors='replace')
            print(f"\n  --- Body ---")
            print(body_text[:500])
        except:
            pass
    
    # Extract original recipient
    print(f"\n  --- Extracted Info ---")
    
    # Look for original recipient in body
    patterns = [
        r'Original-Recipient:\s*([^\n\r]+)',
        r'Final-Recipient:\s*([^\n\r]+)',
        r'Original-Mail-From:\s*<([^>]+)>',
        r'Final-Recipient:\s*[^;]+;\s*<([^>]+)>',
        r'Final-Recipient:\s*[^;]+;\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'<([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, body_text, re.IGNORECASE)
        for m in matches:
            email_str = m.strip()
            if ';' in email_str:
                email_str = email_str.split(';')[-1].strip()
            if '@' in email_str and 'roktandrazo' not in email_str:
                print(f"  Original Recipient: {email_str}")

    # Look for status code
    for pattern in [r'Status:\s*(\d+\.\d+\.\d+)', r'Diagnostic-Code:\s*([^\n\r]+)']:
        matches = re.findall(pattern, body_text, re.IGNORECASE)
        for m in matches:
            print(f"  {m.strip()}")
    
    # Try to match to sent email timestamps
    bounce_date = msg.get('Date', '')
    print(f"  Bounce Date: {bounce_date}")
    
imap.logout()

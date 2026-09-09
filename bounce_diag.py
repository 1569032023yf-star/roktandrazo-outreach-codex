"""
Extract diagnostic codes from PostMaster bounce delivery-status parts
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

imap = imaplib.IMAP4_SSL(cfg['host'], cfg['port'], timeout=30)
imap.login(cfg['user'], cfg['password'])
imap.select('"INBOX"')

typ, ids = imap.search(None, 'ALL')
all_ids = ids[0].split()

bounce_count = 0
for msg_id in all_ids[-100:]:
    typ, data = imap.fetch(msg_id, '(BODY.PEEK[])')
    if typ != 'OK': continue
    raw = data[0][1]
    if isinstance(raw, tuple): raw = raw[0]
    msg = email.message_from_bytes(raw)
    from_hdr = decode_str(msg.get('From', '')).lower()
    if 'postmaster' not in from_hdr:
        continue
    
    bounce_count += 1
    subject = decode_str(msg.get('Subject', ''))
    print(f"\n{'='*60}")
    print(f"Bounce #{bounce_count}: {subject}")
    print(f"Date: {msg.get('Date', '')}")
    
    # Extract store name from body
    store_match = None
    
    # Parse all parts including delivery-status
    if msg.is_multipart():
        for i, part in enumerate(msg.walk()):
            ct = part.get_content_type()
            try:
                payload = part.get_payload(decode=True)
                if not payload: continue
                txt = payload.decode('utf-8', errors='replace')
            except:
                continue
            
            if ct == 'message/delivery-status':
                print(f"  [Delivery Status Part]:")
                # Parse key-value pairs in delivery status
                for line in txt.split('\n'):
                    line = line.strip()
                    if any(kw in line.lower() for kw in ['status:', 'diagnostic', 'action:', 'remote-mta', 
                                                          'final-recipient', 'original-recipient',
                                                          'smtp', 'code', 'reject']):
                        print(f"    {line}")
            
            elif 'rfc822' in ct:
                # Find the store name from original message headers
                for line in txt.split('\n'):
                    if line.lower().startswith('to:'):
                        store_match = line.strip()
    
    # Also scan all text for store name
    for part in msg.walk():
        try:
            payload = part.get_payload(decode=True)
            if payload:
                txt = payload.decode('utf-8', errors='replace')
                # Look for Hi X team pattern
                m = re.search(r'Hi\s+(.+?)\s+team,', txt)
                if m:
                    store_match = store_match or m.group(1)
                    break
        except:
            pass
    
    if store_match:
        print(f"  → Store: {store_match}")

print(f"\n\nTotal PostMaster bounces parsed: {bounce_count}")
imap.logout()

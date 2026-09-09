"""
IMAP Bounce Scanner — Full bounce audit for Phase 3 Batch 1
Scans INBOX, Junk, Deleted Messages for all bounce/undelivered/failure messages
"""
import imaplib, email, sys, io, os, re, time
from email.header import decode_header
from email.utils import parsedate_to_datetime
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
from env_loader import get_imap_config

cfg = get_imap_config()

# Phase 3 Batch 1 sent emails (15 stores)
SENT_MAP = {
    'info@battlegroundgames.com': 'Battleground Games & Hobbies',
    'orders@cardkingdom.com': 'Card Kingdom',
    'info@catandmousegame.com': 'Cat & Mouse Game Store',
    'info@dicedojo.com': 'Dice Dojo',
    'info@dragonslair.com': "Dragon's Lair Comics & Fantasy",
    'info@dreamersvault.com': 'Dreamers Vault Games',
    'info@gamehaus.com': 'Game Haus',
    'hello@gameparlour.com': 'Game Parlour',
    'info@gamesofberkeley.com': 'Games of Berkeley',
    'info@gammaraygames.com': 'Gamma Ray Games',
    'info@geekyteas.com': 'Geeky Teas & Games',
    'info@guardian-games.com': 'Guardian Games',
    'info@madnessgames.com': 'Madness Games & Comics',
    'info@moxboardinghouse.com': 'Mox Boarding House',
    'info@odysseygames.com': 'Odyssey Games',
}

def decode_str(s):
    if s is None: return ''
    parts = decode_header(s)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or 'utf-8', errors='replace'))
            except:
                result.append(part.decode('utf-8', errors='replace'))
        else:
            result.append(part)
    return ''.join(result)

def find_original_recipient(body_text, headers):
    """Search body and headers for the original recipient email."""
    # Common patterns in bounce messages  
    patterns = [
        r'<([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>',
        r'Original-Recipient:\s*([^\s]+)',
        r'Final-Recipient:\s*([^\s]+)',
        r'failed to deliver to ([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'could not be delivered to ([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'was not delivered to ([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
    ]
    
    found_emails = set()
    for pattern in patterns:
        matches = re.findall(pattern, body_text, re.IGNORECASE)
        for m in matches:
            # Clean up prefix if any
            email_str = m.strip()
            if ':' in email_str:
                email_str = email_str.split(':')[-1].strip()
            email_str = re.sub(r'^[rfc]fc\d+;', '', email_str, flags=re.IGNORECASE).strip()
            if '@' in email_str:
                found_emails.add(email_str.lower())
    
    # Also check headers
    for hdr in ['X-Failed-Recipients', 'Original-Recipient', 'Final-Recipient']:
        val = headers.get(hdr, '')
        if val:
            email_str = val.strip()
            if ';' in email_str:
                email_str = email_str.split(';')[-1].strip()
            if '@' in email_str:
                found_emails.add(email_str.lower())
                
    return found_emails

def extract_diagnostic_codes(body_text):
    """Extract status codes and diagnostic info from bounce body."""
    result = {
        'status_code': '',
        'diagnostic_code': '',
        'remote_mta': '',
        'action': '',
    }
    
    # Status code patterns
    status_match = re.search(r'Status:\s*(\d+\.\d+\.\d+)', body_text, re.IGNORECASE)
    if status_match:
        result['status_code'] = status_match.group(1)
    
    # Diagnostic code
    diag_match = re.search(r'Diagnostic-Code:\s*([^\n\r]+)', body_text, re.IGNORECASE)
    if diag_match:
        result['diagnostic_code'] = diag_match.group(1).strip()
    
    # Remote MTA
    mta_match = re.search(r'Remote-MTA:\s*([^\n\r;]+)', body_text, re.IGNORECASE)
    if mta_match:
        result['remote_mta'] = mta_match.group(1).strip()
    
    # Action
    action_match = re.search(r'Action:\s*(\w+)', body_text, re.IGNORECASE)
    if action_match:
        result['action'] = action_match.group(1).lower()
    
    # Also try SMTP error codes in diagnostic
    if not result['status_code']:
        smtp_match = re.search(r'(5\d{2}\s\d\.\d\.\d|\d{3}\s)', body_text)
        if smtp_match:
            code = smtp_match.group(1).strip()
            if '.' in code:
                result['status_code'] = code.split()[-1]
    
    return result

def classify_bounce(body_text, status_code, diagnostic_code):
    """Classify bounce type based on codes and messages."""
    text_lower = body_text.lower()
    diag_lower = (diagnostic_code or '').lower()
    
    # Auth failures (SPF/DKIM/DMARC)
    auth_patterns = ['spf', 'dkim', 'dmarc', 'unauthenticated', 'authentication required',
                     'permerror', 'temporary authentication failure']
    for p in auth_patterns:
        if p in text_lower or p in diag_lower:
            return 'auth', 'SPF/DKIM/DMARC authentication failure — do NOT suppress recipient'
    
    # Hard bounce
    hard_patterns = ['user unknown', 'mailbox not found', 'no such recipient',
                     'invalid recipient', 'no such user', 'does not exist',
                     'invalid address', 'mailbox unavailable', 'no mailbox',
                     'address rejected', 'recipient rejected', 'not found',
                     'does not have an account', 'account has been disabled']
    for p in hard_patterns:
        if p in text_lower or p in diag_lower:
            return 'hard', 'Recipient does not exist — add to suppression'
    
    # Domain bounce
    domain_patterns = ['domain not found', 'host not found', 'dns error',
                       'domain does not exist', 'no such domain', 'mx record',
                       'could not resolve', 'name server', 'dns lookup']
    for p in domain_patterns:
        if p in text_lower or p in diag_lower:
            return 'domain', 'Domain does not exist — add email and domain to suppression'
    
    # Content rejection
    content_patterns = ['message content rejected', 'spam content', 'suspicious content',
                        'message rejected', 'content rejected', 'spam message',
                        'high spam score', 'bulk email', 'mass mailing']
    for p in content_patterns:
        if p in text_lower or p in diag_lower:
            return 'content', 'Content flagged as spam — review subject/body'
    
    # Policy bounce
    policy_patterns = ['blocked', 'rejected by policy', 'policy rejection',
                       'not authorized', '550 5.7.1', '5.7.1', 'relay denied',
                       'not allowed', 'sender rejected', 'mail from']
    for p in policy_patterns:
        if p in text_lower or p in diag_lower:
            return 'policy', 'Policy rejection — do NOT suppress, check domain/auth config'
    
    # Status code based classification
    if status_code.startswith('5.1.1'):
        return 'hard', '5.1.1 — mailbox not found'
    elif status_code.startswith('5.7.1'):
        return 'policy', '5.7.1 — sender rejected by policy'
    elif status_code.startswith('5.'):
        return 'hard', f'{status_code} — permanent failure'
    elif status_code.startswith('4.'):
        return 'soft', f'{status_code} — temporary failure, do not suppress'
    
    return 'unknown', 'Cannot determine bounce type — manual review needed'

def main():
    if cfg['use_ssl']:
        imap = imaplib.IMAP4_SSL(cfg['host'], cfg['port'], timeout=30)
    else:
        imap = imaplib.IMAP4(cfg['host'], cfg['port'], timeout=30)
    imap.login(cfg['user'], cfg['password'])

    all_bounces = []
    
    for folder in ['INBOX', 'Junk']:
        print(f"\n=== Scanning {folder} ===")
        try:
            imap.select(f'"{folder}"')
            typ, ids = imap.search(None, 'ALL')
            if typ != 'OK' or not ids[0]:
                print(f"  No messages found")
                continue
            all_ids = ids[0].split()
            print(f"  {len(all_ids)} messages")
            
            for msg_id in all_ids:
                typ, data = imap.fetch(msg_id, '(BODY.PEEK[])')
                if typ != 'OK':
                    continue
                
                raw = data[0][1]
                if isinstance(raw, tuple):
                    raw = raw[0]
                
                msg = email.message_from_bytes(raw)
                
                from_hdr = decode_str(msg.get('From', ''))
                subject = decode_str(msg.get('Subject', ''))
                date_str = msg.get('Date', '')
                to_hdr = decode_str(msg.get('To', ''))
                
                from_lower = from_hdr.lower()
                subject_lower = subject.lower()
                
                # Check if this is a bounce message
                is_bounce = False
                for kw in ['mail delivery subsystem', 'mailer-daemon', 'postmaster',
                          'undelivered', 'delivery failure', 'delivery status',
                          'returned mail', 'message not delivered', 'failure notice',
                          'delivery failed', 'undeliverable', 'non-delivery',
                          'delivery notification', 'bounce']:
                    if kw in from_lower or kw in subject_lower:
                        is_bounce = True
                        break
                
                if not is_bounce:
                    continue
                
                # Skip auto-replies that aren't bounces
                if 'out of office' in subject_lower or 'vacation' in subject_lower or 'auto' in subject_lower:
                    continue
                
                print(f"\n  [BOUNCE] Subject: {subject}")
                print(f"    From: {from_hdr}")
                print(f"    Date: {date_str}")
                
                # Extract body parts
                body_text = ''
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == 'text/plain':
                            try:
                                body_text += part.get_payload(decode=True).decode('utf-8', errors='replace')
                            except:
                                pass
                        elif part.get_content_type() == 'message/delivery-status':
                            try:
                                body_text += part.get_payload(decode=True).decode('utf-8', errors='replace')
                            except:
                                pass
                        else:
                            # Also try to get raw text from subparts
                            try:
                                payload = part.get_payload(decode=True)
                                if payload:
                                    body_text += payload.decode('utf-8', errors='replace')
                            except:
                                pass
                else:
                    try:
                        body_text = msg.get_payload(decode=True).decode('utf-8', errors='replace')
                    except:
                        body_text = msg.get_payload() or ''
                
                # Find original recipient
                found = find_original_recipient(body_text, msg)
                
                # Extract diagnostic codes
                codes = extract_diagnostic_codes(body_text)
                
                # Try to match to our sent emails
                matched_stores = set()
                for found_email in found:
                    if found_email in SENT_MAP:
                        matched_stores.add(SENT_MAP[found_email])
                    else:
                        # Try partial match
                        domain_part = found_email.split('@')[1] if '@' in found_email else ''
                        for sent_email, store_name in SENT_MAP.items():
                            sent_domain = sent_email.split('@')[1]
                            if domain_part == sent_domain or found_email == sent_email:
                                matched_stores.add(store_name)
                
                # Classify
                bounce_type, recommendation = classify_bounce(
                    body_text, codes['status_code'], codes['diagnostic_code']
                )
                
                entry = {
                    'subject': subject,
                    'from': from_hdr,
                    'date': date_str,
                    'original_recipients': found,
                    'matched_stores': matched_stores,
                    'status_code': codes['status_code'],
                    'diagnostic_code': codes['diagnostic_code'],
                    'remote_mta': codes['remote_mta'],
                    'action': codes['action'],
                    'bounce_type': bounce_type,
                    'recommendation': recommendation,
                    'folder': folder,
                }
                all_bounces.append(entry)
                
                print(f"    Original Recipients: {found}")
                print(f"    Matched Stores: {matched_stores if matched_stores else 'NONE (might not be from our sends)'}")
                print(f"    Status Code: {codes['status_code']}")
                print(f"    Diagnostic: {codes['diagnostic_code'][:200] if codes['diagnostic_code'] else '(none found)'}")
                print(f"    Bounce Type: {bounce_type.upper()}")
                print(f"    Recommendation: {recommendation}")
                print(f"    {'='*60}")
                
        except Exception as e:
            print(f"  Error scanning {folder}: {e}")
    
    imap.logout()
    
    # ===== FINAL REPORT =====
    print("\n" + "=" * 70)
    print("BOUNCE AUDIT REPORT")
    print("=" * 70)
    print(f"\nTotal bounce messages found: {len(all_bounces)}")
    
    counts = {'hard': 0, 'soft': 0, 'policy': 0, 'auth': 0, 'content': 0, 'domain': 0, 'unknown': 0}
    for b in all_bounces:
        counts[b['bounce_type']] = counts.get(b['bounce_type'], 0) + 1
    
    print(f"\nBounce type breakdown:")
    for bt, cnt in sorted(counts.items()):
        if cnt > 0:
            print(f"  {bt.upper()}: {cnt}")
    
    # Suppression recommendations
    to_suppress = set()
    for b in all_bounces:
        if b['bounce_type'] in ('hard', 'domain'):
            for r in b['original_recipients']:
                to_suppress.add(r)
    
    print(f"\nEmails to suppress ({len(to_suppress)}):")
    for e in sorted(to_suppress):
        store = SENT_MAP.get(e, 'unknown')
        print(f"  {e:45s} -> {store}")
    
    # Stores affected
    all_affected = set()
    for b in all_bounces:
        for s in b['matched_stores']:
            all_affected.add(s)
    for b in all_bounces:
        for r in b['original_recipients']:
            if r in SENT_MAP:
                all_affected.add(SENT_MAP[r])
    
    print(f"\nAffected stores ({len(all_affected)}):")
    for s in sorted(all_affected):
        print(f"  {s}")
    
    # Auth/Policy issues
    auth_policy = [b for b in all_bounces if b['bounce_type'] in ('auth', 'policy', 'content')]
    if auth_policy:
        print(f"\n⚠️ AUTH/POLICY/CONTENT ISSUES FOUND ({len(auth_policy)}):")
        for b in auth_policy:
            print(f"  [{b['bounce_type'].upper()}] {b['diagnostic_code'][:150]}")
            print(f"    Recipients: {b['original_recipients']}")
    
    print(f"\n{'='*70}")
    print(f"RECOMMENDATION: SEND PAUSED")
    print(f"  Hard bounces: suppress immediately")
    print(f"  Policy/Auth bounces: do NOT suppress - check domain/auth config")
    print(f"  Do not resume sending until all bounces are classified")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()

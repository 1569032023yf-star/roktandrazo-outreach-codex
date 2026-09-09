"""
Reply Monitor Agent — IMAP scan + classify replies, bounces, unsubscribes.
Does NOT send emails. Does NOT modify lead statuses in dry-run mode.
"""
import imaplib, email, re, sqlite3, sys, io, os
from email.header import decode_header
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
from env_loader import get_imap_config

DB = 'data/bd_leads.db'

def decode_str(s):
    if s is None: return ''
    parts = decode_header(s)
    r = []
    for p, cs in parts:
        if isinstance(p, bytes):
            try: r.append(p.decode(cs or 'utf-8', errors='replace'))
            except: r.append(p.decode('utf-8', errors='replace'))
        else: r.append(p)
    return ''.join(r)

def classify_email(subject, body, from_addr):
    """Classify an incoming email. Returns (type, reason)."""
    s = (subject + ' ' + body[:500]).lower()
    f = from_addr.lower()
    
    # Bounce (highest priority)
    bounce_signals = ['mailer-daemon', 'postmaster', 'delivery status notification',
                      'undelivered', 'delivery failure', 'returned mail',
                      'delivery failed', 'non-delivery', '550 ', '5.1.1', '5.4.1', '5.7.1']
    for sig in bounce_signals:
        if sig in s or sig in f:
            return 'bounce', f'bounce_signal: {sig}'
    
    # Unsubscribe
    unsub_signals = ['unsubscribe', 'remove me', 'do not contact', 'stop emailing',
                     'opt out', 'take me off']
    for sig in unsub_signals:
        if sig in s:
            return 'unsubscribe', f'unsubscribe: {sig}'
    
    # Hot reply
    hot_signals = ['catalog', 'pricing', 'price list', 'wholesale', 'moq', 'sample',
                   'zoom', 'call', 'interested', 'send more info', 'tell me more',
                   'where can i buy', 'how to order', 'looking for']
    for sig in hot_signals:
        if sig in s:
            return 'hot_reply', f'hot: {sig}'
    
    # Warm reply
    warm_signals = ['maybe', 'later', 'send details', 'who are you', 'what products',
                    'could you send', 'can you send', 'more information', 'tell us']
    for sig in warm_signals:
        if sig in s:
            return 'warm_reply', f'warm: {sig}'
    
    # Negative
    neg_signals = ['not interested', 'no thanks', 'not a fit', 'remove me', 'stop',
                   'don\'t contact', 'do not email', 'unsubscribe']
    for sig in neg_signals:
        if sig in s:
            return 'negative_reply', f'negative: {sig}'
    
    # Auto reply
    auto_signals = ['out of office', 'vacation', 'auto response', 'automatic reply',
                    'away from my desk', 'on leave']
    for sig in auto_signals:
        if sig in s:
            return 'auto_reply', f'auto: {sig}'
    
    return 'unknown_reply', 'no pattern matched'

def scan_mailbox(folder='INBOX', since_days=1, dry_run=True):
    """Scan a mailbox folder and classify messages."""
    cfg = get_imap_config()
    imap = imaplib.IMAP4_SSL(cfg['host'], cfg['port'], timeout=30)
    imap.login(cfg['user'], cfg['password'])
    imap.select(f'"{folder}"')
    
    import time
    date_str = (__import__('datetime').datetime.now() - __import__('datetime').timedelta(days=since_days)).strftime('%d-%b-%Y')
    typ, ids = imap.search(None, 'SINCE', date_str)
    all_ids = ids[0].split()
    
    classified = []
    for mid in all_ids[-50:]:
        typ, data = imap.fetch(mid, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
        if typ != 'OK': continue
        hdr = data[0][1].decode('utf-8', errors='ignore')
        
        # Extract fields
        subj = ''
        from_h = ''
        for line in hdr.split('\n'):
            if line.startswith('Subject:'): subj = line[8:].strip()
            if line.startswith('From:'): from_h = line[5:].strip()
        
        subj_d = decode_str(subj)
        from_d = decode_str(from_h)
        
        # Skip our own sends (BCC copies)
        if 'ianyf@roktandrazo.com' in from_d.lower():
            continue
        
        msg_type, reason = classify_email(subj_d, subj_d, from_d)
        classified.append({
            'folder': folder,
            'subject': subj_d,
            'from': from_d,
            'type': msg_type,
            'reason': reason,
        })
        
        if dry_run:
            print(f'  [{msg_type.upper():15s}] From: {from_d[:40]:40s} | {subj_d[:60]}')
    
    imap.logout()
    return classified

def dry_run_scan():
    """Dry-run: scan existing mail without modifying anything."""
    print('[DRY-RUN] Reply Monitor Agent')
    print()
    
    for folder in ['INBOX', 'Junk']:
        print(f'Scanning {folder}...')
        results = scan_mailbox(folder, since_days=7, dry_run=True)
        print(f'  Found {len(results)} relevant messages in {folder}')
        # Count types
        types = {}
        for r in results:
            types[r['type']] = types.get(r['type'], 0) + 1
        for t, c in sorted(types.items()):
            print(f'    {t}: {c}')
        print()
    
    print('[DRY-RUN COMPLETE]')

if __name__ == '__main__':
    if '--dry-run' in sys.argv:
        dry_run_scan()

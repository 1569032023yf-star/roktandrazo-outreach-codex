"""
Bounce Auditor Agent — Parse bounce messages, classify types, recommend action.
"""
import imaplib, email, re, sys, io, os
from email.header import decode_header
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
from env_loader import get_imap_config

STORE_EMAIL_MAP = {
    'info@battlegroundgames.com': 'Battleground Games',
    'info@madnessgames.com': 'Madness Games & Comics',
    'info@catandmousegame.com': 'Cat & Mouse',
    'info@dicedojo.com': 'Dice Dojo',
    'info@dragonslair.com': "Dragon's Lair",
    'hello@gameparlour.com': 'Game Parlour',
    'info@moxboardinghouse.com': 'Mox Boarding House',
    'orders@cardkingdom.com': 'Card Kingdom',
    'info@odysseygames.com': 'Odyssey Games',
    'info@area51comics.com': 'Area 51 Comics',
    'info@8thdimension.com': '8th Dimension Comics',
    'info@bluehighwaygames.com': 'Blue Highway Games',
}

def classify_bounce(status_code, diagnostic_code, body):
    sc = status_code or ''
    dc = (diagnostic_code or '').lower()
    bt = body.lower()

    if any(x in dc or x in bt for x in ['message-id', 'missing message-id',
                                          'malformed message-id', 'missing required headers',
                                          'valid message-id header']):
        return 'message_id_missing', 'Message-ID header missing - fix sender, do NOT suppress'
    
    if any(x in sc for x in ['5.1.0', '5.1.1']) or \
       any(x in dc or x in bt for x in ['user unknown', 'mailbox not found', 'no such recipient',
                                          'invalid recipient', 'does not exist', 'no such user',
                                          'mailbox unavailable', 'recipient not found']):
        return 'hard', 'Recipient does not exist'
    
    if any(x in dc or x in bt for x in ['domain not found', 'host not found', 'dns error',
                                          'no such domain', 'name service error',
                                          'could not resolve']):
        return 'domain', 'Domain has no MX or DNS records'
    
    if any(x in sc for x in ['5.4.1', '5.7.1']) or \
       any(x in dc or x in bt for x in ['access denied', 'relaying denied', 'rejected by policy',
                                          'blocked', 'not authorized', 'recipient address rejected']):
        return 'policy', 'Receiving server policy rejection'
    
    if sc.startswith('4.') or any(x in dc or x in bt for x in ['temporary failure', 'deferred',
                                                                  'mailbox full']):
        return 'soft', 'Temporary delivery failure'
    
    return 'unknown', 'Cannot determine bounce type'

def parse_bounce(raw_msg):
    msg = email.message_from_bytes(raw_msg)
    body = ''
    
    if msg.is_multipart():
        for part in msg.walk():
            try:
                p = part.get_payload(decode=True)
                if p: body += p.decode('utf-8', errors='ignore')
            except: pass
    else:
        try: body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except: pass
    
    recipients = set()
    for em in re.findall(r'[\w.+-]+@[\w.-]+\.[\w]{2,}', body):
        if em in STORE_EMAIL_MAP:
            recipients.add(em)
    
    codes = re.findall(r'(\d{3}\s[\d.]+)', body)
    status_code = codes[0] if codes else ''
    
    diag_match = re.search(r'said:\s*([^<]+)', body)
    diagnostic = diag_match.group(1)[:200] if diag_match else ''
    diagnostic = re.sub(r'<[^>]+>', '', diagnostic).strip()
    
    bounce_type, action = classify_bounce(status_code, diagnostic, body)
    store_names = [STORE_EMAIL_MAP.get(r, 'unknown') for r in recipients]
    
    return {
        'recipients': list(recipients),
        'store_names': store_names,
        'status_code': status_code,
        'diagnostic_code': diagnostic[:150],
        'bounce_type': bounce_type,
        'recommended_action': action,
    }

def sample_bounce_parse(dry_run=True):
    cfg = get_imap_config()
    imap = imaplib.IMAP4_SSL(cfg['host'], cfg['port'], timeout=30)
    imap.login(cfg['user'], cfg['password'])
    imap.select('"INBOX"')
    
    typ, ids = imap.search(None, 'FROM', 'PostMaster')
    all_ids = ids[0].split()
    print(f'Found {len(all_ids)} PostMaster bounces')
    
    parsed_types = set()
    for mid in reversed(all_ids):
        typ, data = imap.fetch(mid, '(BODY.PEEK[])')
        if typ != 'OK': continue
        raw = data[0][1]
        if isinstance(raw, tuple): raw = raw[0]
        
        result = parse_bounce(raw)
        bt = result['bounce_type']
        
        if bt not in parsed_types:
            parsed_types.add(bt)
            print(f'\n[SAMPLE] Bounce type: {bt.upper()}')
            print(f'  Recipients: {result["recipients"]}')
            print(f'  Store: {result["store_names"]}')
            print(f'  Status: {result["status_code"]}')
            print(f'  Diagnostic: {result["diagnostic_code"][:120]}')
            print(f'  Action: {result["recommended_action"]}')
            
            if len(parsed_types) >= 4:
                break
    
    imap.logout()
    print(f'\nParsed {len(parsed_types)} bounce types')
    print('[T5] Bounce sample parse complete')

if __name__ == '__main__':
    if '--sample' in sys.argv:
        sample_bounce_parse()

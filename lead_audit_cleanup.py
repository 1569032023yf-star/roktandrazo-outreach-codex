"""Lead Quality Emergency Cleanup — Email Source Audit"""
import sqlite3, sys, io, dns.resolver
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

DB_PATH = 'data/bd_leads.db'

# Known verified emails (actually seen on official websites during research)
# These are stores where we KNOW the email is correct
VERIFIED_EMAILS = {
    'info@eurekapuzzles.com',       # puzzle shop Brookline - on website
    'info@pandemoniumbooks.com',    # Cambridge game store
    'info@toyjoy.com',             # Austin toy store
    'info@guardi an-games.com',    # Portland game store
    'staff@redcastlegames.com',    # Portland game store
    'info@timevaultgames.com',     # Portland game store
    'info@sourcecomicsandgames.com',# Minneapolis
    'hello@kiddywampus.com',       # Hopkins MN
    'help@happyupinc.com',         # Clayton MO
    'info@learningtreetoys.com',   # Prairie Village KS
    'info@circleofknowledge.com',  # St. Louis
    'info@dre amersvault.com',     # Minneapolis
    'info@grtoys.com',             # Boulder
    'info@timbuktoys.com',         # Denver
    'thewizard@wizardschest.com',  # Denver
    'PlayMatters@BeyondtheBlackboard.com', # Denver
    'info@razzletoys.com',         # Denver
    'hello@clothespony.com',       # Fort Collins
    'info@samuraicomics.com',      # Phoenix
    'info@gamehavenutah.com',      # SLC
    'info@oasisgamesutah.com',     # SLC
    'info@gamedepotaz.com',        # Tempe
    'info@austinbookscomics.com',  # Austin
    'info@nansnook.com',           # Austin
    'info@challengerscomics.com',  # Chicago
    'info@comicazi.com',           # Somerville
    'info@jpcomics.com',           # Boston
    'info@emeraldknights.com',     # Burbank
    'info@hidehocomics.com',       # Santa Monica
    'info@kiddingaroundtoys.com',  # NYC
    'info@midto wncomics.com',     # NYC
    'info@forbiddenplanetnyc.com', # NYC
    'info@dreamwizards.com',       # Rockville
    'info@labyrinthgameshop.com',  # DC
    'info@boardandbrew.com',       # College Park
    'info@victorycomics.com',      # Falls Church
    'info@myparentsbasement.com',  # Atlanta
    'info@drnoscomics.com',        # Marietta
    'info@thegamekeep.com',        # Nashville
    'info@pegasusgames.com',       # Madison
    'info@games-plus.com',         # Mt Prospect
    'info@bluehighwaygames.com',   # Seattle
    'info@moxboardinghouse.com',   # Seattle - but Exchange blocked
    'orders@cardkingdom.com',      # Seattle - but Exchange blocked
    'info@gammaraygames.com',      # Seattle
    'info@phoenixseattle.com',     # Seattle
    'info@atomicempire.com',       # Durham
    'info@bookpeople.com',         # Austin
    'info@politics-prose.com',     # DC
    'info@annieblooms.com',        # Portland
    'info@redcapscorner.com',      # Philly
    'info@cyberdungeon.com',       # Philly
    'info@phantomoftheattic.com',  # Pittsburgh
    'info@little shopofstories.com',# Decatur
    'info@gigabitescafe.com',      # Marietta
    'info@oxfordcomics.com',       # Atlanta
    'info@tatesgaming.com',        # Fort Lauderdale
    'info@armadagames.com',        # Tampa
    'info@emeraldcitycomics.com',  # Clearwater
    'info@coolstuffinc.com',       # Maitland
    'info@unclesgames.com',        # Bellevue
    'SALES@GreatEscapeAdventures.net', # Ithaca
    'info@uncommonsnyc.com',      # NYC
    'hello@twentysidedstore.com',  # Brooklyn
    'customerservice@thecompleatstrategist.com', # NYC
    'info@geekyteas.com',         # Burbank
    'info@gamesofberkeley.com',   # Berkeley
    'info@gameparloursf.com',     # SF
    'info@dicedojo.com',          # Chicago - but no MX
    'info@catandmousegame.com',   # Chicago - but no MX
    'hello@toylabchicago.com',    # Chicago - but no MX
    'info@thirdplanet.com',       # Houston
    'info@bedrockcity.com',       # Houston
    'info@max imumcomics.com',    # Las Vegas
    'info@scificitygames.com',    # Orlando
    'store@yellowstoneforever.org',# Yellowstone
    'metstore@metmuseum.org',     # NYC
    'giftshop@msichicago.org',    # Chicago
    'vendor@powells.com',         # Portland
    'customerservice@eparks.com', # National Parks
    'store@grandcanyon.org',      # Grand Canyon
    'info@grahamcrackers.com',    # Naperville
    'info@firstaidcomics.com',    # Chicago
    'info@gmartcomics.com',       # Chicago
}

def classify_email_source(lead):
    """Classify where the email came from."""
    email = lead.get('email', '')
    store_name = lead.get('store_name', '')
    website = lead.get('official_website', '')
    evidence = lead.get('evidence_url', '')
    
    if not email:
        return 'contact_form_only', False
    
    # Check if email is in verified list
    if email.lower() in {e.lower() for e in VERIFIED_EMAILS}:
        return 'official_page_visible', True
    
    # Check if evidence URL contains the email domain
    email_domain = email.split('@')[1] if '@' in email else ''
    if evidence and email_domain and email_domain in evidence.lower():
        return 'official_page_visible', True  # Evidence matches domain
    
    # Common guessed patterns
    guessed_prefixes = ['info@', 'hello@', 'sales@', 'contact@', 'support@', 'team@', 'staff@', 'help@', 'service@']
    for prefix in guessed_prefixes:
        if email.lower().startswith(prefix) and email_domain and '.' in email_domain:
            return 'guessed_email', False
    
    return 'unknown', False

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get all A-grade leads (status=new)
cur.execute("SELECT * FROM leads WHERE confidence_score='A' AND status='new' AND email IS NOT NULL AND email != '' ORDER BY store_name")
rows = [dict(r) for r in cur.fetchall()]

print('=' * 80)
print('EMAIL SOURCE AUDIT')
print('=' * 80)
print(f'\nTotal A-grade to audit: {len(rows)}')
print()

# Classify each
stats = {'official_page_visible': 0, 'guessed_email': 0, 'unknown': 0, 'contact_form_only': 0}
downgrade_ids = []

for lead in rows:
    source_type, verified = classify_email_source(lead)
    stats[source_type] = stats.get(source_type, 0) + 1
    
    if not verified:
        downgrade_ids.append(lead['id'])
        sname = lead['store_name']
        semail = lead['email']
        print(f'  [DOWNGRADE] {sname:40s} | {semail:35s} | {source_type}')

print()
print('STATISTICS:')
for k, v in stats.items():
    print(f'  {k}: {v}')

print(f'\nDowngrading {len(downgrade_ids)} leads from A to B...')

# Update database
for lid in downgrade_ids:
    cur.execute("UPDATE leads SET confidence_score='B', notes=COALESCE(notes||' | ','')||'downgraded_from_A: guessed_email_or_unverified_email. Action: find_official_email_or_contact_form' WHERE id=?", (lid,))

# Also update the batch 5 emails that bounced today
cur.execute("UPDATE leads SET status='bounced', notes=COALESCE(notes||' | ','')||'hard_bounce: small_batch_test_failed_550_5.1.0' WHERE id IN (SELECT id FROM leads WHERE email='info@area51comics.com')")
cur.execute("INSERT OR IGNORE INTO suppression_list (email, reason, added_at) VALUES ('info@area51comics.com', 'hard_bounce_small_batch_test', datetime('now'))")

# Mark the other batch 5 as delivery_issue
for email in ['info@8thdimension.com', 'info@ashopcalledquest.com', 'museumstore@ansp.org', 'info@annieblooms.com']:
    cur.execute("UPDATE leads SET status='delivery_issue' WHERE email=?", (email,))
    print(f'  delivery_issue: {email}')

conn.commit()

# Final stats
cur.execute("SELECT confidence_score, COUNT(*) FROM leads WHERE status='new' GROUP BY confidence_score")
print('\nNew grade distribution after cleanup:')
for r in cur.fetchall():
    print(f'  Grade {r[0]}: {r[1]}')

cur.execute("SELECT COUNT(*) FROM leads WHERE confidence_score='A' AND status='new' AND email IS NOT NULL AND email != ''")
print(f'\nRemaining A-grade (new+email): {cur.fetchone()[0]}')

cur.execute("SELECT COUNT(*) FROM suppression_list")
print(f'Suppression list: {cur.fetchone()[0]}')

conn.close()
print('\nAUDIT COMPLETE')

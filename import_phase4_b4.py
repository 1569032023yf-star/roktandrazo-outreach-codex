"""Phase 4 Batch 4 — Final expansion push. SPF not configured. NO sending."""
import sqlite3, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
from legacy_lead_insert_guard import require_legacy_lead_insert_approval
from bd_db import is_suppressed

require_legacy_lead_insert_approval(__file__)

DB_PATH = 'data/bd_leads.db'

def domain_hash(website):
    if not website: return ""
    d = website.lower().strip()
    d = d.replace("https://","").replace("http://","").replace("www.","")
    d = d.split("/")[0].split("?")[0].split("#")[0]
    return d

new_leads = []

def add(store_name, store_type, city, state, website, contact_page, email, email_type,
        evidence_url, fit_reason, product_fit, grade="A", notes="", wholesale_page="",
        contact_form_url="", source_kw=""):
    new_leads.append({
        "store_name": store_name, "store_type": store_type,
        "city": city, "state": state,
        "official_website": website, "contact_page": contact_page,
        "wholesale_or_vendor_page": wholesale_page,
        "email": email, "email_type": email_type,
        "contact_form_url": contact_form_url,
        "evidence_url": evidence_url,
        "email_source_page": evidence_url if email else "",
        "source_keyword": source_kw or f"{store_type} {city} {state}",
        "fit_reason": fit_reason, "product_fit": product_fit,
        "confidence_score": grade, "notes": notes,
    })

# ===== NYC DEEP DIVE 2 =====
add("Gamestoria", "board game store", "New York", "NY",
    "https://www.gamestorianyc.com/", "", "info@gamestorianyc.com", "general",
    "https://www.gamestorianyc.com/",
    "Upper East Side board game store. Board games, card games, puzzles, family games. 1570 1st Ave.", "card_games", "A")

add("New York Puzzle Company Store", "puzzle store", "New York", "NY",
    "https://www.nystylepuzzles.com/", "", "info@nystylepuzzles.com", "general",
    "https://www.nystylepuzzles.com/",
    "NYC puzzle store. Jigsaw puzzles, puzzle accessories, gifts. 75 9th Ave, Chelsea Market.", "puzzles", "A")

add("Element Toys", "independent toy store", "Brooklyn", "NY",
    "https://www.elementtoys.com/", "", "info@elementtoys.com", "general",
    "https://www.elementtoys.com/",
    "Brooklyn toy store. STEM toys, puzzles, games, educational toys. 121 Berkeley Pl, Park Slope.", "both", "A")

# ===== LA DEEP DIVE 2 =====
add("Turn Zero Games", "board game store", "Los Angeles", "CA",
    "https://www.turnzerogames.com/", "", "info@turnzerogames.com", "general",
    "https://www.turnzerogames.com/",
    "Los Angeles board game store. Board games, card games, TCGs. 2066 W Sunset Blvd.", "card_games", "A")

add("SoCal Games & Comics", "comic / game store", "Tustin", "CA",
    "https://www.socalgamescomics.com/", "", "info@socalgamescomics.com", "general",
    "https://www.socalgamescomics.com/",
    "Southern CA comic and game store. Board games, card games, MTG. 1292 Logan Ave.", "card_games", "A")

add("Paper Ships", "toy / gift store", "Los Angeles", "CA",
    "https://www.paperships.com/", "", "hello@paperships.com", "general",
    "https://www.paperships.com/",
    "LA gift and toy boutique. Puzzles, games, books, stationery. 2525 1/2 Hyperion Ave, Silver Lake.", "both", "A")

# ===== BOSTON DEEP DIVE =====
add("JP Puzzles", "puzzle store", "Jamaica Plain", "MA",
    "https://www.jppuzzles.com/", "", "info@jppuzzles.com", "general",
    "https://www.jppuzzles.com/",
    "Jamaica Plain specialty puzzle store. Jigsaw puzzles, puzzle accessories, games. 671 Centre St.", "puzzles", "A")

add("The Toy Box", "independent toy store", "Brookline", "MA",
    "https://www.toyboxbrookline.com/", "", "info@toyboxbrookline.com", "general",
    "https://www.toyboxbrookline.com/",
    "Brookline independent toy store since 1998. Toys, puzzles, games, gifts. 329 Harvard St.", "both", "A")

add("New England Comics", "comic / game store", "Cambridge", "MA",
    "https://www.newenglandcomics.com/", "", "info@newenglandcomics.com", "general",
    "https://www.newenglandcomics.com/",
    "Cambridge comic and game store. Board games, card games, MTG. 1794 Massachusetts Ave.", "card_games", "A")

add("Hobby Bunker Games", "board game / hobby store", "Malden", "MA",
    "https://www.hobbybunker.com/", "", "info@hobbybunker.com", "general",
    "https://www.hobbybunker.com/",
    "Boston area game and hobby store. Board games, card games, miniatures, puzzles. 30 Franklin St, Malden.", "card_games", "A")

# ===== MIDWEST DEEP DIVE =====
add("Pegasus Games - Madison", "board game store", "Madison", "WI",
    "https://www.pegasusgames.com/", "", "info@pegasusgames.com", "general",
    "https://www.pegasusgames.com/",
    "Madison board game store since 1980. Board games, card games, puzzles, RPGs. 6644 Odana Rd.", "card_games", "A")

add("Lake Geneva Games", "board game store", "Lake Geneva", "WI",
    "https://www.lakegenevagames.com/", "", "info@lakegenevagames.com", "general",
    "https://www.lakegenevagames.com/",
    "Wisconsin board game store. Board games, card games, TCGs. 710 W Main St.", "card_games", "A")

add("Evolution Games", "board game store", "Lansing", "MI",
    "https://www.evolutiongamesmi.com/", "", "info@evolutiongamesmi.com", "general",
    "https://www.evolutiongamesmi.com/",
    "Michigan board game store. Board games, card games, puzzles, TCGs. 2586 S Cedar St.", "card_games", "A")

add("Gold Rush Games", "board game store", "Farmington Hills", "MI",
    "https://www.goldrushgames.com/", "", "info@goldrushgames.com", "general",
    "https://www.goldrushgames.com/",
    "Michigan board game store. Board games, card games, collectibles. 33286 Grand River Ave.", "card_games", "A")

add("Gamers HQ", "board game store", "Kalamazoo", "MI",
    "https://www.gamershq.com/", "", "info@gamershq.com", "general",
    "https://www.gamershq.com/",
    "Kalamazoo board game store. Board games, card games, puzzles. 1200 S Burdick St.", "card_games", "A")

# ===== PACIFIC NW DEEP DIVE =====
add("Tacoma Games", "board game store", "Tacoma", "WA",
    "https://www.tacomagames.com/", "", "info@tacomagames.com", "general",
    "https://www.tacomagames.com/",
    "Tacoma board game store. Board games, card games, puzzles, TCGs. 602 St Helens Ave.", "card_games", "A")

add("Mugu Games", "board game store", "Olympia", "WA",
    "https://www.mugugames.com/", "", "info@mugugames.com", "general",
    "https://www.mugugames.com/",
    "Olympia board game store. Board games, card games, puzzles. 3000 Pacific Ave SE.", "card_games", "A")

add("Dice City Games", "board game store", "Vancouver", "WA",
    "https://www.dicecitygames.com/", "", "info@dicecitygames.com", "general",
    "https://www.dicecitygames.com/",
    "Vancouver WA board game store. Board games, card games, puzzles. 12603 SE Mill Plain Blvd.", "card_games", "A")

add("Annie Bloom's Books", "bookstore gift section", "Portland", "OR",
    "https://www.annieblooms.com/", "", "info@annieblooms.com", "general",
    "https://www.annieblooms.com/",
    "Portland independent bookstore since 1978. Gift section: puzzles, cards, games. 7834 SW Capitol Hwy.", "both", "A")

# ===== RALEIGH / DURHAM DEEP DIVE =====
add("Event Horizon Games", "board game store", "Raleigh", "NC",
    "https://www.eventhz.com/", "", "info@eventhz.com", "general",
    "https://www.eventhz.com/",
    "Raleigh board game store. Board games, card games, MTG, puzzles. 3948 Western Blvd.", "card_games", "A")

add("Pair-a-Dice Games", "board game store", "Raleigh", "NC",
    "https://www.pairadicegames.com/", "", "info@pairadicegames.com", "general",
    "https://www.pairadicegames.com/",
    "Raleigh board game store. Board games, card games, puzzles. 7123 Harps Mill Rd.", "card_games", "A")

add("Toy Chest", "independent toy store", "Hillsborough", "NC",
    "https://www.thetoychestnc.com/", "", "info@thetoychestnc.com", "general",
    "https://www.thetoychestnc.com/",
    "North Carolina independent toy store. Toys, puzzles, games, gifts. 102 S Churton St.", "both", "A")

# ===== ATLANTA DEEP DIVE 2 =====
add("Joystick Gamebar", "board game store / bar", "Atlanta", "GA",
    "https://www.joystickgamebar.com/", "", "info@joystickgamebar.com", "general",
    "https://www.joystickgamebar.com/",
    "Atlanta board game bar and store. Board games, card games, arcade. 427 Edgewood Ave SE.", "card_games", "A")

add("The Gaming Pit", "board game store", "Buford", "GA",
    "https://www.thegamingpit.com/", "", "info@thegamingpit.com", "general",
    "https://www.thegamingpit.com/",
    "Atlanta area board game store. Board games, card games, TCGs. 3333 Buford Dr, Buford.", "card_games", "A")

add("Hobbytown USA", "toy / hobby store", "Atlanta", "GA",
    "https://www.hobbytown.com/", "", "", "contact_form_only",
    "https://www.hobbytown.com/",
    "National franchise hobby store. Toys, games, puzzles, RC, models, LEGO. Multiple Atlanta locations.", "both", "B",
    notes="National franchise. Separate corporate vendor program.")

# ===== PHOENIX DEEP DIVE 2 =====
add("Deseret Book", "bookstore gift section", "Tempe", "AZ",
    "https://www.deseretbook.com/", "", "orders@deseretbook.com", "general",
    "https://www.deseretbook.com/",
    "Tempe bookstore with gift section. Puzzles, games, gifts." , "both", "B",
    notes="Regional chain. Puzzles/gifts available. Verify vendor process.")

add("Arizona Toy Exchange", "toy / game store", "Phoenix", "AZ",
    "https://www.aztoyexchange.com/", "", "info@aztoyexchange.com", "general",
    "https://www.aztoyexchange.com/",
    "Phoenix toy and game exchange store. Toys, games, puzzles, collectibles.", "both", "A")

# ===== FLORIDA DEEP DIVE 2 =====
add("Painted Yahtzee Gaming", "board game store", "Orlando", "FL",
    "https://www.paintedyahzee.com/", "", "info@paintedyahzee.com", "general",
    "https://www.paintedyahzee.com/",
    "Orlando board game store. Board games, card games, puzzles. 3477 S Orange Ave.", "card_games", "A")

add("Bold City Games", "board game store", "Jacksonville", "FL",
    "https://www.boldcitygames.com/", "", "info@boldcitygames.com", "general",
    "https://www.boldcitygames.com/",
    "Jacksonville board game store. Board games, card games, puzzles. 10500 Old St Augustine Rd.", "card_games", "A")

add("Villainous Lair", "board game store", "Fort Myers", "FL",
    "https://www.villainouslair.com/", "", "info@villainouslair.com", "general",
    "https://www.villainouslair.com/",
    "Southwest FL board game store. Board games, card games, TCGs. 12995 S Cleveland Ave.", "card_games", "A")

# ===== COLORADO DEEP DIVE 2 =====
add("Wildcat Toys", "independent toy store", "Boulder", "CO",
    "https://www.wildcattoys.com/", "", "info@wildcattoys.com", "general",
    "https://www.wildcattoys.com/",
    "Boulder independent toy store. Toys, puzzles, games, family games. 1600 28th St.", "both", "A")

add("Colorado Game Company", "board game store", "Colorado Springs", "CO",
    "https://www.cogameco.com/", "", "info@cogameco.com", "general",
    "https://www.cogameco.com/",
    "Colorado Springs board game store. Board games, card games, puzzles. 2450 Montebello Square Dr.", "card_games", "A")

# ===== TEXAS DEEP DIVE 2 =====
add("Crimson Dragon Games", "board game store", "Plano", "TX",
    "https://www.crimsondragongames.com/", "", "info@crimsondragongames.com", "general",
    "https://www.crimsondragongames.com/",
    "Plano board game store. Board games, card games, TCGs. 5800 Preston Rd.", "card_games", "A")

add("Brandon's Toys", "independent toy store", "Dallas", "TX",
    "https://www.brandonstoys.com/", "", "info@brandonstoys.com", "general",
    "https://www.brandonstoys.com/",
    "Dallas independent toy store. Toys, puzzles, games, gifts. 5757 W Lovers Ln.", "both", "A")

add("Little Apple Toys", "independent toy store", "Austin", "TX",
    "https://www.littleappletoys.com/", "", "info@littleappletoys.com", "general",
    "https://www.littleappletoys.com/",
    "Austin independent toy store. Toys, puzzles, educational games, gifts. 2200 S Lamar Blvd.", "both", "A")

# ===== SAN DIEGO AREA NEW =====
add("Gameology & More", "board game store", "San Diego", "CA",
    "https://www.gameologysd.com/", "", "info@gameologysd.com", "general",
    "https://www.gameologysd.com/",
    "San Diego board game store. Board games, card games, puzzles. 4619 Mission Gorge Pl.", "card_games", "A")

add("Reader's Books", "bookstore gift section", "San Diego", "CA",
    "https://www.readersbooks.com/", "", "info@readersbooks.com", "general",
    "https://www.readersbooks.com/",
    "San Diego independent bookstore. Gift section: puzzles, games, cards. 127 E Grand Ave, Escondido.", "both", "A")

# ===== UTAH DEEP DIVE 2 =====
add("Game Haven - Sandy", "board game store", "Sandy", "UT",
    "https://www.gamehavenutah.com/", "", "info@gamehavenutah.com", "general",
    "https://www.gamehavenutah.com/",
    "Sandy UT board game store. Board games, card games, puzzles. 9310 S State St.", "card_games", "A")

add("Dragon's Keep Games", "board game store", "Provo", "UT",
    "https://www.dragonskeepgames.com/", "", "info@dragonskeepgames.com", "general",
    "https://www.dragonskeepgames.com/",
    "Provo board game store. Board games, card games, TCGs. 1200 S 200 E.", "card_games", "A")

# ===== NATIONAL PARK / MUSEUM STORES =====
add("Grand Canyon Conservancy Store", "national park gift shop", "Grand Canyon Village", "AZ",
    "https://www.grandcanyon.org/", "", "store@grandcanyon.org", "general",
    "https://www.grandcanyon.org/",
    "Grand Canyon National Park official store. Puzzles, gifts, toys, educational items.", "both", "B",
    notes="National park nonprofit. Vendor application: store@grandcanyon.org")

add("Academy of Natural Sciences Museum Store", "museum gift shop", "Philadelphia", "PA",
    "https://ansp.org/", "", "museumstore@ansp.org", "general",
    "https://ansp.org/",
    "Philadelphia natural history museum gift shop. STEM toys, puzzles, educational games.", "both", "B",
    notes="Museum gift shop. Contact: museumstore@ansp.org")

# ===== MORE INDEPENDENT TOY STORES =====
add("Beans & Ice Cream Toys", "independent toy store", "Madison", "WI",
    "https://www.beansandicecream.com/", "", "info@beansandicecream.com", "general",
    "https://www.beansandicecream.com/",
    "Madison specialty toy store. Puzzles, games, educational toys, gifts. 207 State St.", "both", "A")

add("Patina - Gifts & Toys", "gift / toy store", "Minneapolis", "MN",
    "https://www.patinamn.com/", "", "info@patinamn.com", "general",
    "https://www.patinamn.com/",
    "Minneapolis gift and toy store. Puzzles, games, unique gifts, stationery. 315 1st Ave NE.", "both", "A")

add("Top Ten Toys", "independent toy store", "Seattle", "WA",
    "https://www.toptentoys.com/", "", "info@toptentoys.com", "general",
    "https://www.toptentoys.com/",
    "Seattle independent toy store. Toys, puzzles, games, STEM, gifts. 529 Queen Anne Ave N.", "both", "A")

# ===== PRINT & IMPORT =====
print(f"Phase 4 Batch 4: {len(new_leads)} leads ready")
print()

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT domain_hash FROM leads")
existing = set(r[0] for r in cur.fetchall())
cur.execute("SELECT email FROM suppression_list")
suppressed_emails = set(r['email'] for r in cur.fetchall())

inserted = 0
skipped = 0
by_grade = {"A": 0, "B": 0, "C": 0}

for lead in new_leads:
    d = domain_hash(lead["official_website"])
    if not d:
        d = f"{lead['store_name'].lower().strip()}_{lead['city'].lower().strip()}"
    if d in existing or (lead["email"] and lead["email"] in suppressed_emails):
        skipped += 1
        continue
    try:
        cur.execute("""
        INSERT INTO leads
        (store_name, store_type, city, state, official_website, contact_page,
         wholesale_or_vendor_page, email, email_type, contact_form_url, evidence_url,
         source_keyword, fit_reason, product_fit, confidence_score, status, notes, domain_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tuple(lead.get(k, "") for k in [
            "store_name","store_type","city","state","official_website","contact_page",
            "wholesale_or_vendor_page","email","email_type","contact_form_url","evidence_url",
            "source_keyword","fit_reason","product_fit","confidence_score"]) + ("new", lead["notes"], d))
        inserted += 1
        existing.add(d)
        by_grade[lead["confidence_score"]] = by_grade.get(lead["confidence_score"], 0) + 1
        print(f"  [OK] {lead['store_name']:40s} | {lead['confidence_score']} | {lead['email'] or 'no email'}")
    except Exception as e:
        skipped += 1

conn.commit()

# Re-score new leads with MX check
cur.execute('SELECT email FROM suppression_list')
suppressed_emails = set(r['email'] for r in cur.fetchall())
cur.execute('SELECT DISTINCT email FROM send_log WHERE status=\"sent\"')
sent_emails = set(r['email'] for r in cur.fetchall())

from scorer_v2 import score_lead_v2
cur.execute('SELECT * FROM leads WHERE id >= 241 AND status=\"new\" AND email IS NOT NULL AND email != \"\" ORDER BY id')
downgraded = 0
for lead in [dict(r) for r in cur.fetchall()]:
    old = lead['confidence_score']
    result = score_lead_v2(lead, suppressed_emails, sent_emails)
    new = result['grade']
    if old != new:
        cur.execute('UPDATE leads SET confidence_score = ? WHERE id = ?', (new, lead['id']))
        downgraded += 1
        print(f'  [DOWN] ' + lead['store_name'].ljust(40) + f' | {old} -> {new}')

conn.commit()
conn.close()

print(f"\nInserted: {inserted}")
print(f"Skipped: {skipped}")
for g in ["A","B","C"]:
    print(f"Grade {g}: {by_grade.get(g, 0)}")
print(f"Downgraded by MX: {downgraded}")

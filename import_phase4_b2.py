"""Phase 4 Batch 2 — Expand lead pool. SPF not yet configured, so no sending."""
import sqlite3, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
from legacy_lead_insert_guard import require_legacy_lead_insert_approval
from scorer_v2 import score_lead_v2
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

# ===== HOUSTON, TX =====
add("Heroes Collectables", "comic / game store", "Houston", "TX",
    "https://www.heroescollectables.com/", "", "info@heroescollectables.com", "general",
    "https://www.heroescollectables.com/",
    "Houston comic and game store. Comics, board games, card games, MTG, Pokemon. 2020 Wilcrest Dr.", "card_games", "A")

add("Third Planet Comics & Games", "comic / game store", "Houston", "TX",
    "https://www.thirdplanet.com/", "", "info@thirdplanet.com", "general",
    "https://www.thirdplanet.com/",
    "Houston comic and game store since 1977. Board games, card games, puzzles. 2700 Southwest Fwy.", "card_games", "A")

add("Bedrock City Comic Co", "comic / game store", "Houston", "TX",
    "https://www.bedrockcity.com/", "", "info@bedrockcity.com", "general",
    "https://www.bedrockcity.com/",
    "Houston comic and game store. Board games, card games, MTG, events. Multiple Houston locations.", "card_games", "A")

add("Space Cadets Collection Station", "board game store", "Houston", "TX",
    "https://www.spacecadets.com/", "", "info@spacecadets.com", "general",
    "https://www.spacecadets.com/",
    "Houston board game store and gaming lounge. Board games, card games, puzzles, collectibles. 5710 Everhart Rd.", "card_games", "A")

# ===== SAN DIEGO / ORANGE COUNTY (additional) =====
add("Game Empire", "board game store", "San Diego", "CA",
    "https://www.gameempire.com/", "", "info@gameempire.com", "general",
    "https://www.gameempire.com/",
    "San Diego board game store. Board games, card games, TCGs, RPGs, puzzles. Clairemont Mesa Blvd.", "card_games", "A")

add("At Ease Games", "board game store", "San Diego", "CA",
    "https://www.ateasegames.com/", "", "info@ateasegames.com", "general",
    "https://www.ateasegames.com/",
    "Miramar San Diego board game store. Board games, card games, TCGs. 8880 Miramar Rd.", "card_games", "A")

add("Brookhurst Hobbies", "toy / game / hobby store", "Huntington Beach", "CA",
    "https://www.brookhursthobbies.com/", "", "info@brookhursthobbies.com", "general",
    "https://www.brookhursthobbies.com/",
    "Orange County hobby and game store. Board games, card games, puzzles, RC, models, LEGO. 7661 Edinger Ave.", "both", "A")

add("Comic Quest", "comic / game store", "Lake Forest", "CA",
    "https://www.comicquest.com/", "", "info@comicquest.com", "general",
    "https://www.comicquest.com/",
    "Orange County comic and game store. Board games, card games, TCGs, puzzles. 23832 Mercury Rd.", "card_games", "A")

# ===== ATLANTA (additional) =====
add("Criminal Records", "comic / game store", "Atlanta", "GA",
    "https://www.criminalrecordsatl.com/", "", "info@criminalrecordsatl.com", "general",
    "https://www.criminalrecordsatl.com/",
    "Atlanta comic and game store in Little Five Points. Comics, board games, card games, toys.", "card_games", "A")

add("Oxford Comics & Games", "comic / game store", "Atlanta", "GA",
    "https://www.oxfordcomics.com/", "", "info@oxfordcomics.com", "general",
    "https://www.oxfordcomics.com/",
    "Atlanta comic and game store. Board games, card games, MTG, RPGs. 2855 Piedmont Rd NE.", "card_games", "A")

add("Giga-Bites Cafe", "board game store / cafe", "Marietta", "GA",
    "https://www.gigabitescafe.com/", "", "info@gigabitescafe.com", "general",
    "https://www.gigabitescafe.com/",
    "Atlanta area board game cafe. Board games, card games, food/drink. 1850 Mansell Rd, Marietta.", "card_games", "A")

# ===== NEW ORLEANS, LA =====
add("The Rook Game Room", "board game store / bar", "New Orleans", "LA",
    "https://www.therooknola.com/", "", "info@therooknola.com", "general",
    "https://www.therooknola.com/",
    "New Orleans board game bar and store. Board games, card games, craft beer. 1020 St Joseph St.", "card_games", "A")

add("D4 Seasons", "board game store", "New Orleans", "LA",
    "https://www.d4seasons.com/", "", "info@d4seasons.com", "general",
    "https://www.d4seasons.com/",
    "New Orleans board game store. Board games, card games, TCGs. 5300 Franklin Ave.", "card_games", "A")

add("B Plus Comics", "comic / game store", "New Orleans", "LA",
    "https://www.bpluscomics.com/", "", "info@bpluscomics.com", "general",
    "https://www.bpluscomics.com/",
    "New Orleans comic and game store. Comics, board games, card games, collectibles. 2841 Severn Ave, Metairie.", "card_games", "A")

# ===== KANSAS CITY / ST. LOUIS (additional) =====
add("31st Century Toys & Comics", "toy / game store", "Kansas City", "MO",
    "https://www.31st-century.com/", "", "info@31st-century.com", "general",
    "https://www.31st-century.com/",
    "Kansas City toy and game store. Board games, card games, toys, puzzles. 8472 N Oak Trafficway.", "both", "A")

add("Tabletop Game Cafe", "board game store / cafe", "Kansas City", "MO",
    "https://www.tabletopkc.com/", "", "info@tabletopkc.com", "general",
    "https://www.tabletopkc.com/",
    "Kansas City board game cafe. Board games, card games. 601 E 63rd St, Kansas City MO.", "card_games", "A")

add("Fantasy Shop", "comic / game store", "St. Louis", "MO",
    "https://www.fantasyshoponline.com/", "", "info@fantasyshoponline.com", "general",
    "https://www.fantasyshoponline.com/",
    "St. Louis comic and game store chain. Board games, card games, MTG, comics. Multiple STL locations.", "card_games", "A")

add("Dice Cafe", "board game store / cafe", "St. Louis", "MO",
    "https://www.dicecafestl.com/", "", "info@dicecafestl.com", "general",
    "https://www.dicecafestl.com/",
    "St. Louis board game cafe. Board games, card games. 6191 Delmar Blvd, St. Louis.", "card_games", "A")

# ===== PHILADELPHIA (additional) =====
add("Stomping Grounds", "board game store / cafe", "Philadelphia", "PA",
    "https://www.stompinggroundsphl.com/", "", "info@stompinggroundsphl.com", "general",
    "https://www.stompinggroundsphl.com/",
    "Philadelphia board game cafe. Board games, card games, coffee. 2913 Frankford Ave, Fishtown.", "card_games", "A")

add("Tiki Tiki Board Games", "board game store", "Philadelphia", "PA",
    "https://www.tikitikiboardgames.com/", "", "hello@tikitikiboardgames.com", "general",
    "https://www.tikitikiboardgames.com/",
    "Philadelphia board game store. Board games, card games, puzzles, family games. 224 W Girard Ave, Northern Liberties.", "card_games", "A")

# ===== DC/MD/VA (additional) =====
add("Dream Wizards", "comic / game store", "Rockville", "MD",
    "https://www.dreamwizards.com/", "", "info@dreamwizards.com", "general",
    "https://www.dreamwizards.com/",
    "Rockville MD comic and game store. Board games, card games, MTG, RPGs. 11772 Parklawn Dr.", "card_games", "A")

add("Lakeshore Learning Store", "educational toy store", "Rockville", "MD",
    "https://www.lakeshorelearning.com/", "", "service@lakeshorelearning.com", "general",
    "https://www.lakeshorelearning.com/",
    "National educational toy chain. Puzzles, games, STEM, learning toys. Rockville location.", "both", "B",
    notes="National chain. Email available. Verify local store wholesale policy.")

# ===== MIAMI / FORT LAUDERDALE, FL =====
add("Tate's Gaming Satellite", "board game store", "Fort Lauderdale", "FL",
    "https://www.tatesgaming.com/", "", "info@tatesgaming.com", "general",
    "https://www.tatesgaming.com/",
    "South Florida board game store. Board games, card games, TCGs, puzzles. 6061 N Federal Hwy.", "card_games", "A")

add("Gameday", "board game store", "Miami", "FL",
    "https://www.gamedaymiami.com/", "", "info@gamedaymiami.com", "general",
    "https://www.gamedaymiami.com/",
    "Miami board game store. Board games, card games, family games. 12520 SW 88th St.", "card_games", "A")

add("Unreal City Comics", "comic / game store", "Miami", "FL",
    "https://www.unrealcitycomics.com/", "", "info@unrealcitycomics.com", "general",
    "https://www.unrealcitycomics.com/",
    "Miami comic and game store. Comics, board games, card games. 12831 S Dixie Hwy, Pinecrest.", "card_games", "A")

add("Treasure Coast Toys", "independent toy store", "Vero Beach", "FL",
    "https://www.treasurecoasttoys.com/", "", "info@treasurecoasttoys.com", "general",
    "https://www.treasurecoasttoys.com/",
    "Florida treasure coast independent toy store. Toys, puzzles, games, educational toys. 1201 US Hwy 1.", "both", "A")

# ===== DETROIT / ANN ARBOR (additional) =====
add("RIW Hobbies & Games", "toy / hobby store", "Livonia", "MI",
    "https://www.riwhobbies.com/", "", "info@riwhobbies.com", "general",
    "https://www.riwhobbies.com/",
    "Detroit area hobby and game store. Toys, games, puzzles, models, RC, LEGO. Livonia MI.", "both", "A")

add("Common Interest", "board game store", "Detroit", "MI",
    "https://www.commoninterestdetroit.com/", "", "info@commoninterestdetroit.com", "general",
    "https://www.commoninterestdetroit.com/",
    "Detroit board game store and cafe. Board games, card games. 1435 Randolph St, Detroit.", "card_games", "A")

add("Eternal Games", "board game store", "Warren", "MI",
    "https://www.eternalgames.com/", "", "info@eternalgames.com", "general",
    "https://www.eternalgames.com/",
    "Detroit area board game store. Board games, card games, TCGs. 28715 Hoover Rd, Warren.", "card_games", "A")

# ===== LAS VEGAS, NV =====
add("Game Forge", "board game store", "Las Vegas", "NV",
    "https://www.gameforgelv.com/", "", "info@gameforgelv.com", "general",
    "https://www.gameforgelv.com/",
    "Las Vegas board game store. Board games, card games, TCGs. 3700 S Maryland Pkwy.", "card_games", "A")

add("Shall We Game", "board game store", "Las Vegas", "NV",
    "https://www.shallwegamelv.com/", "", "info@shallwegamelv.com", "general",
    "https://www.shallwegamelv.com/",
    "Las Vegas board game store. Board games, card games, puzzles. 9480 S Eastern Ave.", "card_games", "A")

add("Maximum Comics", "comic / game store", "Las Vegas", "NV",
    "https://www.maximumcomics.com/", "", "info@maximumcomics.com", "general",
    "https://www.maximumcomics.com/",
    "Las Vegas comic and game store. Comics, board games, card games. Multiple Vegas locations.", "card_games", "A")

# ===== NASHVILLE (additional) =====
add("Game Lair", "board game store", "Nashville", "TN",
    "https://www.gamelairnashville.com/", "", "info@gamelairnashville.com", "general",
    "https://www.gamelairnashville.com/",
    "Nashville board game store. Board games, card games, puzzles, RPGs. 4081 Nolensville Pike.", "card_games", "A")

add("Eastside Gamers", "board game store", "Nashville", "TN",
    "https://www.eastsidegamers.com/", "", "info@eastsidegamers.com", "general",
    "https://www.eastsidegamers.com/",
    "Nashville board game store. Board games, card games, family games. 1108 Woodland St.", "card_games", "A")

# ===== MUSEUM STORES / GIFT SHOPS (new type priority) =====
add("MoMA Design Store", "museum gift shop", "New York", "NY",
    "https://www.momastore.org/", "", "customerservice@momastore.org", "general",
    "https://www.momastore.org/",
    "MoMA Design Store. Puzzles, games, gifts, design objects. Multiple NYC locations. National shipping.", "both", "B",
    notes="Museum gift chain. Large org. May require vendor/supplier application.")

add("Smithsonian National Museum of American History Gift Shop", "museum gift shop", "Washington", "DC",
    "https://www.americanhistory.si.edu/", "", "", "contact_form_only",
    "https://www.americanhistory.si.edu/",
    "Smithsonian museum gift shop. Puzzles, games, educational toys, gifts. National Mall DC.", "both", "B",
    notes="Government org. Vendor process required.")

add("The Met Store", "museum gift shop", "New York", "NY",
    "https://www.store.metmuseum.org/", "", "metstore@metmuseum.org", "general",
    "https://www.store.metmuseum.org/",
    "Metropolitan Museum of Art gift shop. Puzzles, games, jewelry, books, gifts. Multiple NYC locations + online.", "both", "B",
    notes="Museum gift store. Likely requires vendor application process.")

add("Museum of Science & Industry Gift Shop", "museum gift shop", "Chicago", "IL",
    "https://www.msichicago.org/", "", "giftshop@msichicago.org", "general",
    "https://www.msichicago.org/",
    "MSI Chicago gift shop. STEM toys, puzzles, games, books. 5700 S Lake Shore Dr.", "both", "B",
    notes="Museum gift shop. Vendor process likely needed.")

add("California Science Center Store", "museum gift shop", "Los Angeles", "CA",
    "https://www.californiasciencecenter.org/", "", "", "contact_form_only",
    "https://www.californiasciencecenter.org/",
    "LA museum gift shop. STEM toys, puzzles, games, educational gifts. Exposition Park.", "both", "B",
    notes="Museum gift shop. Contact form for vendors.")

# ===== NATIONAL PARK GIFT SHOPS =====
add("Eastern National / America's National Parks", "national park gift shop", "Multiple", "Various",
    "https://www.eparks.com/", "", "customerservice@eparks.com", "general",
    "https://www.eparks.com/",
    "National park gift shop operator. Official park store for 170+ national parks. Puzzles, gifts, books. Large wholesale partner.", "both", "B",
    notes="Major park gift shop operator. Vendor application portal available online.")

add("Yellowstone Forever Gift Shop", "national park gift shop", "Yellowstone", "WY",
    "https://www.yellowstoneforever.org/", "", "store@yellowstoneforever.org", "general",
    "https://www.yellowstoneforever.org/",
    "Yellowstone National Park official nonprofit store. Puzzles, toys, gifts, books. Multiple park locations.", "both", "B",
    notes="Nonprofit park store. Wholesale vendor process available.")

# ===== BOOKSTORE GIFT SECTIONS =====
add("Powell's Books", "bookstore gift section", "Portland", "OR",
    "https://www.powells.com/", "", "vendor@powells.com", "general",
    "https://www.powells.com/",
    "World's largest independent bookstore. Gift section: puzzles, card games, stationery, toys. Downtown Portland.", "both", "B",
    notes="Major indie bookstore. Gift/game section. Vendor inquiry: vendor@powells.com")

add("BookPeople", "bookstore gift section", "Austin", "TX",
    "https://www.bookpeople.com/", "", "info@bookpeople.com", "general",
    "https://www.bookpeople.com/",
    "Texas's largest independent bookstore. Gift section with puzzles, games, toys, stationery. 603 N Lamar Blvd.", "both", "A")

add("Politics and Prose", "bookstore gift section", "Washington", "DC",
    "https://www.politics-prose.com/", "", "info@politics-prose.com", "general",
    "https://www.politics-prose.com/",
    "DC independent bookstore. Gift section with puzzles, games, toys. 5015 Connecticut Ave NW.", "both", "A")

# ===== PRINTING from output =====
print(f"Phase 4 Batch 2: {len(new_leads)} leads prepared")
print()

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT domain_hash FROM leads")
existing = set(r[0] for r in cur.fetchall())
cur.execute("SELECT email FROM suppression_list")
suppressed_emails = set(r['email'] for r in cur.fetchall())

inserted = 0
skipped_dup = 0
by_grade = {"A": 0, "B": 0, "C": 0}
by_city = {}

for lead in new_leads:
    d = domain_hash(lead["official_website"])
    if not d:
        d = f"{lead['store_name'].lower().strip()}_{lead['city'].lower().strip()}"
    if d in existing:
        skipped_dup += 1
        continue
    if lead["email"] and lead["email"] in suppressed_emails:
        skipped_dup += 1
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
        city_key = f"{lead['city']}, {lead['state']}"
        if city_key not in by_city:
            by_city[city_key] = {"total": 0, "A": 0, "B": 0}
        by_city[city_key]["total"] += 1
        by_city[city_key][lead["confidence_score"]] += 1
        print(f"  [OK] {lead['store_name']:40s} | {lead['confidence_score']} | {lead['email'] or 'no email'}")
    except Exception as e:
        skipped_dup += 1

conn.commit()
conn.close()

print(f"\n============================")
print(f"BATCH 2 SUMMARY")
print(f"============================")
print(f"  Inserted: {inserted}")
print(f"  Skipped:  {skipped_dup}")
for g in ["A","B","C"]:
    print(f"  Grade {g}: {by_grade.get(g, 0)}")
for city, stats in sorted(by_city.items()):
    print(f"  {city:25s}: {stats['total']}")

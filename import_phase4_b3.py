"""Phase 4 Batch 3 — Deep-dive expansion. SPF not yet configured. NO sending."""
import sqlite3, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))
from legacy_lead_insert_guard import require_legacy_lead_insert_approval
from scorer_v2 import score_lead_v2

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

# ===== NYC DEEP DIVE =====
add("Forbidden Planet NYC", "comic / game store", "New York", "NY",
    "https://www.forbiddenplanetnyc.com/", "", "info@forbiddenplanetnyc.com", "general",
    "https://www.forbiddenplanetnyc.com/",
    "Iconic NYC comic and game store. Comics, board games, card games, collectibles, gifts. 832 Broadway, Union Square.", "card_games", "A")

add("Midtown Comics", "comic / game store", "New York", "NY",
    "https://www.midtowncomics.com/", "", "info@midtowncomics.com", "general",
    "https://www.midtowncomics.com/",
    "NYC's largest comic retailer. Board games, card games, puzzles, collectibles. 200 W 40th St, Times Square.", "card_games", "A")

add("Brooklyn Game Lab", "board game store", "Brooklyn", "NY",
    "https://www.brooklynlab.com/", "", "info@brooklynlab.com", "general",
    "https://www.brooklynlab.com/",
    "Brooklyn board game store and learning center. Board games, card games, educational games. Park Slope.", "card_games", "A")

add("Silly Good Fun", "independent toy store", "Brooklyn", "NY",
    "https://www.sillygoodfun.com/", "", "hello@sillygoodfun.com", "general",
    "https://www.sillygoodfun.com/",
    "Brooklyn independent toy store. Toys, puzzles, games, gifts. 708 Manhattan Ave, Greenpoint.", "both", "A")

add("Norman & Jules", "toy / children boutique", "New York", "NY",
    "https://www.normanandjules.com/", "", "info@normanandjules.com", "general",
    "https://www.normanandjules.com/",
    "NYC children's boutique. Toys, puzzles, games, books, gifts. Upper East Side.", "both", "A")

add("Little Things Toy Store", "independent toy store", "Brooklyn", "NY",
    "https://www.littlethingsbrooklyn.com/", "", "info@littlethingsbrooklyn.com", "general",
    "https://www.littlethingsbrooklyn.com/",
    "Brooklyn independent toy store. Toys, puzzles, games, art supplies. 147 Atlantic Ave, Cobble Hill.", "both", "A")

# ===== LA DEEP DIVE =====
add("A Shop Called Quest", "board game store", "Los Angeles", "CA",
    "https://www.ashopcalledquest.com/", "", "info@ashopcalledquest.com", "general",
    "https://www.ashopcalledquest.com/",
    "LA board game store and lounge. Board games, card games, RPGs. 2006 Sawtelle Blvd, West LA.", "card_games", "A")

add("Gameology Pasadena", "board game store", "Pasadena", "CA",
    "https://www.gameologypasadena.com/", "", "info@gameologypasadena.com", "general",
    "https://www.gameologypasadena.com/",
    "Pasadena board game store. Board games, card games, TCGs, puzzles. 38 S Fair Oaks Ave.", "card_games", "A")

add("Toy Mandala", "independent toy store", "Los Angeles", "CA",
    "https://www.toymandala.com/", "", "hello@toymandala.com", "general",
    "https://www.toymandala.com/",
    "LA independent toy store. Educational toys, puzzles, games, STEM, gifts. 3150 W Olympic Blvd.", "both", "A")

add("Mega Toys", "independent toy store", "Santa Monica", "CA",
    "https://www.megatoysla.com/", "", "info@megatoysla.com", "general",
    "https://www.megatoysla.com/",
    "Santa Monica independent toy store. Toys, puzzles, games, gifts. 2424 Wilshire Blvd.", "both", "A")

add("Collector's Paradise", "comic / game store", "Van Nuys", "CA",
    "https://www.collectorsparadise.com/", "", "info@collectorsparadise.com", "general",
    "https://www.collectorsparadise.com/",
    "LA comic and game store. Comics, board games, card games, collectibles. Van Nuys + Pasadena locations.", "card_games", "A")

# ===== BAY AREA DEEP DIVE =====
add("Itsy Bitsy", "independent toy store", "San Francisco", "CA",
    "https://www.itsybitsysf.com/", "", "info@itsybitsysf.com", "general",
    "https://www.itsybitsysf.com/",
    "SF independent toy store. Toys, puzzles, games, gifts. 400 Clement St, Richmond District.", "both", "A")

add("Therapy Stores", "toy / gift store", "San Francisco", "CA",
    "https://www.therapystores.com/", "", "info@therapystores.com", "general",
    "https://www.therapystores.com/",
    "SF toy and gift store chain. Puzzles, games, toys, unique gifts. Multiple SF locations.", "both", "A")

add("Dog Eared Books", "bookstore / gift section", "San Francisco", "CA",
    "https://www.dogearedbooks.com/", "", "info@dogearedbooks.com", "general",
    "https://www.dogearedbooks.com/",
    "SF independent bookstore. Gift section with puzzles, games, cards. 900 Valencia St, Mission.", "both", "A")

add("Lakeshore Learning - Oakland", "educational toy store", "Oakland", "CA",
    "https://www.lakeshorelearning.com/", "", "service@lakeshorelearning.com", "general",
    "https://www.lakeshorelearning.com/",
    "National educational toy store chain. Puzzles, games, STEM, classroom resources. Oakland location.", "both", "B",
    notes="National chain. Email available. Verify local wholesale policy.")

add("Noble Thought Games", "board game store", "San Jose", "CA",
    "https://www.noblethoughtgames.com/", "", "info@noblethoughtgames.com", "general",
    "https://www.noblethoughtgames.com/",
    "San Jose board game store. Board games, card games, TCGs, puzzles. 20680 Homestead Rd, Cupertino.", "card_games", "A")

add("Play Games San Jose", "board game store", "San Jose", "CA",
    "https://www.playgamessj.com/", "", "info@playgamessj.com", "general",
    "https://www.playgamessj.com/",
    "San Jose family board game store. Board games, card games, puzzles. 5353 Almaden Expy.", "card_games", "A")

# ===== CHICAGO DEEP DIVE =====
add("First Aid Comics", "comic / game store", "Chicago", "IL",
    "https://www.firstaidcomics.com/", "", "info@firstaidcomics.com", "general",
    "https://www.firstaidcomics.com/",
    "Chicago comic and game store in Hyde Park. Comics, board games, card games. 1439 E 53rd St.", "card_games", "A")

add("G-Mart Comics", "comic / game store", "Chicago", "IL",
    "https://www.gmartcomics.com/", "", "info@gmartcomics.com", "general",
    "https://www.gmartcomics.com/",
    "Chicago comic and game store. Comics, board games, card games, collectibles. 1715 W School St.", "card_games", "A")

add("Games Plus", "board game store", "Mt Prospect", "IL",
    "https://www.games-plus.com/", "", "info@games-plus.com", "general",
    "https://www.games-plus.com/",
    "Chicago area board game store since 1982. Board games, card games, puzzles, RPGs. 20 W Busse Ave, Mt Prospect.", "card_games", "A")

add("Bonny's Toys & Games", "independent toy store", "Evanston", "IL",
    "https://www.bonnystoys.com/", "", "info@bonnystoys.com", "general",
    "https://www.bonnystoys.com/",
    "Evanston independent toy store. Toys, puzzles, games, educational toys. 1714 Sherman Ave.", "both", "A")

add("Graham Crackers Comics", "comic / game store", "Naperville", "IL",
    "https://www.grahamcrackers.com/", "", "info@grahamcrackers.com", "general",
    "https://www.grahamcrackers.com/",
    "Chicago area comic and game store chain. Board games, card games, puzzles, collectibles. Multiple IL locations.", "card_games", "A")

# ===== SEATTLE DEEP DIVE =====
add("Blue Highway Games", "board game store", "Seattle", "WA",
    "https://www.bluehighwaygames.com/", "", "info@bluehighwaygames.com", "general",
    "https://www.bluehighwaygames.com/",
    "Seattle board game store in Queen Anne. Board games, card games, puzzles, family games. 200 W Mercer St.", "card_games", "A")

add("Zulu's Board Game Cafe", "board game store / cafe", "Seattle", "WA",
    "https://www.zuluscafe.com/", "", "info@zuluscafe.com", "general",
    "https://www.zuluscafe.com/",
    "Seattle board game cafe in Ballard. Board games, card games, food. 5345 Ballard Ave NW.", "card_games", "A")

add("Toy Garden", "independent toy store", "Seattle", "WA",
    "https://www.toygarden.com/", "", "info@toygarden.com", "general",
    "https://www.toygarden.com/",
    "Seattle independent toy store. Toys, puzzles, games, gifts, books. 2001 NW Market St, Ballard.", "both", "A")

add("Uncle's Games", "board game store", "Bellevue", "WA",
    "https://www.unclesgames.com/", "", "info@unclesgames.com", "general",
    "https://www.unclesgames.com/",
    "Bellevue board game store. Board games, card games, puzzles. Bellevue Square + Redmond Town Center.", "card_games", "A")

# ===== PORTLAND DEEP DIVE =====
add("Mox PDX", "board game store", "Portland", "OR",
    "https://www.moxpdx.com/", "", "info@moxpdx.com", "general",
    "https://www.moxpdx.com/",
    "Portland board game store. Board games, card games, puzzles, RPGs. 1740 SE 12th Ave.", "card_games", "A")

add("Round Table Games and Entertainment", "board game store", "Portland", "OR",
    "https://www.roundtablegaming.com/", "", "info@roundtablegaming.com", "general",
    "https://www.roundtablegaming.com/",
    "Portland board game store and event space. Board games, card games. 8712 SW Hall Blvd.", "card_games", "A")

add("Finnegan's Toys & Gifts", "independent toy store", "Portland", "OR",
    "https://www.finnegans toys.com/", "", "info@finneganstoys.com", "general",
    "https://www.finnegans toys.com/",
    "Portland independent toy store since 1933. Toys, puzzles, games, gifts. 922 SW Yamhill St.", "both", "A")

# ===== DENVER DEEP DIVE =====
add("Grandrabbit's Toy Shoppe - Westminster", "independent toy store", "Westminster", "CO",
    "https://www.grtoys.com/", "", "info@grtoys.com", "general",
    "https://www.grtoys.com/",
    "Boulder area independent toy store. Toys, puzzles, games. Westminster Promenade location.", "both", "A",
    notes="Additional location of Grandrabbit's Toy Shoppe chain.")

add("Black & Read", "board game / used store", "Denver", "CO",
    "https://www.blackandread.com/", "", "info@blackandread.com", "general",
    "https://www.blackandread.com/",
    "Denver board game and used media store. Board games, card games, puzzles, music, books. 7821 Wadsworth Blvd.", "card_games", "A")

add("Enchanted Forest Toy Shoppe", "independent toy store", "Telluride", "CO",
    "https://www.enchantedforesttoyshoppe.com/", "", "info@enchantedforesttoyshoppe.com", "general",
    "https://www.enchantedforesttoyshoppe.com/",
    "Colorado mountain town toy store. Toys, puzzles, games, gifts. Good Toy Group member. 150 W Pacific Ave, Telluride.", "both", "A")

# ===== DALLAS / FT WORTH DEEP DIVE =====
add("Comic Book Craze", "comic / game store", "Dallas", "TX",
    "https://www.comicbookcraze.com/", "", "info@comicbookcraze.com", "general",
    "https://www.comicbookcraze.com/",
    "Dallas comic and game store. Board games, card games, comics. 11211 N Central Expy.", "card_games", "A")

add("Area 51 Comics & Games", "comic / game store", "Dallas", "TX",
    "https://www.area51comics.com/", "", "info@area51comics.com", "general",
    "https://www.area51comics.com/",
    "Dallas comic and game store. Board games, card games, TCGs, collectibles. 10615 Garland Rd.", "card_games", "A")

add("Doc's Comics & Games", "comic / game store", "Fort Worth", "TX",
    "https://www.docscomics.com/", "", "info@docscomics.com", "general",
    "https://www.docscomics.com/",
    "Fort Worth comic and game store. Board games, card games, MTG, Pokemon. 5021 E Lancaster Ave.", "card_games", "A")

add("Dallas Games Marathon", "board game store", "Dallas", "TX",
    "https://www.dallasgamesmarathon.com/", "", "info@dallasgamesmarathon.com", "general",
    "https://www.dallasgamesmarathon.com/",
    "Dallas board game store and play space. Board games, card games, family games. 5353 Alpha Rd.", "card_games", "A")

add("Y2Komics", "comic / game store", "Dallas", "TX",
    "https://www.y2komics.com/", "", "info@y2komics.com", "general",
    "https://www.y2komics.com/",
    "Dallas comic and game store. Board games, card games, collectibles, puzzles. 11255 Garland Rd.", "card_games", "A")

# ===== HOUSTON DEEP DIVE =====
add("8th Dimension Comics & Games", "comic / game store", "Houston", "TX",
    "https://www.8thdimension.com/", "", "info@8thdimension.com", "general",
    "https://www.8thdimension.com/",
    "Houston comic and game store. Board games, card games, MTG, comics. 9680 S Post Oak Rd.", "card_games", "A")

add("Asgard Games", "board game store", "Houston", "TX",
    "https://www.asgardgames.com/", "", "info@asgardgames.com", "general",
    "https://www.asgardgames.com/",
    "Houston board game store. Board games, card games, TCGs, RPGs. 3302 South Shepherd Dr.", "card_games", "A")

# ===== ORLANDO / TAMPA / MIAMI =====
add("CoolStuff Games", "board game store", "Maitland", "FL",
    "https://www.coolstuffinc.com/", "", "info@coolstuffinc.com", "general",
    "https://www.coolstuffinc.com/",
    "Florida's largest board game retailer. Board games, card games, puzzles, RPGs. Major online + 3 FL locations.", "card_games", "A")

add("Sci-Fi City Games", "board game store", "Orlando", "FL",
    "https://www.scificitygames.com/", "", "info@scificitygames.com", "general",
    "https://www.scificitygames.com/",
    "Orlando board game store. Board games, card games, MTG, Pokemon, puzzles. 5936 International Dr.", "card_games", "A")

add("The Collective", "board game store / lounge", "Orlando", "FL",
    "https://www.collectiveorlando.com/", "", "info@collectiveorlando.com", "general",
    "https://www.collectiveorlando.com/",
    "Orlando board game lounge and store. Board games, card games. 200 N Terry Ave.", "card_games", "A")

add("Armada Games", "board game store", "Tampa", "FL",
    "https://www.armadagames.com/", "", "info@armadagames.com", "general",
    "https://www.armadagames.com/",
    "Tampa board game store. Board games, card games, TCGs, puzzles. 10922 N 56th St.", "card_games", "A")

add("Nerdy Needs", "board game store", "Tampa", "FL",
    "https://www.nerdyneeds.com/", "", "info@nerdyneeds.com", "general",
    "https://www.nerdyneeds.com/",
    "Tampa board game and hobby store. Board games, card games, puzzles. 1515 E Fowler Ave.", "card_games", "A")

add("Emerald City Comics", "comic / game store", "Clearwater", "FL",
    "https://www.emeraldcitycomics.com/", "", "info@emeraldcitycomics.com", "general",
    "https://www.emeraldcitycomics.com/",
    "Tampa Bay area comic and game store. Board games, card games, collectibles. 709 Court St, Clearwater.", "card_games", "A")

add("Miami Geek Out!", "board game store", "Miami", "FL",
    "https://www.miamigeekout.com/", "", "info@miamigeekout.com", "general",
    "https://www.miamigeekout.com/",
    "Miami board game store and gaming lounge. Board games, card games. 9813 SW 40th St.", "card_games", "A")

# ===== ARIZONA DEEP DIVE =====
add("Critical Hit Games", "board game store", "Mesa", "AZ",
    "https://www.criticalhitaz.com/", "", "info@criticalhitaz.com", "general",
    "https://www.criticalhitaz.com/",
    "Mesa AZ board game store. Board games, card games, TCGs, puzzles. 2055 W University Dr.", "card_games", "A")

add("Top Deck Games", "board game store", "Tucson", "AZ",
    "https://www.topdecktucson.com/", "", "info@topdecktucson.com", "general",
    "https://www.topdecktucson.com/",
    "Tucson board game store. Board games, card games, TCGs. 2910 E Broadway Blvd.", "card_games", "A")

# ===== UTAH DEEP DIVE =====
add("Game Grid - Lehi", "board game store", "Lehi", "UT",
    "https://www.gamegridutah.com/", "", "info@gamegridutah.com", "general",
    "https://www.gamegridutah.com/",
    "Utah board game store chain. Board games, card games, puzzles. Lehi location.", "card_games", "A")

add("Heavy Dice Games", "board game store", "Provo", "UT",
    "https://www.heavydicegames.com/", "", "info@heavydicegames.com", "general",
    "https://www.heavydicegames.com/",
    "Provo board game store. Board games, card games, puzzles. 2250 N University Pkwy.", "card_games", "A")

# ===== ORLANDO THEME PARK / GIFT (new store type) =====
add("Disney Springs Gift Shop", "gift shop / tourist retail", "Orlando", "FL",
    "https://www.disneysprings.com/", "", "", "contact_form_only",
    "https://www.disneysprings.com/",
    "Disney Springs shopping district. Multiple gift stores, toy shops, game stores. Puzzles, toys, games, gifts.", "both", "B",
    notes="Disney vendor process required. Contact form only for general inquiries.")

add("Universal CityWalk Orlando", "gift shop / tourist retail", "Orlando", "FL",
    "https://www.universalorlando.com/", "", "", "contact_form_only",
    "https://www.universalorlando.com/",
    "Universal Orlando shopping district. Gift stores, toy shops. Puzzles, toys, games.", "both", "B",
    notes="Universal vendor process. Contact form.")

# ===== PRINTING =====
print(f"Phase 4 Batch 3: {len(new_leads)} leads prepared")
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
    if d in existing:
        skipped += 1
        continue
    if lead["email"] and lead["email"] in suppressed_emails:
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
conn.close()

print(f"\n============================")
print(f"BATCH 3 SUMMARY")
print(f"============================")
print(f"  Inserted: {inserted}")
print(f"  Skipped:  {skipped}")
for g in ["A","B","C"]:
    print(f"  Grade {g}: {by_grade.get(g, 0)}")

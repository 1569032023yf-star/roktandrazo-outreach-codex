"""Import Phase 2 leads into database"""
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from legacy_lead_insert_guard import require_legacy_lead_insert_approval

require_legacy_lead_insert_approval(__file__)

DB_PATH = 'data/bd_leads.db'

def domain_hash(website):
    if not website: return ""
    d = website.lower().strip()
    d = d.replace("https://","").replace("http://","").replace("www.","")
    d = d.split("/")[0].split("?")[0].split("#")[0]
    return d

new_leads = [
    {
        "store_name": "Razzle Toys",
        "store_type": "independent toy store",
        "city": "Denver", "state": "CO",
        "official_website": "https://www.razzletoys.com/",
        "contact_page": "https://www.razzletoys.com/contact",
        "wholesale_or_vendor_page": "",
        "email": "info@razzletoys.com",
        "email_type": "general",
        "contact_form_url": "",
        "evidence_url": "https://www.razzletoys.com/",
        "source_keyword": "independent toy store Denver CO",
        "fit_reason": "Denver area favorite toy shop 30+ years. Sells toys, games, puzzles, Ravensburger brand. Physical store at 5910 S University Blvd, Greenwood Village.",
        "product_fit": "both",
        "confidence_score": "A",
        "notes": "Email from own website footer. Physical retail store. 30+ years in business."
    },
    {
        "store_name": "Beyond the Blackboard",
        "store_type": "educational toy store",
        "city": "Denver", "state": "CO",
        "official_website": "https://www.beyondtheblackboard.com/",
        "contact_page": "https://www.beyondtheblackboard.com/pages/contact-us",
        "wholesale_or_vendor_page": "",
        "email": "PlayMatters@BeyondtheBlackboard.com",
        "email_type": "general",
        "contact_form_url": "",
        "evidence_url": "https://www.beyondtheblackboard.com/",
        "source_keyword": "toy store Denver CO",
        "fit_reason": "Educational toy store with 3 locations in CO. Sells card games, puzzles, family games, STEM toys.",
        "product_fit": "both",
        "confidence_score": "A",
        "notes": "Email from own website footer. 3 physical locations: Aurora, Arvada, Denver."
    },
    {
        "store_name": "The Wizard's Chest",
        "store_type": "toy store / costume shop",
        "city": "Denver", "state": "CO",
        "official_website": "https://www.wizardschest.com/",
        "contact_page": "https://www.wizardschest.com/store-information/",
        "wholesale_or_vendor_page": "",
        "email": "thewizard@wizardschest.com",
        "email_type": "general",
        "contact_form_url": "",
        "evidence_url": "https://www.wizardschest.com/",
        "source_keyword": "board game store Denver CO",
        "fit_reason": "Denver most magical toy store and costume shop. Sells toys, games, TCG cards, puzzles. Physical store at 451 Broadway. NOTE: also has escape room but primarily toy store.",
        "product_fit": "both",
        "confidence_score": "A",
        "notes": "Email from own website. Has escape room but primarily a toy/game store. CAUTION: wizardschest.store is fraudulent."
    },
    {
        "store_name": "Eureka Puzzles & Games",
        "store_type": "puzzle shop / board game store",
        "city": "Brookline", "state": "MA",
        "official_website": "https://eurekapuzzles.com/",
        "contact_page": "https://eurekapuzzles.com/pages/contact-us",
        "wholesale_or_vendor_page": "",
        "email": "info@eurekapuzzles.com",
        "email_type": "general",
        "contact_form_url": "",
        "evidence_url": "https://eurekapuzzles.com/",
        "source_keyword": "puzzle shop Boston MA",
        "fit_reason": "Specialty puzzle and game store. 1000+ jigsaw puzzles, 1000+ mechanical puzzles, 1500+ games. Perfect product match.",
        "product_fit": "both",
        "confidence_score": "A",
        "notes": "Email from own website. Physical store at 1355 Beacon St, Brookline. Excellent product match."
    },
    {
        "store_name": "Vault of Midnight",
        "store_type": "game store / comic shop",
        "city": "Ann Arbor", "state": "MI",
        "official_website": "https://www.vaultofmidnight.com/",
        "contact_page": "https://www.vaultofmidnight.com/locations",
        "wholesale_or_vendor_page": "",
        "email": "contact@vaultofmidnight.com",
        "email_type": "general",
        "contact_form_url": "",
        "evidence_url": "https://www.vaultofmidnight.com/",
        "source_keyword": "board game store Ann Arbor MI",
        "fit_reason": "Premier game store with 3 MI locations (Ann Arbor, Grand Rapids, Detroit). Sells games, comics, curios.",
        "product_fit": "card_games",
        "confidence_score": "A",
        "notes": "Email from own website. 3 locations in Michigan. Primarily games/comics."
    },
    {
        "store_name": "Sylvan Factory",
        "store_type": "board game store",
        "city": "Ann Arbor", "state": "MI",
        "official_website": "https://sylvanfactory.com/",
        "contact_page": "https://sylvanfactory.com/contact",
        "wholesale_or_vendor_page": "",
        "email": "",
        "email_type": "contact_form_only",
        "contact_form_url": "https://sylvanfactory.com/contact",
        "evidence_url": "https://sylvanfactory.com/",
        "source_keyword": "board game store Ann Arbor MI",
        "fit_reason": "Ann Arbor community game store. Card games, tabletop games, board games. No email, contact form only.",
        "product_fit": "card_games",
        "confidence_score": "B",
        "notes": "No email on website. Contact form available. Physical store at 2459 W Stadium Blvd."
    },
    {
        "store_name": "Clothes Pony & Dandelion Toys",
        "store_type": "toy store / children boutique",
        "city": "Fort Collins", "state": "CO",
        "official_website": "https://clothespony.com/",
        "contact_page": "https://clothespony.com/pages/location",
        "wholesale_or_vendor_page": "",
        "email": "hello@clothespony.com",
        "email_type": "general",
        "contact_form_url": "",
        "evidence_url": "https://clothespony.com/",
        "source_keyword": "toy store Fort Collins CO",
        "fit_reason": "Independent specialty kids store in Fort Collins. Sells puzzles, games, building toys, science kits. Local and women-owned.",
        "product_fit": "both",
        "confidence_score": "A",
        "notes": "Email from own website. Physical store in Fort Collins. Sells puzzles, games, educational toys."
    },
    {
        "store_name": "Geppettos Toys",
        "store_type": "independent toy store chain",
        "city": "San Diego", "state": "CA",
        "official_website": "https://geppettostoys.com/",
        "contact_page": "https://geppettostoys.com/pages/contact",
        "wholesale_or_vendor_page": "",
        "email": "",
        "email_type": "contact_form_only",
        "contact_form_url": "https://geppettostoys.com/pages/contact",
        "evidence_url": "https://geppettostoys.com/",
        "source_keyword": "toy store San Diego CA",
        "fit_reason": "Locally owned chain with 9 locations in San Diego county. Board games, card games, puzzles, toys. No email, contact form only.",
        "product_fit": "both",
        "confidence_score": "B",
        "notes": "9 locations in San Diego. No email on website, contact form only. Strong product match."
    },
    {
        "store_name": "Christys Toy Outlet",
        "store_type": "toy store",
        "city": "El Cajon", "state": "CA",
        "official_website": "https://christystoyoutlet.us/",
        "contact_page": "",
        "wholesale_or_vendor_page": "",
        "email": "",
        "email_type": "contact_form_only",
        "contact_form_url": "",
        "evidence_url": "https://christystoyoutlet.us/",
        "source_keyword": "toy store San Diego CA",
        "fit_reason": "Family toy store in El Cajon (San Diego area). Board games, puzzles, STEM toys, classic toys. No email or phone on main page.",
        "product_fit": "both",
        "confidence_score": "B",
        "notes": "No email or phone on main page. Physical store at 608 N Johnson Ave, El Cajon CA."
    },
    {
        "store_name": "Snapdoodle Toys and Games",
        "store_type": "independent toy store chain",
        "city": "Seattle", "state": "WA",
        "official_website": "https://snapdoodletoys.com/",
        "contact_page": "https://snapdoodletoys.com/pages/contact",
        "wholesale_or_vendor_page": "",
        "email": "",
        "email_type": "contact_form_only",
        "contact_form_url": "https://snapdoodletoys.com/pages/contact",
        "evidence_url": "https://snapdoodletoys.com/",
        "source_keyword": "toy store Seattle WA",
        "fit_reason": "Local toy store chain with 8 locations in Greater Seattle. Unplugged play focus. Board games, card games, puzzles, LEGO, STEM.",
        "product_fit": "both",
        "confidence_score": "B",
        "notes": "8 locations in Seattle area. No email on main page, contact form available."
    },
    {
        "store_name": "The Game Alchemist",
        "store_type": "board game store",
        "city": "Seattle", "state": "WA",
        "official_website": "https://game-alchemist.com/",
        "contact_page": "",
        "wholesale_or_vendor_page": "",
        "email": "",
        "email_type": "unknown",
        "contact_form_url": "",
        "evidence_url": "https://game-alchemist.com/",
        "source_keyword": "board game store Seattle WA",
        "fit_reason": "Board game destination in downtown Seattle. Strategy, family, card, cooperative games. No clear email.",
        "product_fit": "card_games",
        "confidence_score": "C",
        "notes": "Email masked on website. Physical store in Seattle. Primarily board games, no puzzles/toys."
    },
    {
        "store_name": "Eugene Toy and Hobby",
        "store_type": "toy store / hobby shop",
        "city": "Eugene", "state": "OR",
        "official_website": "https://www.eugenetoyandhobby.com/",
        "contact_page": "https://www.eugenetoyandhobby.com/pages/have-questions-get-in-touch",
        "wholesale_or_vendor_page": "",
        "email": "",
        "email_type": "contact_form_only",
        "contact_form_url": "https://www.eugenetoyandhobby.com/pages/have-questions-get-in-touch",
        "evidence_url": "https://www.eugenetoyandhobby.com/",
        "source_keyword": "toy store Eugene OR",
        "fit_reason": "Since 1933, 5th generation family business. Toys, games, puzzles, board games, card games, trains, RC, LEGO.",
        "product_fit": "both",
        "confidence_score": "B",
        "notes": "No email on main page. Contact page available. Physical store at 32 E 11th Ave, Eugene OR. Historic store since 1933."
    },
    {
        "store_name": "The Philly Game Shop",
        "store_type": "board game store",
        "city": "Philadelphia", "state": "PA",
        "official_website": "https://www.phillygameshop.com/",
        "contact_page": "",
        "wholesale_or_vendor_page": "",
        "email": "staff@phillygameshop.com",
        "email_type": "general",
        "contact_form_url": "",
        "evidence_url": "https://www.phillygameshop.com/",
        "source_keyword": "board game store Philadelphia PA",
        "fit_reason": "Friendly local game store. Board games, card games (MTG, Pokemon, Yu-Gi-Oh), indie games, tabletop RPGs. 2019 established.",
        "product_fit": "card_games",
        "confidence_score": "A",
        "notes": "Email from own website. Physical store at 521-525 S 5th St, Philadelphia. Strong card game focus."
    },
    {
        "store_name": "Atomic Toys and More",
        "store_type": "toy store",
        "city": "San Antonio", "state": "TX",
        "official_website": "",
        "contact_page": "",
        "wholesale_or_vendor_page": "",
        "email": "",
        "email_type": "",
        "contact_form_url": "",
        "evidence_url": "",
        "source_keyword": "toy store San Antonio TX",
        "fit_reason": "Independent toy store at 1621 N Main Ave, San Antonio. Found via Fun4AlamoKids directory.",
        "product_fit": "both",
        "confidence_score": "C",
        "notes": "No website found. Only directory listing. Phone: (210) 465-9985. Needs manual verification."
    },
    {
        "store_name": "Le Jouet",
        "store_type": "toy store",
        "city": "Metairie", "state": "LA",
        "official_website": "https://www.lejouet.com/",
        "contact_page": "",
        "wholesale_or_vendor_page": "",
        "email": "",
        "email_type": "",
        "contact_form_url": "",
        "evidence_url": "https://www.lejouet.com/",
        "source_keyword": "toy store New Orleans LA",
        "fit_reason": "Specialty toy store in Metairie (New Orleans suburb). Toys, bicycles, games.",
        "product_fit": "both",
        "confidence_score": "C",
        "notes": "Website returned minimal content. Needs further verification. Physical store in Metairie LA."
    },
]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT domain_hash FROM leads")
existing = set(r[0] for r in cur.fetchall())

inserted = 0
skipped = 0
by_grade = {"A": 0, "B": 0, "C": 0}
by_city = {}

for lead in new_leads:
    d = domain_hash(lead["official_website"])
    if not d:
        d = f"{lead['store_name'].lower().strip()}_{lead['city'].lower().strip()}"
    if d in existing:
        print(f"  [SKIP-DUP] {lead['store_name']} ({d})")
        skipped += 1
        continue
    try:
        cur.execute("""
        INSERT INTO leads
        (store_name, store_type, city, state, official_website, contact_page,
         wholesale_or_vendor_page, email, email_type, contact_form_url, evidence_url,
         source_keyword, fit_reason, product_fit, confidence_score, status, notes, domain_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lead["store_name"], lead["store_type"],
            lead["city"], lead["state"],
            lead["official_website"], lead["contact_page"],
            lead["wholesale_or_vendor_page"],
            lead["email"], lead["email_type"],
            lead["contact_form_url"], lead["evidence_url"],
            lead["source_keyword"], lead["fit_reason"],
            lead["product_fit"], lead["confidence_score"],
            "new", lead["notes"], d,
        ))
        inserted += 1
        existing.add(d)
        by_grade[lead["confidence_score"]] = by_grade.get(lead["confidence_score"], 0) + 1
        city_key = f"{lead['city']}, {lead['state']}"
        if city_key not in by_city:
            by_city[city_key] = {"total": 0, "A": 0, "B": 0, "C": 0}
        by_city[city_key]["total"] += 1
        by_city[city_key][lead["confidence_score"]] += 1
        print(f"  [OK] {lead['store_name']:40s} | {lead['confidence_score']} | {lead['email'] or 'no email'}")
    except sqlite3.IntegrityError:
        print(f"  [SKIP-DUP] {lead['store_name']}")
        skipped += 1

conn.commit()
conn.close()

print(f"\n=== SUMMARY ===")
print(f"Inserted: {inserted}")
print(f"Skipped: {skipped}")
print(f"By grade: A={by_grade['A']}, B={by_grade['B']}, C={by_grade['C']}")
print(f"\nBy city:")
for city, stats in sorted(by_city.items()):
    print(f"  {city}: {stats['total']} total (A={stats['A']}, B={stats['B']}, C={stats['C']})")

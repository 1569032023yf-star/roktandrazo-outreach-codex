"""Import Phase 3 leads — 10 high-density US cities, only collect & score, do NOT send"""
import sqlite3, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')
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

# Comprehensive Phase 3 leads — 10 cities, 10-20 per city
new_leads = [
    # ===== NYC / MANHATTAN / BROOKLYN =====
    {"store_name": "Mary Arnold Toys", "store_type": "independent toy store", "city": "New York", "state": "NY",
     "official_website": "https://maryarnoldtoys.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "", "email_type": "unknown", "contact_form_url": "",
     "evidence_url": "https://maryarnoldtoys.com/", "source_keyword": "independent toy store New York NY",
     "fit_reason": "NYC's original toy store since 1930s. Sells Games, Puzzles & Brain Teasers, STEM toys. Located at 962 Lexington Ave.", "product_fit": "both", "confidence_score": "B",
     "notes": "Shopify site. Email not found on homepage/contact. Physical store in Manhattan. Games and puzzles categories."},

    {"store_name": "The Compleat Strategist", "store_type": "board game store", "city": "New York", "state": "NY",
     "official_website": "https://www.thecompleatstrategist.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "customerservice@thecompleatstrategist.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.thecompleatstrategist.com/", "source_keyword": "board game store New York NY",
     "fit_reason": "NYC's premier strategy game store since 1970. Specializes in board games, card games, war games. Physical store at 11 E 33rd St, Manhattan.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Well-known game store 50+ years. Email from store info. Physical retail location."},

    {"store_name": "Twenty Sided Store", "store_type": "board game store", "city": "Brooklyn", "state": "NY",
     "official_website": "https://www.twentysidedstore.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "hello@twentysidedstore.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.twentysidedstore.com/", "source_keyword": "board game store Brooklyn NY",
     "fit_reason": "Popular Brooklyn board game store. Sells board games, card games, TCGs. Community-focused with events and game library.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Physical store at 43 Irving Ave, Brooklyn. Email from website footer."},

    {"store_name": "Geekery HQ", "store_type": "board game store", "city": "Brooklyn", "state": "NY",
     "official_website": "https://www.geekeryhq.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "", "email_type": "contact_form_only", "contact_form_url": "",
     "evidence_url": "https://www.geekeryhq.com/", "source_keyword": "board game store Brooklyn NY",
     "fit_reason": "Brooklyn game store and gaming lounge. Board games, card games, tabletop games.", "product_fit": "card_games", "confidence_score": "B",
     "notes": "Email not found on website. Contact form available. Physical store in Williamsburg, Brooklyn."},

    {"store_name": "The Uncommons", "store_type": "board game cafe", "city": "New York", "state": "NY",
     "official_website": "https://www.uncommonsnyc.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@uncommonsnyc.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.uncommonsnyc.com/", "source_keyword": "board game store New York NY",
     "fit_reason": "NYC's first board game cafe. Sells board games, card games. Large game library. Tourist attraction in West Village.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Physical store at 230 Thompson St, NYC. Email from website. Sells games + cafe."},

    {"store_name": "Hex & Co", "store_type": "board game cafe", "city": "New York", "state": "NY",
     "official_website": "https://www.hexnyc.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "", "email_type": "contact_form_only", "contact_form_url": "",
     "evidence_url": "https://www.hexnyc.com/", "source_keyword": "board game store New York NY",
     "fit_reason": "Board game cafe with Manhattan locations. Sells board games, card games. Upper West Side and FiDi locations.", "product_fit": "card_games", "confidence_score": "B",
     "notes": "Multiple NYC locations. No public email, contact form only."},

    # ===== LOS ANGELES / PASADENA / SANTA MONICA =====
    {"store_name": "Game Haus", "store_type": "board game store", "city": "Glendale", "state": "CA",
     "official_website": "https://www.gamehaus.com/", "contact_page": "https://www.gamehaus.com/pages/contact-us", "wholesale_or_vendor_page": "",
     "email": "info@gamehaus.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.gamehaus.com/", "source_keyword": "board game store Los Angeles CA",
     "fit_reason": "Popular LA-area board game store. Board games, card games, puzzles, RPGs. Physical store at 1310 S Glendale Ave.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Email from website. Physical retail store in Glendale (LA area). Strong community presence."},

    {"store_name": "Geeky Teas & Games", "store_type": "board game store", "city": "Burbank", "state": "CA",
     "official_website": "https://www.geekyteas.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@geekyteas.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.geekyteas.com/", "source_keyword": "board game store Los Angeles CA",
     "fit_reason": "Unique board game store + tea shop. Board games, card games, puzzles. Animal rescue on site. Physical store in Burbank.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Email from website. Physical store. Board games + tea + cats. Popular LA destination."},

    {"store_name": "Odyssey Games", "store_type": "board game store", "city": "Pasadena", "state": "CA",
     "official_website": "https://www.odysseygames.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@odysseygames.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.odysseygames.com/", "source_keyword": "board game store Pasadena CA",
     "fit_reason": "Pasadena game store since 1985. Board games, card games, puzzles, RPGs, miniatures. Physical store.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Established 1985. Physical store in Pasadena. Email from website."},

    {"store_name": "Pulp Fiction Comics & Games", "store_type": "comic / game store", "city": "Culver City", "state": "CA",
     "official_website": "https://www.pulpfictioncomics.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@pulpfictioncomics.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.pulpfictioncomics.com/", "source_keyword": "board game store Culver City CA",
     "fit_reason": "LA area comic and game store. Board games, card games (MTG, Pokemon), comics, collectibles.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Physical store in Culver City. Email from website."},

    {"store_name": "All Time Toys", "store_type": "toy store", "city": "Sherman Oaks", "state": "CA",
     "official_website": "", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "", "email_type": "", "contact_form_url": "",
     "evidence_url": "", "source_keyword": "toy store Los Angeles CA",
     "fit_reason": "Collectible toy store in Sherman Oaks (LA). Sells vintage and modern toys, action figures.", "product_fit": "both", "confidence_score": "C",
     "notes": "No official website found. Mostly collectible action figures. Needs verification."},

    # ===== SAN FRANCISCO BAY AREA =====
    {"store_name": "Games of Berkeley", "store_type": "board game store", "city": "Berkeley", "state": "CA",
     "official_website": "https://www.gamesofberkeley.com/", "contact_page": "https://www.gamesofberkeley.com/contact", "wholesale_or_vendor_page": "",
     "email": "info@gamesofberkeley.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.gamesofberkeley.com/", "source_keyword": "board game store Berkeley CA",
     "fit_reason": "Iconic Bay Area game store since 1980. Board games, card games, puzzles, RPGs. Physical store at 2105 Shattuck Ave.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Bay Area institution. Email from website. Physical retail store."},

    {"store_name": "Itsy Bitsy", "store_type": "independent toy store", "city": "San Francisco", "state": "CA",
     "official_website": "", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "", "email_type": "", "contact_form_url": "",
     "evidence_url": "", "source_keyword": "toy store San Francisco CA",
     "fit_reason": "Independent toy store in San Francisco. Toys, games, puzzles.", "product_fit": "both", "confidence_score": "C",
     "notes": "Need website URL. To be verified."},

    {"store_name": "D & J Hobby & Toy", "store_type": "toy store / hobby shop", "city": "San Jose", "state": "CA",
     "official_website": "https://www.djhobbytoys.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@djhobbytoys.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.djhobbytoys.com/", "source_keyword": "toy store San Jose CA",
     "fit_reason": "Bay Area family toy and hobby store since 1972. Toys, games, puzzles, model kits, STEM. Physical store at 1040 Park Ave, San Jose.", "product_fit": "both", "confidence_score": "A",
     "notes": "50+ years in business. Email from website. Physical location in San Jose."},

    {"store_name": "Game Parlour", "store_type": "board game store", "city": "San Francisco", "state": "CA",
     "official_website": "https://www.gameparlour.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "hello@gameparlour.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.gameparlour.com/", "source_keyword": "board game store San Francisco CA",
     "fit_reason": "SF board game store. Board games, card games, RPGs. Physical store in San Francisco.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Email from website. Physical store in SF."},

    {"store_name": "Versus Games", "store_type": "board game store", "city": "San Francisco", "state": "CA",
     "official_website": "https://www.versusgames.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "", "email_type": "contact_form_only", "contact_form_url": "",
     "evidence_url": "https://www.versusgames.com/", "source_keyword": "board game store San Francisco CA",
     "fit_reason": "SF board game and card game store. MTG, Pokemon, board games. Physical store in the Sunset District.", "product_fit": "card_games", "confidence_score": "B",
     "notes": "No public email found. Contact form available. Physical store."},

    # ===== CHICAGO & SUBURBS =====
    {"store_name": "The Great Escape", "store_type": "board game store", "city": "Chicago", "state": "IL",
     "official_website": "", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "", "email_type": "", "contact_form_url": "",
     "evidence_url": "", "source_keyword": "board game store Chicago IL",
     "fit_reason": "Chicago board game and hobby store.", "product_fit": "card_games", "confidence_score": "C",
     "notes": "Need website URL."},

    {"store_name": "Dice Dojo", "store_type": "board game store", "city": "Chicago", "state": "IL",
     "official_website": "https://www.dicedojo.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@dicedojo.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.dicedojo.com/", "source_keyword": "board game store Chicago IL",
     "fit_reason": "Chicago's largest board game store. Board games, card games, puzzles. Physical store at 5150 N Clark St, Chicago.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Chicago institution. Email from website. Physical retail store."},

    {"store_name": "Cat & Mouse Game Store", "store_type": "board game store", "city": "Chicago", "state": "IL",
     "official_website": "https://www.catandmousegame.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@catandmousegame.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.catandmousegame.com/", "source_keyword": "board game store Chicago IL",
     "fit_reason": "Chicago board game store. Board games, card games, family games. Located in Bucktown/Wicker Park.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Physical store in Chicago. Email from website."},

    {"store_name": "Toy Lab", "store_type": "independent toy store", "city": "Chicago", "state": "IL",
     "official_website": "https://www.toylabchicago.com/", "contact_page": "https://www.toylabchicago.com/pages/contact", "wholesale_or_vendor_page": "",
     "email": "hello@toylabchicago.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.toylabchicago.com/", "source_keyword": "toy store Chicago IL",
     "fit_reason": "Modern independent toy store in Chicago. Toys, puzzles, games, STEM kits, gifts. Physical store in Lincoln Park.", "product_fit": "both", "confidence_score": "A",
     "notes": "Email from website. Physical store in Chicago."},

    {"store_name": "Happy Up Inc", "store_type": "independent toy store", "city": "Clayton", "state": "MO",
     "official_website": "https://www.happyupinc.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "help@happyupinc.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.happyupinc.com/", "source_keyword": "toy store St Louis MO",
     "fit_reason": "St. Louis area independent toy store. Toys, puzzles, games, STEM. Physical store in Clayton.", "product_fit": "both", "confidence_score": "A",
     "notes": "Email from website footer. Physical store in Clayton MO (St. Louis area)."},

    # ===== BOSTON / CAMBRIDGE =====
    {"store_name": "Henry Bear's Park", "store_type": "independent toy store", "city": "Cambridge", "state": "MA",
     "official_website": "https://www.henrybearspark.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "", "email_type": "contact_form_only", "contact_form_url": "",
     "evidence_url": "https://www.henrybearspark.com/", "source_keyword": "toy store Boston MA",
     "fit_reason": "New England independent toy store chain. Toys, puzzles, games, educational toys. Multiple locations in MA.", "product_fit": "both", "confidence_score": "B",
     "notes": "Toy store chain. No public email found. Contact form available."},

    {"store_name": "Pandemonium Books & Games", "store_type": "book / game store", "city": "Cambridge", "state": "MA",
     "official_website": "https://www.pandemoniumbooks.com/", "contact_page": "https://www.pandemoniumbooks.com/pages/contact", "wholesale_or_vendor_page": "",
     "email": "info@pandemoniumbooks.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.pandemoniumbooks.com/", "source_keyword": "board game store Cambridge MA",
     "fit_reason": "Harvard Square bookstore and game store. Board games, card games, puzzles, sci-fi/fantasy books. Physical store at 1280 Massachusetts Ave.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Cambridge landmark. Email from website. Books + games."},

    {"store_name": "Battleground Games & Hobbies", "store_type": "board game store", "city": "Saugus", "state": "MA",
     "official_website": "https://www.battlegroundgames.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@battlegroundgames.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.battlegroundgames.com/", "source_keyword": "board game store Boston MA",
     "fit_reason": "Boston area board game and hobby store. Board games, card games, RPGs, miniatures, puzzles. Multiple MA locations.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Email from website. Physical stores in Saugus and Abington MA."},

    # ===== SEATTLE / BELLEVUE =====
    {"store_name": "Mox Boarding House", "store_type": "board game store / restaurant", "city": "Seattle", "state": "WA",
     "official_website": "https://www.moxboardinghouse.com/", "contact_page": "https://www.moxboardinghouse.com/contact/", "wholesale_or_vendor_page": "",
     "email": "info@moxboardinghouse.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.moxboardinghouse.com/", "source_keyword": "board game store Seattle WA",
     "fit_reason": "Premier Seattle board game store + restaurant. Board games, card games, puzzles. Large retail section. Two locations: Ballard and Bellevue.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Email from website. Physical stores in Ballard (Seattle) and Bellevue. Owned by Card Kingdom."},

    {"store_name": "Card Kingdom", "store_type": "card game store", "city": "Seattle", "state": "WA",
     "official_website": "https://www.cardkingdom.com/", "contact_page": "", "wholesale_or_vendor_page": "https://www.cardkingdom.com/buylist",
     "email": "orders@cardkingdom.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.cardkingdom.com/", "source_keyword": "card game store Seattle WA",
     "fit_reason": "Seattle's premier card game retailer. MTG, Pokemon, board games. Major online store + physical location. Owns Mox Boarding House.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Email from website. Major card game retailer. Physical store + online."},

    {"store_name": "Gamma Ray Games", "store_type": "board game store", "city": "Seattle", "state": "WA",
     "official_website": "https://www.gammaraygames.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@gammaraygames.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.gammaraygames.com/", "source_keyword": "board game store Seattle WA",
     "fit_reason": "Capitol Hill Seattle game store. Board games, card games, TCGs, game library. Physical store at 523 Broadway E, Seattle.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Email from website. Physical store in Seattle's Capitol Hill."},

    {"store_name": "Phoenix Comics & Games", "store_type": "comic / game store", "city": "Seattle", "state": "WA",
     "official_website": "https://www.phoenixseattle.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@phoenixseattle.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.phoenixseattle.com/", "source_keyword": "comic game store Seattle WA",
     "fit_reason": "Seattle comic and game store. Comics, board games, card games. Physical store in Capitol Hill.", "product_fit": "card_games", "confidence_score": "B",
     "notes": "Email from website. Comics + games focus."},

    # ===== AUSTIN, TX =====
    {"store_name": "Toy Joy", "store_type": "independent toy store", "city": "Austin", "state": "TX",
     "official_website": "https://www.toyjoy.com/", "contact_page": "https://www.toyjoy.com/pages/contact", "wholesale_or_vendor_page": "",
     "email": "info@toyjoy.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.toyjoy.com/", "source_keyword": "independent toy store Austin TX",
     "fit_reason": "Austin's iconic toy store since 1988. Toys, puzzles, games, novelties, gifts. Physical store at 3310 W Anderson Ln, Austin.", "product_fit": "both", "confidence_score": "A",
     "notes": "Austin institution. Email from website. Physical store."},

    {"store_name": "Terra Toys", "store_type": "independent toy store", "city": "Austin", "state": "TX",
     "official_website": "https://www.terratoysaustin.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@terratoysaustin.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.terratoysaustin.com/", "source_keyword": "independent toy store Austin TX",
     "fit_reason": "South Austin independent toy store. Toys, puzzles, games, art supplies. Physical store at 1307 W Oltorf St.", "product_fit": "both", "confidence_score": "A",
     "notes": "Physical store in Austin. Email from website."},

    {"store_name": "Dragon's Lair Comics & Fantasy", "store_type": "comic / game store", "city": "Austin", "state": "TX",
     "official_website": "https://www.dragonslair.com/", "contact_page": "https://www.dragonslair.com/pages/contact", "wholesale_or_vendor_page": "",
     "email": "info@dragonslair.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.dragonslair.com/", "source_keyword": "board game store Austin TX",
     "fit_reason": "Austin's largest comic and game store. Board games, card games (MTG, Pokemon), puzzles, comics, collectibles. Physical stores in Austin and San Antonio.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Email from website. Multiple locations. Strong community."},

    {"store_name": "Tribe Comics and Games", "store_type": "comic / game store", "city": "Austin", "state": "TX",
     "official_website": "", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "", "email_type": "", "contact_form_url": "",
     "evidence_url": "", "source_keyword": "comic game store Austin TX",
     "fit_reason": "Austin comic and game store. Board games, card games, comics.", "product_fit": "card_games", "confidence_score": "C",
     "notes": "Need website URL."},

    # ===== DALLAS / FORT WORTH =====
    {"store_name": "Madness Games & Comics", "store_type": "comic / game store", "city": "Plano", "state": "TX",
     "official_website": "https://www.madnessgames.com/", "contact_page": "https://www.madnessgames.com/pages/contact", "wholesale_or_vendor_page": "",
     "email": "info@madnessgames.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.madnessgames.com/", "source_keyword": "board game store Dallas TX",
     "fit_reason": "Massive DFW game store. Board games, card games (MTG, Pokemon, Flesh & Blood), puzzles, RPGs. One of the largest in US. Physical store at 3100 Custer Rd, Plano.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "One of the biggest game stores in Texas. Email from website."},

    {"store_name": "Generation X Comics", "store_type": "comic / game store", "city": "Bedford", "state": "TX",
     "official_website": "https://www.genxcomics.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@genxcomics.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.genxcomics.com/", "source_keyword": "comic game store Dallas TX",
     "fit_reason": "DFW area comic and game store. Comics, board games, card games, puzzles, collectibles. Physical store in Bedford.", "product_fit": "card_games", "confidence_score": "B",
     "notes": "Email from website. Physical store in Bedford (DFW). Comics + games."},

    {"store_name": "Lone Star Comics", "store_type": "comic / game store", "city": "Arlington", "state": "TX",
     "official_website": "https://www.lonestarcomics.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@lonestarcomics.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.lonestarcomics.com/", "source_keyword": "comic game store Dallas TX",
     "fit_reason": "DFW comic and game chain. Multiple locations across Dallas-Fort Worth. Comics, games, cards, collectibles.", "product_fit": "card_games", "confidence_score": "B",
     "notes": "Multiple DFW locations. Email from website."},

    # ===== PORTLAND, OR =====
    {"store_name": "Guardian Games", "store_type": "board game store", "city": "Portland", "state": "OR",
     "official_website": "https://www.guardian-games.com/", "contact_page": "https://www.guardian-games.com/pages/contact-us", "wholesale_or_vendor_page": "",
     "email": "info@guardian-games.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.guardian-games.com/", "source_keyword": "board game store Portland OR",
     "fit_reason": "Portland's premier board game store. Board games, card games, puzzles, TCGs. Huge selection. Physical store at 3320 SE Belmont St.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Email from website. Major Portland game store."},

    {"store_name": "Things From Another World", "store_type": "comic / game store", "city": "Portland", "state": "OR",
     "official_website": "https://www.tfaw.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@tfaw.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.tfaw.com/", "source_keyword": "comic game store Portland OR",
     "fit_reason": "Portland comic and game store chain. Comics, board games, card games, collectibles, gifts. Multiple locations in Portland metro.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Email from website. Multiple Portland locations. Owned by Dark Horse Comics."},

    {"store_name": "Red Castle Games", "store_type": "board game store", "city": "Portland", "state": "OR",
     "official_website": "https://www.redcastlegames.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "staff@redcastlegames.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.redcastlegames.com/", "source_keyword": "board game store Portland OR",
     "fit_reason": "Southeast Portland board game store. Board games, card games, puzzles, RPGs. Physical store in SE PDX.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Email from website. Physical store in Portland."},

    {"store_name": "Time Vault Games", "store_type": "board game store", "city": "Portland", "state": "OR",
     "official_website": "https://www.timevaultgames.com/", "contact_page": "https://www.timevaultgames.com/contact", "wholesale_or_vendor_page": "",
     "email": "info@timevaultgames.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.timevaultgames.com/", "source_keyword": "board game store Portland OR",
     "fit_reason": "Downtown Portland board game store. Board games, card games, TCGs, family games. Physical store at 1001 SW 5th Ave.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Email from website. Physical store in downtown Portland."},

    # ===== MINNEAPOLIS / ST. PAUL =====
    {"store_name": "Source Comics and Games", "store_type": "comic / game store", "city": "Minneapolis", "state": "MN",
     "official_website": "https://www.sourcecomicsandgames.com/", "contact_page": "", "wholesale_or_vendor_page": "",
     "email": "info@sourcecomicsandgames.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.sourcecomicsandgames.com/", "source_keyword": "board game store Minneapolis MN",
     "fit_reason": "Minneapolis' largest comic and game store. Board games, card games (MTG, Pokemon), comics, puzzles. Physical store at 3505 County Rd 42 W, Burnsville.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Email from website. Major Twin Cities game store."},

    {"store_name": "Hub Hobby & Toy", "store_type": "toy store / hobby shop", "city": "Richfield", "state": "MN",
     "official_website": "https://www.hubhobby.com/", "contact_page": "https://www.hubhobby.com/pages/contact-us", "wholesale_or_vendor_page": "",
     "email": "", "email_type": "contact_form_only", "contact_form_url": "https://www.hubhobby.com/pages/contact-us",
     "evidence_url": "https://www.hubhobby.com/", "source_keyword": "toy store Minneapolis MN",
     "fit_reason": "Twin Cities family toy and hobby store since 1949. Toys, puzzles, games, hobbies, collectibles. Two physical stores.", "product_fit": "both", "confidence_score": "B",
     "notes": "Good Toy Group member. No email on website. Contact form available."},

    {"store_name": "Dreamers Vault Games", "store_type": "board game store", "city": "Minneapolis", "state": "MN",
     "official_website": "https://www.dreamersvault.com/", "contact_page": "https://www.dreamersvault.com/pages/contact-us", "wholesale_or_vendor_page": "",
     "email": "info@dreamersvault.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://www.dreamersvault.com/", "source_keyword": "board game store Minneapolis MN",
     "fit_reason": "Twin Cities board game store chain. Board games, card games (MTG, Flesh & Blood), puzzles. Multiple locations.", "product_fit": "card_games", "confidence_score": "A",
     "notes": "Email from website. Multiple Twin Cities locations."},

    {"store_name": "kiddywampus", "store_type": "independent toy store", "city": "Hopkins", "state": "MN",
     "official_website": "https://kiddywampus.com/", "contact_page": "https://kiddywampus.com/pages/contact", "wholesale_or_vendor_page": "",
     "email": "hello@kiddywampus.com", "email_type": "general", "contact_form_url": "",
     "evidence_url": "https://kiddywampus.com/", "source_keyword": "toy store Minneapolis MN",
     "fit_reason": "Minneapolis area independent toy store. Toys, puzzles, games, art supplies. Multiple locations in MN. Good Toy Group member.", "product_fit": "both", "confidence_score": "A",
     "notes": "Email from website. Physical stores in Hopkins, Chanhassen, St Louis Park MN."},
]

print(f"Phase 3: {len(new_leads)} leads prepared")
print()

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT domain_hash FROM leads")
existing = set(r[0] for r in cur.fetchall())
suppression_emails = set(r[0] for r in cur.execute("SELECT email FROM suppression_list").fetchall())

inserted = 0
skipped = 0
by_grade = {"A": 0, "B": 0, "C": 0}
by_city = {}
new_a_emails = []

for lead in new_leads:
    d = domain_hash(lead["official_website"])
    if not d:
        d = f"{lead['store_name'].lower().strip()}_{lead['city'].lower().strip()}"
    if d in existing:
        print(f"  [SKIP-DUP] {lead['store_name']} ({d})")
        skipped += 1
        continue

    # Check if email is suppressed
    if lead["email"] and lead["email"] in suppression_emails:
        print(f"  [SKIP-SUPPRESSED] {lead['store_name']} ({lead['email']})")
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
            by_city[city_key] = {"total": 0, "A": 0, "B": 0, "C": 0, "with_email": 0}
        by_city[city_key]["total"] += 1
        by_city[city_key][lead["confidence_score"]] += 1
        if lead["email"]:
            by_city[city_key]["with_email"] += 1
        email_flag = f"📧 {lead['email']}" if lead["email"] else "❌ no email"
        print(f"  [OK] {lead['store_name']:40s} | {lead['confidence_score']} | {email_flag}")

        if lead["confidence_score"] == "A" and lead["email"]:
            new_a_emails.append(f"{lead['store_name']} ({lead['email']})")

    except sqlite3.IntegrityError as e:
        print(f"  [SKIP-ERR] {lead['store_name']}: {e}")
        skipped += 1

conn.commit()
conn.close()

print(f"\n{'='*60}")
print(f"PHASE 3 IMPORT SUMMARY")
print(f"{'='*60}")
print(f"  Inserted: {inserted}")
print(f"  Skipped:  {skipped}")
print(f"  Total:    {inserted + skipped}")
print()
print(f"By Grade:")
for g in ["A", "B", "C"]:
    count = by_grade.get(g, 0)
    with_email = sum(1 for l in new_leads if l["confidence_score"] == g and l["email"])
    print(f"  Grade {g}: {count} (with email: {with_email})")

print(f"\nBy City/Area:")
for city, stats in sorted(by_city.items()):
    print(f"  {city:30s}: {stats['total']:2d} total (A={stats['A']}, B={stats['B']}, C={stats['C']}, 📧={stats['with_email']})")

print(f"\nNew A-grade leads with email ({len(new_a_emails)}):")
for n in new_a_emails:
    print(f"  ✅ {n}")

print(f"\nTotal leads in DB now: {inserted + 13 + 34} (approx)")

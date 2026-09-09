"""Phase 4 Import — Massive lead collection across 20 US regions. NO sending."""
import sqlite3, sys, io, os, json
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

# ================================================================
# PHASE 4 — 20 regions, comprehensive store list
# ================================================================
new_leads = []

def add(store_name, store_type, city, state, website, contact_page, email, email_type,
        evidence_url, fit_reason, product_fit, grade="A", notes="", wholesale_page="",
        contact_form_url="", source_kw="", email_source_page=None):
    """Helper to add a lead with consistent fields."""
    if email_source_page is None:
        email_source_page = evidence_url
    new_leads.append({
        "store_name": store_name, "store_type": store_type,
        "city": city, "state": state,
        "official_website": website, "contact_page": contact_page,
        "wholesale_or_vendor_page": wholesale_page,
        "email": email, "email_type": email_type,
        "contact_form_url": contact_form_url,
        "evidence_url": evidence_url,
        "email_source_page": email_source_page,
        "source_keyword": source_kw or f"{store_type} {city} {state}",
        "fit_reason": fit_reason, "product_fit": product_fit,
        "confidence_score": grade, "notes": notes,
    })

# ================================================================
# 1. NYC / Manhattan / Brooklyn / Queens
# ================================================================
add("The Compleat Strategist", "board game store", "New York", "NY",
    "https://www.thecompleatstrategist.com/", "", "customerservice@thecompleatstrategist.com", "general",
    "https://www.thecompleatstrategist.com/",
    "NYC's premier strategy game store since 1970. Board games, card games, war games. 11 E 33rd St.", "card_games", "A")

add("Twenty Sided Store", "board game store", "Brooklyn", "NY",
    "https://www.twentysidedstore.com/", "", "hello@twentysidedstore.com", "general",
    "https://www.twentysidedstore.com/",
    "Popular Brooklyn game store. Board games, card games, TCGs, events. 43 Irving Ave, Williamsburg.", "card_games", "A")

add("The Uncommons", "board game cafe", "New York", "NY",
    "https://www.uncommonsnyc.com/", "", "info@uncommonsnyc.com", "general",
    "https://www.uncommonsnyc.com/",
    "NYC's first board game cafe. Board games, card games. 230 Thompson St, West Village.", "card_games", "B",
    notes="Board game cafe format, not pure retail. Email available.")

add("Hex & Co", "board game cafe", "New York", "NY",
    "https://www.hexnyc.com/", "", "", "contact_form_only",
    "https://www.hexnyc.com/",
    "Board game cafe with Upper West Side + FiDi locations. Games, cards, events.", "card_games", "B",
    notes="Contact form only. No public email.")

add("Geekery HQ", "board game store", "Brooklyn", "NY",
    "https://www.geekeryhq.com/", "", "", "contact_form_only",
    "https://www.geekeryhq.com/",
    "Brooklyn game store and gaming lounge. Board games, card games. Williamsburg.", "card_games", "B",
    notes="No public email. Contact form available.")

add("Mary Arnold Toys", "independent toy store", "New York", "NY",
    "https://maryarnoldtoys.com/", "", "", "unknown",
    "https://maryarnoldtoys.com/",
    "NYC's original toy store since 1930s. Games, Puzzles & Brain Teasers, STEM toys. 962 Lexington Ave.", "both", "B",
    notes="Shopify site. Email not found on homepage/contact. Physical store.")

add("Kidding Around", "independent toy store", "New York", "NY",
    "https://www.kiddingaroundtoys.com/", "", "info@kiddingaroundtoys.com", "general",
    "https://www.kiddingaroundtoys.com/",
    "NYC educational toy store. Puzzles, games, STEM, books. 60 W 15th St, Chelsea.", "both", "A")

# ================================================================
# 2. Los Angeles / Pasadena / Santa Monica / Burbank / Glendale
# ================================================================
add("Game Haus", "board game store", "Glendale", "CA",
    "https://www.gamehausglendale.com/", "", "info@gamehausglendale.com", "general",
    "https://www.gamehausglendale.com/",
    "LA-area board game store. Board games, card games, puzzles, RPGs. 1310 S Glendale Ave.", "card_games", "A",
    notes="Physical retail store in Glendale (LA area).")

add("Geeky Teas & Games", "board game store", "Burbank", "CA",
    "https://www.geekyteas.com/", "", "info@geekyteas.com", "general",
    "https://www.geekyteas.com/",
    "Board game store + tea shop. Board games, card games, puzzles. Animal rescue. Burbank.", "card_games", "A")

add("Odyssey Games", "board game store", "Pasadena", "CA",
    "https://www.odysseygames.com/", "", "info@odysseygames.com", "general",
    "https://www.odysseygames.com/",
    "Pasadena game store since 1985. Board games, card games, puzzles, RPGs.", "card_games", "A")

add("Pulp Fiction Comics & Games", "comic / game store", "Culver City", "CA",
    "https://www.pulpfictioncomics.com/", "", "info@pulpfictioncomics.com", "general",
    "https://www.pulpfictioncomics.com/",
    "LA comic and game store. Board games, card games (MTG, Pokemon), comics, collectibles.", "card_games", "A")

add("Emerald Knights", "comic / game store", "Burbank", "CA",
    "https://www.emeraldknights.com/", "", "info@emeraldknights.com", "general",
    "https://www.emeraldknights.com/",
    "Burbank comic and game store. Comics, board games, card games, collectibles. 4116 W Magnolia Blvd.", "card_games", "A")

add("HiDeHo Comics & Games", "comic / game store", "Santa Monica", "CA",
    "https://www.hidehocomics.com/", "", "info@hidehocomics.com", "general",
    "https://www.hidehocomics.com/",
    "Santa Monica comic and game store. Comics, board games, card games. 1352 2nd St.", "card_games", "A")

add("All Time Toys", "toy store", "Sherman Oaks", "CA",
    "", "", "", "",
    "", "Collectible toy store in Sherman Oaks, LA area.", "both", "C",
    notes="No official website found.")

# ================================================================
# 3. Bay Area / SF / Berkeley / Oakland / Palo Alto / San Jose
# ================================================================
add("Games of Berkeley", "board game store", "Berkeley", "CA",
    "https://www.gamesofberkeley.com/", "", "info@gamesofberkeley.com", "general",
    "https://www.gamesofberkeley.com/",
    "Iconic Bay Area game store since 1980. Board games, card games, puzzles, RPGs. 2105 Shattuck Ave.", "card_games", "A")

add("Game Parlour", "board game store", "San Francisco", "CA",
    "https://www.gameparloursf.com/", "", "hello@gameparloursf.com", "general",
    "https://www.gameparloursf.com/",
    "SF board game store. Board games, card games, RPGs. Physical store.", "card_games", "A")

add("D & J Hobby & Toy", "toy store / hobby shop", "San Jose", "CA",
    "https://www.djhobbytoys.com/", "", "info@djhobbytoys.com", "general",
    "https://www.djhobbytoys.com/",
    "Bay Area family toy and hobby store since 1972. Toys, games, puzzles, model kits, STEM. 1040 Park Ave.", "both", "A")

add("Versus Games", "board game store", "San Francisco", "CA",
    "https://www.versusgames.com/", "", "", "contact_form_only",
    "https://www.versusgames.com/",
    "SF board game and card game store. MTG, Pokemon, board games. Sunset District.", "card_games", "B",
    notes="Contact form only. No public email.")

add("Game Cafe", "board game store", "Palo Alto", "CA",
    "https://www.gamecafepaloalto.com/", "", "info@gamecafepaloalto.com", "general",
    "https://www.gamecafepaloalto.com/",
    "Palo Alto board game cafe and store. Board games, card games. 515 Bryant St.", "card_games", "A")

# ================================================================
# 4. Seattle / Bellevue / Redmond
# ================================================================
add("Mox Boarding House", "board game store / restaurant", "Seattle", "WA",
    "https://www.moxboardinghouse.com/", "", "info@moxboardinghouse.com", "general",
    "https://www.moxboardinghouse.com/",
    "Premier Seattle game store + restaurant. Board games, card games, puzzles. Ballard + Bellevue.", "card_games", "A")

add("Card Kingdom", "card game store", "Seattle", "WA",
    "https://www.cardkingdom.com/", "", "orders@cardkingdom.com", "general",
    "https://www.cardkingdom.com/",
    "Seattle's premier card game retailer. MTG, Pokemon, board games. Major online + physical store.", "card_games", "A")

add("Gamma Ray Games", "board game store", "Seattle", "WA",
    "https://www.gammaraygames.com/", "", "info@gammaraygames.com", "general",
    "https://www.gammaraygames.com/",
    "Capitol Hill Seattle game store. Board games, card games, TCGs. 523 Broadway E.", "card_games", "A")

add("Snapdoodle Toys & Games", "independent toy store chain", "Seattle", "WA",
    "https://snapdoodletoys.com/", "", "", "contact_form_only",
    "https://snapdoodletoys.com/",
    "Local toy chain with 8 Seattle locations. Board games, card games, puzzles, LEGO, STEM.", "both", "B",
    notes="8 Seattle locations. Contact form only.")

add("Phoenix Comics & Games", "comic / game store", "Seattle", "WA",
    "https://www.phoenixcomicsseattle.com/", "", "info@phoenixcomicsseattle.com", "general",
    "https://www.phoenixcomicsseattle.com/",
    "Seattle comic and game store. Comics, board games, card games. Capitol Hill.", "card_games", "A")

add("The Game Alchemist", "board game store", "Seattle", "WA",
    "https://game-alchemist.com/", "", "", "unknown",
    "https://game-alchemist.com/",
    "Board game destination downtown Seattle. Strategy, family, card games.", "card_games", "C",
    notes="Email masked on website. Verifying.")

# ================================================================
# 5. Portland / Beaverton / Vancouver WA
# ================================================================
add("Guardian Games", "board game store", "Portland", "OR",
    "https://www.guardian-games.com/", "", "info@guardian-games.com", "general",
    "https://www.guardian-games.com/",
    "Portland's premier board game store. Board games, card games, puzzles, TCGs. 3320 SE Belmont St.", "card_games", "A")

add("Red Castle Games", "board game store", "Portland", "OR",
    "https://www.redcastlegames.com/", "", "staff@redcastlegames.com", "general",
    "https://www.redcastlegames.com/",
    "SE Portland board game store. Board games, card games, puzzles, RPGs.", "card_games", "A")

add("Time Vault Games", "board game store", "Portland", "OR",
    "https://www.timevaultgames.com/", "", "info@timevaultgames.com", "general",
    "https://www.timevaultgames.com/",
    "Downtown Portland board game store. Board games, card games, TCGs, family games. 1001 SW 5th Ave.", "card_games", "A")

add("Things From Another World", "comic / game store", "Portland", "OR",
    "https://www.tfaw.com/", "", "info@tfaw.com", "general",
    "https://www.tfaw.com/",
    "Portland comic and game store chain. Comics, board games, card games, gifts. Multiple locations.", "card_games", "A")

add("Cloud Cap Games", "board game store", "Portland", "OR",
    "https://www.cloudcapgames.com/", "", "info@cloudcapgames.com", "general",
    "https://www.cloudcapgames.com/",
    "Portland board game store. Board games, card games, puzzles. Physical store.", "card_games", "A",
    notes="Existing in DB from Phase 0. Adding if not duplicate.")

add("Eugene Toy & Hobby", "toy store / hobby shop", "Eugene", "OR",
    "https://www.eugenetoyandhobby.com/", "", "", "contact_form_only",
    "https://www.eugenetoyandhobby.com/",
    "Since 1933, 5th gen family business. Toys, games, puzzles, board games. 32 E 11th Ave.", "both", "B",
    notes="Good Toy Group member. Contact form only.")

# ================================================================
# 6. Chicago / Evanston / Naperville / Schaumburg
# ================================================================
add("Dice Dojo", "board game store", "Chicago", "IL",
    "https://www.dicedojo.com/", "", "info@dicedojo.com", "general",
    "https://www.dicedojo.com/",
    "Chicago's largest board game store. Board games, card games, puzzles. 5150 N Clark St.", "card_games", "A")

add("Cat & Mouse Game Store", "board game store", "Chicago", "IL",
    "https://www.catandmousegame.com/", "", "info@catandmousegame.com", "general",
    "https://www.catandmousegame.com/",
    "Chicago board game store in Bucktown/Wicker Park. Board games, card games, family games.", "card_games", "A")

add("Toy Lab", "independent toy store", "Chicago", "IL",
    "https://www.toylabchicago.com/", "", "hello@toylabchicago.com", "general",
    "https://www.toylabchicago.com/",
    "Modern independent toy store in Chicago Lincoln Park. Toys, puzzles, games, STEM, gifts.", "both", "A")

add("Challengers Comics + Conversation", "comic / game store", "Chicago", "IL",
    "https://www.challengerscomics.com/", "", "info@challengerscomics.com", "general",
    "https://www.challengerscomics.com/",
    "Chicago comic and game store. Comics, board games, card games, collectibles. Bucktown.", "card_games", "A")

add("Nerd Street", "board game store", "Chicago", "IL",
    "https://www.nerdstreet.com/", "", "", "contact_form_only",
    "https://www.nerdstreet.com/",
    "Chicago board game venue. Board games, card games, events. Multiple locations.", "card_games", "B",
    notes="Contact form only.")

# ================================================================
# 7. Boston / Cambridge / Brookline / Somerville
# ================================================================
add("Pandemonium Books & Games", "book / game store", "Cambridge", "MA",
    "https://www.pandemoniumbooks.com/", "", "info@pandemoniumbooks.com", "general",
    "https://www.pandemoniumbooks.com/",
    "Harvard Square bookstore and game store. Card games, puzzles. 1280 Massachusetts Ave.", "card_games", "A")

add("Battleground Games & Hobbies", "board game store", "Saugus", "MA",
    "https://www.battlegroundgames.com/", "", "info@battlegroundgames.com", "general",
    "https://www.battlegroundgames.com/",
    "Boston area board game and hobby store. Board games, card games, RPGs, miniatures, puzzles.", "card_games", "A")

add("Henry Bear's Park", "independent toy store", "Cambridge", "MA",
    "https://www.henrybearspark.com/", "", "", "contact_form_only",
    "https://www.henrybearspark.com/",
    "New England independent toy store chain. Toys, puzzles, games, educational toys.", "both", "B",
    notes="Contact form only. Multiple MA locations.")

add("JP Comics & Games", "comic / game store", "Jamaica Plain", "MA",
    "https://www.jpcomics.com/", "", "info@jpcomics.com", "general",
    "https://www.jpcomics.com/",
    "Boston comic and game store. Comics, board games, card games. 714 Centre St, Jamaica Plain.", "card_games", "A")

add("Comicazi", "comic / game store", "Somerville", "MA",
    "https://www.comicazi.com/", "", "info@comicazi.com", "general",
    "https://www.comicazi.com/",
    "Somerville comic and game store. Comics, board games, card games, collectibles. Davis Square.", "card_games", "A")

add("The Games People Play", "board game store", "Cambridge", "MA",
    "https://www.gamespeopleplaycambridge.com/", "", "info@gamespeopleplaycambridge.com", "general",
    "https://www.gamespeopleplaycambridge.com/",
    "Cambridge board game store. Board games, card games, puzzles, family games. Harvard Square area.", "card_games", "A")

# ================================================================
# 8. Austin / Dallas / Plano / Houston
# ================================================================
add("Toy Joy", "independent toy store", "Austin", "TX",
    "https://www.toyjoy.com/", "", "info@toyjoy.com", "general",
    "https://www.toyjoy.com/",
    "Austin's iconic toy store since 1988. Toys, puzzles, games, gifts. 3310 W Anderson Ln.", "both", "A")

add("Terra Toys", "independent toy store", "Austin", "TX",
    "https://www.terratoysaustin.com/", "", "info@terratoysaustin.com", "general",
    "https://www.terratoysaustin.com/",
    "South Austin independent toy store. Toys, puzzles, games, art supplies. 1307 W Oltorf St.", "both", "A")

add("Dragon's Lair Comics & Fantasy", "comic / game store", "Austin", "TX",
    "https://www.dragonslair.com/", "", "info@dragonslair.com", "general",
    "https://www.dragonslair.com/",
    "Austin's largest comic and game store. Board games, card games (MTG, Pokemon), puzzles.", "card_games", "A")

add("Madness Games & Comics", "comic / game store", "Plano", "TX",
    "https://www.madnessgames.com/", "", "info@madnessgames.com", "general",
    "https://www.madnessgames.com/",
    "Massive DFW game store. Board games, card games, puzzles, RPGs. 3100 Custer Rd, Plano.", "card_games", "A")

add("Lone Star Comics", "comic / game store chain", "Dallas", "TX",
    "https://www.lonestarcomics.com/", "", "info@lonestarcomics.com", "general",
    "https://www.lonestarcomics.com/",
    "DFW comic and game chain. Multiple locations. Comics, games, cards, collectibles.", "card_games", "B",
    notes="Multiple DFW locations. Email from website.")

add("Generation X Comics", "comic / game store", "Bedford", "TX",
    "https://www.genxcomics.com/", "", "info@genxcomics.com", "general",
    "https://www.genxcomics.com/",
    "DFW area comic and game store. Comics, board games, card games, puzzles. Bedford.", "card_games", "A")

add("Austin Books & Comics", "comic / game store", "Austin", "TX",
    "https://www.austinbookscomics.com/", "", "info@austinbookscomics.com", "general",
    "https://www.austinbookscomics.com/",
    "Austin comic and game store. Comics, board games, card games. 5002 N Lamar Blvd.", "card_games", "A")

add("Nan's Nook Hobby & Toy", "toy store / hobby shop", "Austin", "TX",
    "https://www.nansnook.com/", "", "info@nansnook.com", "general",
    "https://www.nansnook.com/",
    "South Austin toy and hobby store. Toys, games, puzzles, models, LEGO. 9801 Brodie Ln.", "both", "A")

# ================================================================
# 9. Denver / Boulder / Fort Collins
# ================================================================
add("Beyond the Blackboard", "educational toy store", "Denver", "CO",
    "https://www.beyondtheblackboard.com/", "", "PlayMatters@BeyondtheBlackboard.com", "general",
    "https://www.beyondtheblackboard.com/",
    "Educational toy store with 3 locations in CO. Card games, puzzles, family games, STEM.", "both", "A")

add("Razzle Toys", "independent toy store", "Denver", "CO",
    "https://www.razzletoys.com/", "", "info@razzletoys.com", "general",
    "https://www.razzletoys.com/",
    "Denver area favorite 30+ years. Toys, games, puzzles, Ravensburger. 5910 S University Blvd.", "both", "A")

add("The Wizard's Chest", "toy store / costume shop", "Denver", "CO",
    "https://www.wizardschest.com/", "", "thewizard@wizardschest.com", "general",
    "https://www.wizardschest.com/",
    "Denver's magical toy store. Toys, games, TCG cards, puzzles. 451 Broadway.", "both", "A")

add("Timbuk Toys", "independent toy store chain", "Denver", "CO",
    "https://timbuktoys.com/", "", "info@timbuktoys.com", "general",
    "https://timbuktoys.com/",
    "Denver independent toy store chain. 3 locations in Denver metro. Toys, games, puzzles.", "both", "A")

add("Grandrabbit's Toy Shoppe", "independent toy store", "Boulder", "CO",
    "https://www.grtoys.com/", "", "info@grtoys.com", "general",
    "https://www.grtoys.com/",
    "Boulder's favorite toy store. Toys, puzzles, games, educational toys. 2525 Arapahoe Ave.", "both", "A")

add("Clothes Pony & Dandelion Toys", "toy store / children boutique", "Fort Collins", "CO",
    "https://clothespony.com/", "", "hello@clothespony.com", "general",
    "https://clothespony.com/",
    "Fort Collins specialty kids store. Puzzles, games, building toys, science kits.", "both", "A")

# ================================================================
# 10. Minneapolis / St. Paul
# ================================================================
add("Source Comics and Games", "comic / game store", "Minneapolis", "MN",
    "https://www.sourcecomicsandgames.com/", "", "info@sourcecomicsandgames.com", "general",
    "https://www.sourcecomicsandgames.com/",
    "Minneapolis' largest comic and game store. Board games, card games, comics, puzzles.", "card_games", "A")

add("Dreamers Vault Games", "board game store", "Minneapolis", "MN",
    "https://www.dreamersvault.com/", "", "info@dreamersvault.com", "general",
    "https://www.dreamersvault.com/",
    "Twin Cities board game store chain. Board games, card games, puzzles. Multiple locations.", "card_games", "A")

add("kiddywampus", "independent toy store", "Hopkins", "MN",
    "https://kiddywampus.com/", "", "hello@kiddywampus.com", "general",
    "https://kiddywampus.com/",
    "Minneapolis area indie toy store. Toys, puzzles, games, art supplies. Multiple MN locations.", "both", "A")

add("Hub Hobby & Toy", "toy store / hobby shop", "Richfield", "MN",
    "https://www.hubhobby.com/", "", "", "contact_form_only",
    "https://www.hubhobby.com/",
    "Twin Cities family toy and hobby store since 1949. Toys, puzzles, games. Good Toy Group member.", "both", "B",
    notes="Contact form only. Multiple locations.")

add("Levels Up Games", "board game store", "Roseville", "MN",
    "https://www.levelsuggames.com/", "", "info@levelsuggames.com", "general",
    "https://www.levelsuggames.com/",
    "Twin Cities board game store. Board games, card games, puzzles. Roseville MN.", "card_games", "A")

# ================================================================
# 11. Philadelphia / Pittsburgh
# ================================================================
add("The Philly Game Shop", "board game store", "Philadelphia", "PA",
    "https://www.phillygameshop.com/", "", "staff@phillygameshop.com", "general",
    "https://www.phillygameshop.com/",
    "Philly board game store. Board games, card games (MTG, Pokemon). 521-525 S 5th St.", "card_games", "A",
    notes="Already sent Phase 2. Duplicate protection in import.")

add("Red Caps Corner", "board game store", "Philadelphia", "PA",
    "https://www.redcapscorner.com/", "", "info@redcapscorner.com", "general",
    "https://www.redcapscorner.com/",
    "Philadelphia board game and comic store. Board games, card games, RPGs. 4048 Locust St.", "card_games", "A")

add("Phantom of the Attic", "comic / game store", "Pittsburgh", "PA",
    "https://www.phantomoftheattic.com/", "", "info@phantomoftheattic.com", "general",
    "https://www.phantomoftheattic.com/",
    "Pittsburgh comic and game store since 1982. Board games, card games, comics, RPGs. Multiple locations.", "card_games", "A")

add("Game Masters", "board game store", "Pittsburgh", "PA",
    "https://www.gamemasterspgh.com/", "", "info@gamemasterspgh.com", "general",
    "https://www.gamemasterspgh.com/",
    "Pittsburgh board game store. Board games, card games, puzzles. South Hills.", "card_games", "A")

# ================================================================
# 12. Washington DC / Arlington / Alexandria
# ================================================================
add("Labyrinth Game Shop", "board game store", "Washington", "DC",
    "https://www.labyrinthgameshop.com/", "", "info@labyrinthgameshop.com", "general",
    "https://www.labyrinthgameshop.com/",
    "DC board game store and cafe. Board games, card games. 645 Pennsylvania Ave SE, Eastern Market.", "card_games", "A")

add("Board & Brew", "board game store / cafe", "College Park", "MD",
    "https://www.boardandbrew.com/", "", "info@boardandbrew.com", "general",
    "https://www.boardandbrew.com/",
    "DC area board game cafe. Board games, card games, food/drink. College Park, MD.", "card_games", "A")

add("Comics & Gaming Outpost", "comic / game store", "Gainesville", "VA",
    "https://www.comicsgamingoutpost.com/", "", "info@comicsgamingoutpost.com", "general",
    "https://www.comicsgamingoutpost.com/",
    "Northern VA comic and game store. Board games, card games, comics, puzzles.", "card_games", "A")

add("Victory Comics", "comic / game store", "Falls Church", "VA",
    "https://www.victorycomics.com/", "", "info@victorycomics.com", "general",
    "https://www.victorycomics.com/",
    "DC area comic and game store. Board games, card games, comics. Falls Church, VA.", "card_games", "A")

add("The Curio Shoppe & Wizardry Store", "gift / game store", "Alexandria", "VA",
    "https://www.curioshoppealexandria.com/", "", "hello@curioshoppealexandria.com", "general",
    "https://www.curioshoppealexandria.com/",
    "Alexandria gift and game shop. Puzzles, games, gifts, curios. Old Town Alexandria.", "both", "A")

# ================================================================
# 13. Raleigh / Durham / Chapel Hill
# ================================================================
add("Atomic Empire", "board game store", "Durham", "NC",
    "https://www.atomicempire.com/", "", "info@atomicempire.com", "general",
    "https://www.atomicempire.com/",
    "Triangle area's largest game store. Board games, card games, RPGs, puzzles. 3400 Westgate Dr.", "card_games", "A")

add("Gamers Geek and Tavern", "board game store / tavern", "Raleigh", "NC",
    "https://www.gamersgeekandtavern.com/", "", "info@gamersgeekandtavern.com", "general",
    "https://www.gamersgeekandtavern.com/",
    "Raleigh board game tavern. Board games, card games. 307 W Tremont Ave.", "card_games", "B",
    notes="Game tavern format. Retail component unclear.")

add("Uncle Bob's Hobbies", "board game store", "Raleigh", "NC",
    "https://www.unclebobshobbies.com/", "", "info@unclebobshobbies.com", "general",
    "https://www.unclebobshobbies.com/",
    "Raleigh hobby and game store. Board games, card games, puzzles, RC. 3130 Capital Blvd.", "card_games", "A")

add("Chapel Hill Toys", "independent toy store", "Chapel Hill", "NC",
    "https://www.chapelhilltoys.com/", "", "info@chapelhilltoys.com", "general",
    "https://www.chapelhilltoys.com/",
    "Chapel Hill independent toy store. Toys, puzzles, games, educational toys. 179 E Franklin St.", "both", "A")

# ================================================================
# 14. Atlanta / Decatur
# ================================================================
add("My Parent's Basement", "board game store / bar", "Avondale Estates", "GA",
    "https://www.myparentsbasement.com/", "", "info@myparentsbasement.com", "general",
    "https://www.myparentsbasement.com/",
    "Atlanta area board game bar and store. Board games, card games, craft beer. Avondale Estates.", "card_games", "A")

add("Dr. No's Comics & Games", "comic / game store", "Marietta", "GA",
    "https://www.drnoscomics.com/", "", "info@drnoscomics.com", "general",
    "https://www.drnoscomics.com/",
    "Atlanta area comic and game store since 1985. Board games, card games, comics. Marietta.", "card_games", "A")

add("Titan Comics & Games", "comic / game store", "Atlanta", "GA",
    "https://www.titancomicsga.com/", "", "info@titancomicsga.com", "general",
    "https://www.titancomicsga.com/",
    "Atlanta comic and game store. Board games, card games, MTG, Pokemon, Flesh & Blood.", "card_games", "A")

add("Little Shop of Stories", "bookstore / gift shop", "Decatur", "GA",
    "https://www.littleshopofstories.com/", "", "info@littleshopofstories.com", "general",
    "https://www.littleshopofstories.com/",
    "Decatur independent bookstore with games and gifts. Puzzles, card games, toys. 133A E Court Sq.", "both", "A")

# ================================================================
# 15. Nashville / Franklin
# ================================================================
add("The Game Keep", "board game store", "Nashville", "TN",
    "https://www.thegamekeep.com/", "", "info@thegamekeep.com", "general",
    "https://www.thegamekeep.com/",
    "Nashville board game store. Board games, card games, puzzles, RPGs. 2136 Belcourt Ave.", "card_games", "A")

add("Next Level Games", "board game store", "Nashville", "TN",
    "https://www.nextlevelgamesnashville.com/", "", "staff@nextlevelgamesnashville.com", "general",
    "https://www.nextlevelgamesnashville.com/",
    "Nashville board game store. Board games, card games, TCGs. 5208 Tennessee Ave.", "card_games", "A")

add("Comic Asylum", "comic / game store", "Nashville", "TN",
    "https://www.comicasylum.com/", "", "info@comicasylum.com", "general",
    "https://www.comicasylum.com/",
    "Nashville comic and game store. Comics, board games, card games, collectibles. 5112 Nolensville Pk.", "card_games", "A")

# ================================================================
# 16. San Diego / Orange County
# ================================================================
add("Geppetto's Toys", "independent toy store chain", "San Diego", "CA",
    "https://geppettostoys.com/", "", "", "contact_form_only",
    "https://geppettostoys.com/",
    "Locally owned chain with 9 locations in San Diego. Board games, card games, puzzles, toys.", "both", "B",
    notes="9 locations. Contact form only.")

add("Gamezone", "board game store", "San Diego", "CA",
    "https://www.gamezonesd.com/", "", "info@gamezonesd.com", "general",
    "https://www.gamezonesd.com/",
    "San Diego board game store. Board games, card games. Multiple locations.", "card_games", "A")

add("TC's Rockets", "collectible / game store", "San Diego", "CA",
    "https://www.tcsrockets.com/", "", "info@tcsrockets.com", "general",
    "https://www.tcsrockets.com/",
    "San Diego collectible and game store. Sports cards, TCGs, board games.", "card_games", "B",
    notes="More collectible focused. Game section available.")

add("Shuffle & Cut", "board game store", "Orange", "CA",
    "https://www.shuffleandcut.com/", "", "info@shuffleandcut.com", "general",
    "https://www.shuffleandcut.com/",
    "Orange County board game store. Board games, card games, TCGs. 1911 E Chapman Ave.", "card_games", "A")

# ================================================================
# 17. Madison / Milwaukee
# ================================================================
add("I'm Board! Games & Family Fun", "board game store", "Madison", "WI",
    "https://www.imboardgames.com/", "", "info@imboardgames.com", "general",
    "https://www.imboardgames.com/",
    "Madison board game store. Board games, card games, puzzles. 3 locations. Campus, Middleton, Sun Prairie.", "card_games", "B",
    notes="Email from third-party FAB TCG directory. Website has contact form only.")

add("Pegasus Games", "board game store", "Madison", "WI",
    "https://www.pegasusgames.com/", "", "info@pegasusgames.com", "general",
    "https://www.pegasusgames.com/",
    "Madison board game store since 1980. Board games, card games, puzzles, RPGs. 6644 Odana Rd.", "card_games", "A")

add("Warhammer Madison", "board game / hobby store", "Madison", "WI",
    "https://www.warhammermadison.com/", "", "info@warhammermadison.com", "general",
    "https://www.warhammermadison.com/",
    "Madison hobby and game store. Miniatures, board games, card games, paints. 6316 Odana Rd.", "card_games", "A")

add("Game Universe", "board game store", "Milwaukee", "WI",
    "https://www.gameuniverse.com/", "", "info@gameuniverse.com", "general",
    "https://www.gameuniverse.com/",
    "Milwaukee board game store. Board games, card games, TCGs. Multiple locations in WI.", "card_games", "A")

add("Collectible Corner & Game Store", "comic / game store", "Milwaukee", "WI",
    "https://www.collectiblecornermke.com/", "", "info@collectiblecornermke.com", "general",
    "https://www.collectiblecornermke.com/",
    "Milwaukee comic and game store. Board games, card games, comics, collectibles.", "card_games", "A")

# ================================================================
# 18. Ann Arbor / Grand Rapids / Detroit suburbs
# ================================================================
add("Vault of Midnight", "game store / comic shop", "Ann Arbor", "MI",
    "https://www.vaultofmidnight.com/", "", "contact@vaultofmidnight.com", "general",
    "https://www.vaultofmidnight.com/",
    "Premier game store with 3 MI locations. Board games, card games, comics. Ann Arbor, Grand Rapids, Detroit.", "card_games", "A")

add("Sylvan Factory", "board game store", "Ann Arbor", "MI",
    "https://sylvanfactory.com/", "", "", "contact_form_only",
    "https://sylvanfactory.com/",
    "Ann Arbor community game store. Card games, tabletop games, board games. 2459 W Stadium Blvd.", "card_games", "B",
    notes="Contact form only.")

add("Fun4All Gaming Lounge", "board game store / lounge", "Grand Rapids", "MI",
    "https://www.fun4allgr.com/", "", "info@fun4allgr.com", "general",
    "https://www.fun4allgr.com/",
    "Grand Rapids board game lounge and store. Board games, card games. 1149 Wealthy St SE.", "card_games", "A")

add("Grand Lantern Games", "board game store", "Grand Rapids", "MI",
    "https://www.grandlanterngames.com/", "", "info@grandlanterngames.com", "general",
    "https://www.grandlanterngames.com/",
    "Grand Rapids board game store. Board games, card games, puzzles. 3015 Breton Rd SE.", "card_games", "A")

add("RIW Hobbies & Games", "toy / game / hobby store", "Livonia", "MI",
    "https://www.riwhobbies.com/", "", "info@riwhobbies.com", "general",
    "https://www.riwhobbies.com/",
    "Detroit area hobby and game store. Games, puzzles, models, RC, trains, LEGO. Livonia.", "both", "A")

# ================================================================
# 19. Phoenix / Scottsdale / Tempe
# ================================================================
add("Samurai Comics & Games", "comic / game store", "Phoenix", "AZ",
    "https://www.samuraicomics.com/", "", "info@samuraicomics.com", "general",
    "https://www.samuraicomics.com/",
    "Phoenix comic and game store. Board games, card games, comics. Multiple Phoenix locations.", "card_games", "A")

add("Imperial Outpost Games", "board game store", "Phoenix", "AZ",
    "https://www.imperialoutpostgames.com/", "", "info@imperialoutpostgames.com", "general",
    "https://www.imperialoutpostgames.com/",
    "Phoenix board game store. Board games, card games, TCGs, RPGs. 4920 W Thunderbird Rd.", "card_games", "A")

add("Game Depot", "board game store", "Tempe", "AZ",
    "https://www.gamedepotaz.com/", "", "info@gamedepotaz.com", "general",
    "https://www.gamedepotaz.com/",
    "Tempe board game store. Board games, card games, puzzles, RPGs. 3130 S McClintock Dr.", "card_games", "A")

add("Snakes & Lattes", "board game store / cafe", "Tempe", "AZ",
    "https://www.snakesandlattes.com/", "", "info@snakesandlattes.com", "general",
    "https://www.snakesandlattes.com/",
    "Tempe board game cafe. Board games, card games. Mill Ave in Tempe.", "card_games", "A")

add("Scottsdale Toy Company", "independent toy store", "Scottsdale", "AZ",
    "https://www.scottsdaletoyco.com/", "", "info@scottsdaletoyco.com", "general",
    "https://www.scottsdaletoyco.com/",
    "Scottsdale independent toy store. Toys, puzzles, games, gifts, STEM. Scottsdale Quarter.", "both", "A")

# ================================================================
# 20. Salt Lake City / Park City
# ================================================================
add("Game Haven", "board game store", "Salt Lake City", "UT",
    "https://www.gamehavenutah.com/", "", "info@gamehavenutah.com", "general",
    "https://www.gamehavenutah.com/",
    "SLC board game store. Board games, card games, puzzles. Multiple SLC locations.", "card_games", "A")

add("Oasis Games", "board game store", "Salt Lake City", "UT",
    "https://www.oasisgamesutah.com/", "", "info@oasisgamesutah.com", "general",
    "https://www.oasisgamesutah.com/",
    "Salt Lake City board game store. Board games, card games, puzzles, TCGs. 1516 S 1500 E.", "card_games", "A")

add("Hobby Hobbies", "toy / hobby store", "Salt Lake City", "UT",
    "https://www.blickhobbies.com/", "", "info@blickhobbies.com", "general",
    "https://www.blickhobbies.com/",
    "SLC area hobby store. Toys, games, puzzles, craft, LEGO. Multiple locations.", "both", "A")

add("Game Grid", "board game store", "Salt Lake City", "UT",
    "https://www.gamegridutah.com/", "", "info@gamegridutah.com", "general",
    "https://www.gamegridutah.com/",
    "Utah board game store chain. Board games, card games, puzzles. Multiple Utah locations.", "card_games", "A")

add("Park City Toy Lending Library", "toy store / gift shop", "Park City", "UT",
    "https://www.parkcitytoylibrary.com/", "", "info@parkcitytoylibrary.com", "general",
    "https://www.parkcitytoylibrary.com/",
    "Park City toy store. Toys, games, puzzles, family gifts.", "both", "B",
    notes="Small specialty toy store. Verify focus.")

# ================================================================
# Good Toy Group additional stores (previously unfetched)
# ================================================================
add("Happy Up Inc", "independent toy store", "Clayton", "MO",
    "https://www.happyupinc.com/", "", "help@happyupinc.com", "general",
    "https://www.happyupinc.com/",
    "St. Louis area independent toy store. Toys, puzzles, games, STEM. Clayton MO. Good Toy Group member.", "both", "A")

add("Learning Tree Toys", "independent toy store", "Prairie Village", "KS",
    "https://learningtreetoys.com/", "", "info@learningtreetoys.com", "general",
    "https://learningtreetoys.com/",
    "Kansas City area toy store. Toys, puzzles, games, STEM. Good Toy Group member.", "both", "A")

add("Circle of Knowledge", "educational toy store", "Sunset Hills", "MO",
    "https://www.circleofknowledge.com/", "", "info@circleofknowledge.com", "general",
    "https://www.circleofknowledge.com/",
    "St. Louis area educational toy store. Toys, puzzles, games, books. Good Toy Group member.", "both", "A")

# ================================================================
# EXISTING DB CHECK + IMPORT LOGIC
# ================================================================
print(f"Phase 4: {len(new_leads)} leads prepared for import")
print()

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Get existing data for dedup
cur.execute("SELECT domain_hash, email FROM leads")
existing = {}
for r in cur.fetchall():
    existing[r['domain_hash']] = r['email']

cur.execute("SELECT email FROM suppression_list")
suppressed_emails = set(r['email'] for r in cur.fetchall())

cur.execute("SELECT DISTINCT email FROM send_log WHERE status='sent'")
sent_emails = set(r['email'] for r in cur.fetchall())

inserted = 0
skipped_dup = 0
skipped_suppressed = 0
by_grade = {"A": 0, "B": 0, "C": 0}
by_city = {}
mx_no_mx = 0

for lead in new_leads:
    # Dedup
    d = domain_hash(lead["official_website"])
    if not d:
        d = f"{lead['store_name'].lower().strip()}_{lead['city'].lower().strip()}"
    if d in existing:
        print(f"  [DUP] {lead['store_name']}")
        skipped_dup += 1
        continue
    
    # Suppression check
    if lead["email"] and lead["email"] in suppressed_emails:
        print(f"  [SUPPRESSED] {lead['store_name']} ({lead['email']})")
        skipped_suppressed += 1
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
        existing[d] = lead["email"]
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
    except sqlite3.IntegrityError as e:
        print(f"  [ERR] {lead['store_name']}: {e}")
        skipped_dup += 1

conn.commit()
conn.close()

print(f"\n{'='*60}")
print(f"PHASE 4 IMPORT SUMMARY")
print(f"{'='*60}")
print(f"  Attempted: {len(new_leads)}")
print(f"  Inserted:  {inserted}")
print(f"  Duplicates: {skipped_dup}")
print(f"  Suppressed: {skipped_suppressed}")
print(f"\nBy Grade:")
for g in ["A", "B", "C"]:
    print(f"  Grade {g}: {by_grade.get(g, 0)}")
print(f"\nBy Region (top entries):")
for city, stats in sorted(by_city.items())[:15]:
    print(f"  {city:30s}: {stats['total']:2d} (A={stats['A']}, B={stats['B']}, C={stats['C']}, 📧={stats['with_email']})")

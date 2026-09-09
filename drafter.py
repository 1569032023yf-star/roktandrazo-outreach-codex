"""
Roktandrazo Outreach - Email Drafter
根据门店信息自动生成个性化 cold email
优先推广 卡游 (card games) 产品，附带拼图
"""

from config import PRODUCT_NAME, PRODUCT_TAGLINE, PRODUCT_WEBSITE, SENDER_NAME, SENDER_TITLE, PRODUCT_LINES

CARD_HIGHLIGHTS = "\n".join(f"  • {g}" for g in PRODUCT_LINES["card_games"][:4])


# ============================================================
# 邮件模板 — 卡游优先
# ============================================================

INITIAL_EMAIL_TEMPLATE = """Hi{greeting},

I'm Ian from {product_name} — we create fun family card games and giftable mini puzzles that are perfect for {store_type_label} like {store_name}.

Our card games are a hit with families, kids, and party-goers:

{CARD_HIGHLIGHTS}

{puzzle_hook}

We've found that stores in {city}, {state} do especially well with our products because {location_reason}.

{specific_connection}

Would you be open to checking out our wholesale catalog? I'd love to send over some samples or jump on a quick call.

Our website: {product_website}

Best regards,
{sender_name}
{sender_title}
"""

FOLLOWUP_1_TEMPLATE = """Hi{greeting},

Just following up on my note about {product_name} card games for {store_name}. Quick question — do you carry family card games or party games in your store currently?

{followup_hook}

Happy to send a free sample of our best-selling Capybara Squad or Math Dinos so you can see the quality.

Best,
{sender_name}
"""

FOLLOWUP_2_TEMPLATE = """Hi{greeting},

Last check-in — just wanted to make sure you saw my note about stocking {product_name} card games at {store_name}.

We offer:
  • Low minimum order (just 12 units to start)
  • 40-50% wholesale margin
  • Free display stand with first order
  • CPSIA & CE safety certified

If timing isn't right, no worries — just say the word and I'll leave you alone!

All the best,
{sender_name}
"""


def _get_greeting(lead: dict) -> str:
    store_name = lead.get("store_name", "there")
    return f" {store_name} team"


def _get_store_type_label(store_type: str) -> str:
    mapping = {
        "independent toy store": "independent toy stores",
        "puzzle/board game store": "puzzle and game shops",
        "gift shop": "gift shops",
        "museum store": "museum stores",
        "bookstore with gifts": "bookstores with gift sections",
        "national park gift shop": "national park gift shops",
        "craft/hobby store": "craft and hobby stores",
    }
    return mapping.get(store_type, store_type or "retail stores")


def _get_puzzle_hook(store_type: str) -> str:
    """拼图附加卖点 (卡游为主，拼图为辅)"""
    hooks = {
        "independent toy store": "We also carry beautifully designed mini puzzles (24 National Parks, Butterfly Symphony, and more) that fly off shelves as grab-and-go gifts.",
        "puzzle/board game store": "Beyond card games, our 1000-piece mini puzzles are a natural fit for your puzzle section — 7 themes including National Parks and World Heritage.",
        "gift shop": "Our mini puzzles are also one of our best-selling gift items — compact, gorgeous, and priced right for impulse buys.",
        "museum store": "We also offer museum-friendly 1000-piece puzzles in themes like National Parks, World Heritage, and Global City Tour — perfect for gift shops.",
        "bookstore with gifts": "Our card games appeal to family shoppers, and our mini puzzles make perfect add-on gifts for your curated section.",
        "national park gift shop": "Our 24 National Parks puzzle is a natural fit — visitors love taking home a keepsake of their trip. We also carry fun family card games.",
        "craft/hobby store": "Our card games and puzzles are a great crossover product for hobby and game sections.",
    }
    return hooks.get(store_type, "We also carry beautifully designed mini puzzles that make perfect giftable souvenirs.")


def _get_location_reason(city: str, state: str) -> str:
    tourist_keywords = {
        "asheville": "your location draws visitors looking for unique, locally-souvenir-worthy gifts",
        "bar harbor": "Acadia visitors are always looking for memorable take-home items",
        "sedona": "tourists in Sedona seek out distinctive, giftable mementos",
        "carmel": "Carmel's walkable downtown creates perfect impulse-buy moments",
        "taos": "Taos visitors appreciate artisan-quality gifts they can't find elsewhere",
        "savannah": "Savannah's charming streets bring in gift-seeking visitors year-round",
        "charleston": "Charleston's popularity as a destination means strong souvenir demand",
        "boulder": "Boulder's mix of locals and tourists creates steady demand for quality products",
        "portland": "Portland's gift culture values unique, well-crafted products",
        "austin": "Austin's vibrant scene drives demand for distinctive, giftable items",
        "nashville": "Nashville's tourism makes it a hot market for giftable souvenirs",
        "eureka springs": "Eureka Springs visitors love discovering unique shops and gifts",
        "cape cod": "Cape Cod summer crowds fuel demand for new, fun products every season",
        "stowe": "Stowe's year-round tourism means steady foot traffic for gift shops",
        "woodstock": "Woodstock's charming downtown draws shoppers looking for unique finds",
        "bend": "Bend's active community loves family-friendly games and puzzles",
        "taos": "Taos art-and-culture visitors appreciate quality, unique merchandise",
        "grand rapids": "Grand Rapids families love finding new games at local toy stores",
        "portsmouth": "Portsmouth's historic shopping district is perfect for giftable products",
        "lake geneva": "Lake Geneva's resort visitors are always shopping for fun souvenirs",
        "traverse city": "Traverse City's tourist season creates strong demand for gift items",
        "park city": "Park City's resort visitors love finding new games and souvenirs",
        "carmel-by-the-sea": "Carmel's walkable downtown creates perfect impulse-buy moments",
        "eureka springs": "Eureka Springs visitors love discovering unique shops and gifts",
    }
    city_lower = (city or "").lower()
    for key, reason in tourist_keywords.items():
        if key in city_lower:
            return reason
    return "your community values quality, fun family products"


def _get_specific_connection(lead: dict) -> str:
    reasons = []
    fit_reason = (lead.get("fit_reason") or "").lower()
    store_name = (lead.get("store_name") or "").lower()
    store_type = (lead.get("store_type") or "").lower()

    if "wholesale" in fit_reason:
        reasons.append("I noticed you already work with wholesale suppliers — our pricing is competitive and terms are flexible.")

    if "game" in store_name or "puzzle" in store_name:
        reasons.append("Since games and puzzles are core to your business, our card games would be a natural addition to your selection.")

    if "museum" in store_type:
        reasons.append("We've had great success with museum stores — our puzzles and educational card games complement museum merchandise beautifully.")

    if "national park" in store_type:
        reasons.append("Our 24 National Parks puzzle was literally designed for stores like yours — visitors love it.")

    if "toy" in store_type and "game" in store_type:
        reasons.append("Your mix of toys and games makes you a perfect partner for our card game line.")

    if "since" in fit_reason or "family" in fit_reason or "established" in fit_reason or "staple" in fit_reason:
        reasons.append("Your store's history shows you care about curating quality — our products would fit right in.")

    if reasons:
        return "One more thing — " + " ".join(reasons)
    return ""


def draft_initial_email(lead: dict) -> dict:
    """为首封邮件生成草稿"""
    store_name = lead.get("store_name", "your store")
    city = lead.get("city", "")
    state = lead.get("state", "")
    store_type = lead.get("store_type", "")

    greeting = _get_greeting(lead)
    store_type_label = _get_store_type_label(store_type)
    puzzle_hook = _get_puzzle_hook(store_type)
    location_reason = _get_location_reason(city, state)
    specific_connection = _get_specific_connection(lead)

    # 主题行 — 卡游优先
    subject = f"Card games & puzzles for {store_name} — wholesale from {PRODUCT_NAME}"

    body = INITIAL_EMAIL_TEMPLATE.format(
        subject=subject,
        greeting=greeting,
        product_name=PRODUCT_NAME,
        product_tagline=PRODUCT_TAGLINE,
        product_website=PRODUCT_WEBSITE,
        store_type_label=store_type_label,
        store_name=store_name,
        CARD_HIGHLIGHTS=CARD_HIGHLIGHTS,
        puzzle_hook=puzzle_hook,
        city=city,
        state=state,
        location_reason=location_reason,
        specific_connection=specific_connection,
        sender_name=SENDER_NAME,
        sender_title=SENDER_TITLE,
    )

    return {
        "subject": subject,
        "body_text": body.strip(),
        "email_type": "initial",
    }


def draft_followup_email(lead: dict, followup_number: int, original_subject: str = "") -> dict:
    store_name = lead.get("store_name", "your store")
    store_type = lead.get("store_type", "")
    greeting = _get_greeting(lead)

    if followup_number == 1:
        followup_hook = _get_puzzle_hook(store_type)
        body = FOLLOWUP_1_TEMPLATE.format(
            original_subject=original_subject,
            greeting=greeting,
            product_name=PRODUCT_NAME,
            store_name=store_name,
            followup_hook=followup_hook,
            sender_name=SENDER_NAME,
        )
        return {
            "subject": f"Re: {original_subject}",
            "body_text": body.strip(),
            "email_type": "followup_1",
        }
    elif followup_number == 2:
        body = FOLLOWUP_2_TEMPLATE.format(
            original_subject=original_subject,
            greeting=greeting,
            product_name=PRODUCT_NAME,
            store_name=store_name,
            sender_name=SENDER_NAME,
        )
        return {
            "subject": f"Re: {original_subject}",
            "body_text": body.strip(),
            "email_type": "followup_2",
        }
    return None


if __name__ == "__main__":
    from db import get_leads
    leads = get_leads(status='drafted', limit=2)
    for lead in leads:
        email = draft_initial_email(lead)
        print(f"=== {lead['store_name']} ({lead.get('email','')}) ===")
        print(f"Subject: {email['subject']}")
        print(email['body_text'])
        print()

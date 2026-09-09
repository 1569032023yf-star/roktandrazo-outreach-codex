"""
Roktandrazo US Retail Store Outreach System - Configuration
"""
import os

# ============================================================
# 产品信息
# ============================================================
PRODUCT_NAME = "Roktandrazo"
PRODUCT_TYPE = "family card games, educational card games, giftable mini puzzles"
PRODUCT_WEBSITE = "https://roktandrazo.com/"
PRODUCT_TAGLINE = "Fun family card games and beautifully crafted mini puzzles"
PRODUCT_LINES = {
    "card_games": [
        "Capybara Squad card games (party + strategy)",
        "Math Dinos — educational math card game",
        "Recipe Rush — cooking matching game",
        "What&Why? Guess The Animal card game",
        "6 in 1 Kids Card Games Pack",
        "Sweet Match memory game",
    ],
    "puzzles": [
        "24 National Parks jigsaw puzzle",
        "Butterfly Symphony laser iridescent puzzle",
        "Flower Speaks glitter puzzle",
        "World Heritage puzzle",
        "Global City Tour puzzle",
    ]
}

# ============================================================
# 发件人信息
# ============================================================
SENDER_NAME = "Ian"
SENDER_EMAIL = "bqniki@gmail.com"
SENDER_TITLE = "Wholesale & Partnerships"

# ============================================================
# SMTP 配置 (Gmail 示例)
# ============================================================
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "bqniki@gmail.com"
# P7：密码不再硬编码。生产通过 .env / 环境变量 BD_SMTP_PASSWORD 提供；
# 为空时功能 fail-closed（见 get_smtp_password()），绝无硬编码回退。
SMTP_PASSWORD = os.environ.get("BD_SMTP_PASSWORD", "")


def get_smtp_password() -> str:
    """返回 SMTP 密码；未配置时 fail-closed（抛错提示缺 env）。

    任何发送路径必须先调用本函数，禁止直接使用可能为空的 SMTP_PASSWORD。
    """
    pwd = SMTP_PASSWORD
    if not pwd:
        raise RuntimeError(
            "SMTP_PASSWORD 未配置：请设置环境变量 BD_SMTP_PASSWORD（生产通过 .env 提供），"
            "否则邮件发送功能不可用（fail-closed）。"
        )
    return pwd

# ============================================================
# 发信策略
# ============================================================
MAX_EMAILS_PER_DAY = 30          # 每天最大发送量
MIN_DELAY_BETWEEN_SECONDS = 60   # 邮件之间最小间隔(秒)
EMAIL_DAILY_SEND_WINDOW = {
    "start_hour": 9,   # 美东时间 9am
    "end_hour": 17,    # 美东时间 5pm
}

# ============================================================
# 线索采集策略
# ============================================================
TARGET_CITIES_PER_WEEK = 20
TARGET_STORES_PER_CITY = 10

STORE_TYPE_PRIORITY = {
    "independent toy store": 1,
    "puzzle/board game store": 1,
    "gift shop": 2,
    "museum store": 2,
    "bookstore with gifts": 3,
    "national park gift shop": 2,
    "craft/hobby store": 3,
}

SEARCH_KEYWORDS = [
    "independent toy store {city} puzzles",
    "puzzle shop {city} jigsaw",
    "gift shop {city} puzzles games",
    "museum store {city} gifts puzzles",
    "bookstore {city} gift section puzzles",
    "souvenir shop {city} puzzles",
    "board game store {city} puzzles",
    "hobby store {city} puzzles crafts",
]

# ============================================================
# 评分阈值
# ============================================================
MIN_SCORE_TO_EMAIL = "B"  # 只有 B 级以上才发邮件
AUTO_EMAIL_GRADES = ["A"]  # A 级自动发送，B 级需确认

# ============================================================
# 邮件追踪
# ============================================================
FOLLOW_UP_DAYS = 5          # 首次跟进天数
SECOND_FOLLOW_UP_DAYS = 10  # 二次跟进天数
MAX_FOLLOW_UPS = 2          # 最大跟进次数

# ============================================================
# 数据库
# ============================================================
DB_PATH = "data/leads.db"

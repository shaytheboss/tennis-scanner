"""Configuration and constants loaded from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram ────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    raise RuntimeError(
        "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID. "
        "Set them in .env locally or in Railway Variables."
    )

# ─── Tennis alert thresholds ─────────────────────────────────
THRESHOLDS = {
    "lead_5_0":         0.03,
    "lead_5_1":         0.06,
    "lead_2_0_sets":    0.06,
    "lead_2_0_and_3_0": 0.02,
}

STAT_PROBS = {
    "lead_5_0":         0.98,
    "lead_5_1":         0.95,
    "lead_2_0_sets":    0.95,
    "lead_2_0_and_3_0": 0.99,
}

# ─── Sofascore ───────────────────────────────────────────────
SOFASCORE_LIVE_URL = "https://api.sofascore.com/api/v1/sport/tennis/events/live"
SOFASCORE_EVENT_URL = "https://api.sofascore.com/api/v1/event/{event_id}"
SOFASCORE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.sofascore.com/",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# ─── Polymarket ──────────────────────────────────────────────
POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com"
POLYMARKET_CLOB_WSS = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# Football tag ID on Polymarket gamma API.
# To find the correct value: GET https://gamma-api.polymarket.com/tags and look for slug="soccer"
# Override with env var POLYMARKET_FOOTBALL_TAG_ID if the default doesn't return results.
POLYMARKET_FOOTBALL_TAG_ID = int(os.getenv("POLYMARKET_FOOTBALL_TAG_ID", "0"))

# ─── Tennis runtime ──────────────────────────────────────────
POLL_INTERVAL_SECONDS = 2
MARKET_REFRESH_SECONDS = 600
ALERT_COOLDOWN_SECONDS = 3600
WS_PING_INTERVAL = 10
FUZZY_MATCH_THRESHOLD = 0.85

# ─── Football runtime ─────────────────────────────────────────
FOOTBALL_POLL_INTERVAL_SECONDS = int(os.getenv("FOOTBALL_POLL_INTERVAL_SECONDS", "30"))
FOOTBALL_MARKET_REFRESH_SECONDS = int(os.getenv("FOOTBALL_MARKET_REFRESH_SECONDS", "600"))
FOOTBALL_ALERT_COOLDOWN_SECONDS = int(os.getenv("FOOTBALL_ALERT_COOLDOWN_SECONDS", "3600"))

# Conditions for a football alert:
#   - leading team's goal advantage >= FOOTBALL_MIN_GOAL_LEAD
#   - current minute >= FOOTBALL_MIN_MINUTE
#   - Polymarket win price for leading team <= FOOTBALL_MAX_LEADER_PRICE
FOOTBALL_MIN_GOAL_LEAD = int(os.getenv("FOOTBALL_MIN_GOAL_LEAD", "2"))
FOOTBALL_MIN_MINUTE = int(os.getenv("FOOTBALL_MIN_MINUTE", "90"))
FOOTBALL_MAX_LEADER_PRICE = float(os.getenv("FOOTBALL_MAX_LEADER_PRICE", "0.99"))

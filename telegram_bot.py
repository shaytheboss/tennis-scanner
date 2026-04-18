"""Telegram notification handler."""
import aiohttp

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from detector import Alert

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


async def send_alert(alert: Alert) -> bool:
    market_url = f"https://polymarket.com/event/{alert.condition_id}"
    message = (
        f"🎾 <b>Tennis Opportunity</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚔️ {alert.player1} vs {alert.player2}\n"
        f"📍 <b>{alert.leader}</b> {alert.situation_text}\n"
        f"🏆 {alert.tournament}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Market price: <b>{alert.price_leader*100:.0f}¢</b>\n"
        f"📊 Stat probability: {alert.statistical_prob*100:.0f}%\n"
        f"✅ Edge: <b>+{alert.edge*100:.1f}%</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f'<a href="{market_url}">Open in Polymarket →</a>'
    )
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TELEGRAM_API,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    return True
                body = await resp.text()
                print(f"[telegram error] status={resp.status}, body={body[:200]}")
                return False
    except Exception as e:
        print(f"[telegram error] {e}")
        return False


async def send_startup_message(num_markets: int) -> bool:
    message = (
        f"🟢 <b>Tennis Scanner online</b>\n"
        f"Tracking {num_markets} live Polymarket tennis markets.\n"
        f"Monitoring Sofascore for opportunities..."
    )
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TELEGRAM_API, json=payload, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"[telegram startup error] {e}")
        return False


async def send_error_message(error_text: str) -> bool:
    message = f"🔴 <b>Scanner error</b>\n<code>{error_text[:500]}</code>"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TELEGRAM_API, json=payload, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                return resp.status == 200
    except Exception:
        return False

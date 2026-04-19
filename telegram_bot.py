"""Telegram notification handler."""
from typing import Optional

import aiohttp

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from detector import Alert
from sofascore_feed import MatchState
from polymarket_feed import Market
from football_detector import FootballAlert

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


async def _send(message: str) -> bool:
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TELEGRAM_API,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    print(f"[telegram] ✅ sent ({len(message)} chars)")
                    return True
                body = await resp.text()
                print(f"[telegram error] status={resp.status}, body={body[:300]}")
                return False
    except Exception as e:
        print(f"[telegram error] {e}")
        return False


async def send_match_started(match: MatchState, market: Optional[Market]) -> bool:
    if market:
        p1_pct = round(market.price_p1 * 100)
        p2_pct = round(market.price_p2 * 100)
        market_url = f"https://polymarket.com/event/{market.condition_id}"
        message = (
            f"🎾 <b>Match started — now tracking</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚔️ <b>{match.player1}</b> vs <b>{match.player2}</b>\n"
            f"🏆 {match.tournament} ({match.format.upper()})\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 Polymarket odds:\n"
            f"  • {match.player1}: <b>{p1_pct}¢</b>\n"
            f"  • {match.player2}: <b>{p2_pct}¢</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f'<a href="{market_url}">Open in Polymarket →</a>'
        )
    else:
        message = (
            f"🎾 <b>Match started (no Polymarket market found)</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚔️ <b>{match.player1}</b> vs <b>{match.player2}</b>\n"
            f"🏆 {match.tournament} ({match.format.upper()})"
        )
    return await _send(message)


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
    return await _send(message)


async def send_football_alert(alert: FootballAlert) -> bool:
    market_url = f"https://polymarket.com/event/{alert.condition_id}"
    message = (
        f"⚽ <b>Football Alert — {alert.league}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏟 <b>{alert.team1}</b> {alert.score1}–{alert.score2} <b>{alert.team2}</b>\n"
        f"⏱ Minute: <b>{alert.minute}'</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 Leading team: <b>{alert.leader_team}</b>\n"
        f"💰 Polymarket win price: <b>{alert.leader_price*100:.0f}¢</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f'<a href="{market_url}">Open in Polymarket →</a>'
    )
    return await _send(message)


async def send_startup_message(num_tennis: int, num_football: int) -> bool:
    message = (
        f"🟢 <b>Scanner online</b>\n"
        f"🎾 {num_tennis} Polymarket tennis markets\n"
        f"⚽ {num_football} Polymarket football markets\n"
        f"Monitoring ESPN for opportunities..."
    )
    return await _send(message)


async def send_error_message(error_text: str) -> bool:
    message = f"🔴 <b>Scanner error</b>\n<code>{error_text[:500]}</code>"
    return await _send(message)

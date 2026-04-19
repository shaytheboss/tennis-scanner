"""Main entry point."""
import asyncio
import time

from sofascore_feed import fetch_live_matches, run_sports_feed
from polymarket_feed import fetch_active_tennis_markets, subscribe_prices, Market
from matcher import match_players
from detector import check_opportunity
from telegram_bot import send_alert, send_startup_message, send_error_message, send_match_started
from config import POLL_INTERVAL_SECONDS, MARKET_REFRESH_SECONDS, ALERT_COOLDOWN_SECONDS


async def scanner_loop(markets: list[Market], alerted: dict[str, float], tracked: set):
    unmatched_logged = set()

    while True:
        try:
            live_matches = await fetch_live_matches()

            for match_id, match in live_matches.items():
                market = match_players(match, markets)

                if not market:
                    if match_id not in unmatched_logged:
                        print(f"[unmatched] {match.player1} vs {match.player2}")
                        unmatched_logged.add(match_id)
                    continue

                # שלח הודעת התחלה פעם אחת
                if match_id not in tracked:
                    tracked.add(match_id)
                    print(f"[tracker] new match: {match.player1} vs {match.player2} | p1={market.price_p1:.2f} p2={market.price_p2:.2f}")
                    await send_match_started(match, market)

                alert = check_opportunity(match, market)
                if not alert:
                    continue

                alert_key = f"{match_id}_{alert.situation_type}"
                now = time.time()
                if now - alerted.get(alert_key, 0) < ALERT_COOLDOWN_SECONDS:
                    continue

                success = await send_alert(alert)
                if success:
                    alerted[alert_key] = now
                    print(f"[{alert.timestamp}] ✅ {alert.leader} {alert.situation_text} | edge={alert.edge*100:.1f}%")

            # נקה משחקים שנגמרו מה-tracked
            ended = tracked - set(live_matches.keys())
            for match_id in ended:
                tracked.discard(match_id)
                print(f"[tracker] match ended: {match_id}")

            now = time.time()
            for key in list(alerted.keys()):
                if now - alerted[key] > ALERT_COOLDOWN_SECONDS:
                    del alerted[key]

            if len(unmatched_logged) > 500:
                unmatched_logged.clear()

        except Exception as e:
            print(f"[scanner_loop error] {e}")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def market_refresh_loop(markets: list[Market]):
    while True:
        await asyncio.sleep(MARKET_REFRESH_SECONDS)
        try:
            fresh = await fetch_active_tennis_markets()
            if fresh:
                existing_prices = {m.condition_id: (m.price_p1, m.price_p2) for m in markets}
                for fm in fresh:
                    if fm.condition_id in existing_prices:
                        fm.price_p1, fm.price_p2 = existing_prices[fm.condition_id]
                markets.clear()
                markets.extend(fresh)
                print(f"[refresh] {len(markets)} markets")
        except Exception as e:
            print(f"[refresh error] {e}")


async def main():
    print("🎾 Tennis Scanner starting...")

    markets = await fetch_active_tennis_markets()
    print(f"✅ Found {len(markets)} active Polymarket tennis markets")

    alerted: dict[str, float] = {}
    tracked: set = set()

    await send_startup_message(len(markets))

    try:
        await asyncio.gather(
            run_sports_feed(),
            subscribe_prices(markets),
            scanner_loop(markets, alerted, tracked),
            market_refresh_loop(markets),
        )
    except Exception as e:
        err_msg = f"Fatal error: {e}"
        print(f"[FATAL] {err_msg}")
        await send_error_message(err_msg)
        raise


if __name__ == "__main__":
    asyncio.run(main())

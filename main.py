"""Main entry point."""
import asyncio
import time

from sofascore_feed import fetch_live_matches, run_sports_feed
from polymarket_feed import fetch_active_tennis_markets, fetch_active_football_markets, subscribe_prices, Market
from matcher import match_players
from detector import check_opportunity
from football_feed import run_football_feed, fetch_live_football
from football_matcher import match_teams
from football_detector import check_football_opportunity
from telegram_bot import (
    send_alert,
    send_startup_message,
    send_error_message,
    send_match_started,
    send_football_alert,
)
from config import (
    POLL_INTERVAL_SECONDS,
    MARKET_REFRESH_SECONDS,
    ALERT_COOLDOWN_SECONDS,
    FOOTBALL_POLL_INTERVAL_SECONDS,
    FOOTBALL_MARKET_REFRESH_SECONDS,
    FOOTBALL_ALERT_COOLDOWN_SECONDS,
)


async def scanner_loop(markets: list[Market], alerted: dict[str, float], tracked: set):
    start_alerted: set = set()
    unmatched_logged: set = set()

    while True:
        try:
            live_matches = await fetch_live_matches()

            for match_id, match in live_matches.items():
                tracked.add(match_id)

                market = match_players(match, markets)

                if not market:
                    if match_id not in unmatched_logged:
                        print(f"[unmatched] {match.player1} vs {match.player2}")
                        unmatched_logged.add(match_id)
                    continue

                if match_id not in start_alerted:
                    start_alerted.add(match_id)
                    print(
                        f"[tracker] new match: {match.player1} vs {match.player2}"
                        f" | p1={market.price_p1:.2f} p2={market.price_p2:.2f}"
                    )
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
                    print(
                        f"[{alert.timestamp}] ✅ {alert.leader} {alert.situation_text}"
                        f" | edge={alert.edge*100:.1f}%"
                    )

            ended = tracked - set(live_matches.keys())
            for match_id in ended:
                tracked.discard(match_id)
                start_alerted.discard(match_id)
                unmatched_logged.discard(match_id)
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
                print(f"[refresh tennis] {len(markets)} markets")
        except Exception as e:
            print(f"[refresh tennis error] {e}")


async def football_scanner_loop(markets: list[Market], alerted: dict[str, float]):
    unmatched_logged: set = set()

    while True:
        try:
            live_matches = await fetch_live_football()

            for match_id, match in live_matches.items():
                market = match_teams(match, markets)

                if not market:
                    if match_id not in unmatched_logged:
                        print(f"[football unmatched] {match.team1} vs {match.team2}")
                        unmatched_logged.add(match_id)
                    continue

                alert = check_football_opportunity(match, market)
                if not alert:
                    continue

                alert_key = f"football_{match_id}"
                now = time.time()
                if now - alerted.get(alert_key, 0) < FOOTBALL_ALERT_COOLDOWN_SECONDS:
                    continue

                success = await send_football_alert(alert)
                if success:
                    alerted[alert_key] = now
                    print(
                        f"[football] ✅ {match.team1} {match.score1}-{match.score2} {match.team2}"
                        f" | min {match.minute} | price={alert.leader_price:.2f}"
                    )

            ended = unmatched_logged - set(live_matches.keys())
            for match_id in ended:
                unmatched_logged.discard(match_id)

            if len(unmatched_logged) > 500:
                unmatched_logged.clear()

        except Exception as e:
            print(f"[football scanner error] {e}")

        await asyncio.sleep(FOOTBALL_POLL_INTERVAL_SECONDS)


async def football_market_refresh_loop(markets: list[Market]):
    while True:
        await asyncio.sleep(FOOTBALL_MARKET_REFRESH_SECONDS)
        try:
            fresh = await fetch_active_football_markets()
            if fresh:
                existing_prices = {m.condition_id: (m.price_p1, m.price_p2) for m in markets}
                for fm in fresh:
                    if fm.condition_id in existing_prices:
                        fm.price_p1, fm.price_p2 = existing_prices[fm.condition_id]
                markets.clear()
                markets.extend(fresh)
                print(f"[refresh football] {len(markets)} markets")
        except Exception as e:
            print(f"[refresh football error] {e}")


async def main():
    print("🎾⚽ Scanner starting...")

    tennis_markets = await fetch_active_tennis_markets()
    print(f"✅ Found {len(tennis_markets)} active Polymarket tennis markets")

    football_markets = await fetch_active_football_markets()
    print(f"✅ Found {len(football_markets)} active Polymarket football markets")

    alerted: dict[str, float] = {}
    tracked: set = set()

    print(f"[main] sending startup message to Telegram...")
    try:
        ok = await send_startup_message(len(tennis_markets), len(football_markets))
        print(f"[main] startup message {'sent ✅' if ok else 'FAILED ❌'}")
    except Exception as e:
        print(f"[main] startup message error: {e}")

    try:
        await asyncio.gather(
            # Tennis
            run_sports_feed(),
            subscribe_prices(tennis_markets),
            scanner_loop(tennis_markets, alerted, tracked),
            market_refresh_loop(tennis_markets),
            # Football
            run_football_feed(),
            subscribe_prices(football_markets),
            football_scanner_loop(football_markets, alerted),
            football_market_refresh_loop(football_markets),
        )
    except Exception as e:
        err_msg = f"Fatal error: {e}"
        print(f"[FATAL] {err_msg}")
        await send_error_message(err_msg)
        raise


if __name__ == "__main__":
    asyncio.run(main())

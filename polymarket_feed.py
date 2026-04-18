"""Polymarket feed - REST discovery + WebSocket price updates."""
import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
import websockets

from config import POLYMARKET_GAMMA_URL, POLYMARKET_CLOB_WSS, WS_PING_INTERVAL


@dataclass
class Market:
    condition_id: str
    token_id_p1: str
    token_id_p2: str
    player1_name: str
    player2_name: str
    price_p1: float = 0.5
    price_p2: float = 0.5
    last_updated: float = field(default_factory=time.time)


def _parse_players_from_question(question: str) -> Optional[tuple[str, str]]:
    q = question.strip()
    for sep in [" vs. ", " vs ", " v. ", " v "]:
        if sep in q:
            parts = q.split(sep)
            if len(parts) == 2:
                p1 = parts[0].strip(" ?.!")
                p2 = parts[1].strip(" ?.!")
                for prefix in ["Will ", "will "]:
                    if p1.startswith(prefix):
                        p1 = p1[len(prefix):]
                return (p1, p2)
    if "beat" in q.lower():
        idx = q.lower().find("beat")
        before = q[:idx].strip()
        after = q[idx + 4:].strip(" ?.!")
        for prefix in ["Will ", "will "]:
            if before.startswith(prefix):
                before = before[len(prefix):].strip()
        return (before, after)
    return None


async def fetch_active_tennis_markets() -> list[Market]:
    url = f"{POLYMARKET_GAMMA_URL}/markets"
    params = {"active": "true", "closed": "false", "tag_slug": "tennis", "limit": 200}
    markets = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    print(f"[polymarket gamma] status {resp.status}")
                    return []
                data = await resp.json()

        items = data if isinstance(data, list) else data.get("data", [])
        for item in items:
            try:
                question = item.get("question", "")
                players = _parse_players_from_question(question)
                if not players:
                    continue
                raw_tokens = item.get("clobTokenIds", "[]")
                token_ids = json.loads(raw_tokens) if isinstance(raw_tokens, str) else raw_tokens
                if not token_ids or len(token_ids) < 2:
                    continue
                raw_prices = item.get("outcomePrices", "[0.5, 0.5]")
                prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
                markets.append(Market(
                    condition_id=item.get("conditionId", ""),
                    token_id_p1=str(token_ids[0]),
                    token_id_p2=str(token_ids[1]),
                    player1_name=players[0],
                    player2_name=players[1],
                    price_p1=float(prices[0]) if prices else 0.5,
                    price_p2=float(prices[1]) if len(prices) > 1 else 0.5,
                ))
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                print(f"[polymarket parse] skipping: {e}")
    except Exception as e:
        print(f"[polymarket gamma error] {e}")
    return markets


async def subscribe_prices(markets: list[Market]):
    while True:
        try:
            token_to_market = {}
            token_to_side = {}
            for m in markets:
                token_to_market[m.token_id_p1] = m
                token_to_market[m.token_id_p2] = m
                token_to_side[m.token_id_p1] = "p1"
                token_to_side[m.token_id_p2] = "p2"

            asset_ids = list(token_to_market.keys())
            if not asset_ids:
                print("[polymarket ws] no markets, sleeping 60s")
                await asyncio.sleep(60)
                continue

            print(f"[polymarket ws] connecting, {len(asset_ids)} tokens")
            async with websockets.connect(
                POLYMARKET_CLOB_WSS,
                ping_interval=WS_PING_INTERVAL,
                ping_timeout=30,
            ) as ws:
                await ws.send(json.dumps({"type": "market", "assets_ids": asset_ids}))
                async for raw_msg in ws:
                    try:
                        msg = json.loads(raw_msg)
                    except json.JSONDecodeError:
                        continue
                    events = msg if isinstance(msg, list) else [msg]
                    for ev in events:
                        asset_id = ev.get("asset_id")
                        if not asset_id or asset_id not in token_to_market:
                            continue
                        price = None
                        if "price" in ev:
                            try:
                                price = float(ev["price"])
                            except (ValueError, TypeError):
                                pass
                        elif "best_bid" in ev and "best_ask" in ev:
                            try:
                                price = (float(ev["best_bid"]) + float(ev["best_ask"])) / 2
                            except (ValueError, TypeError):
                                pass
                        if price is None:
                            continue
                        market = token_to_market[asset_id]
                        side = token_to_side[asset_id]
                        if side == "p1":
                            market.price_p1 = price
                        else:
                            market.price_p2 = price
                        market.last_updated = time.time()

        except websockets.ConnectionClosed as e:
            print(f"[polymarket ws] closed: {e}, reconnecting in 5s")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[polymarket ws error] {e}, reconnecting in 10s")
            await asyncio.sleep(10)

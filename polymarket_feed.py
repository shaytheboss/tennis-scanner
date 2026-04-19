"""Polymarket feed - sports events discovery + WebSocket price updates."""
import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
import websockets

from config import (
    POLYMARKET_GAMMA_URL,
    POLYMARKET_CLOB_WSS,
    POLYMARKET_FOOTBALL_TAG_ID,
    WS_PING_INTERVAL,
)


@dataclass
class Market:
    condition_id: str
    token_id_p1: str
    token_id_p2: str
    player1_name: str
    player2_name: str
    game_id: str = ""
    price_p1: float = 0.5
    price_p2: float = 0.5
    last_updated: float = field(default_factory=time.time)


def _parse_players(home: str, away: str, question: str) -> Optional[tuple[str, str]]:
    if home and away:
        return (home, away)
    q = question.strip()
    for sep in [" vs. ", " vs ", " v. ", " v "]:
        if sep in q:
            parts = q.split(sep, 1)
            if len(parts) == 2:
                p1 = parts[0].strip(" ?.!")
                p2 = parts[1].strip(" ?.!")
                for prefix in ["Will ", "will "]:
                    if p1.startswith(prefix):
                        p1 = p1[len(prefix):]
                return (p1, p2)
    return None


async def _fetch_events(params: dict) -> list[Market]:
    """Shared helper: fetch events from gamma API and parse into Market objects."""
    markets = []
    url = f"{POLYMARKET_GAMMA_URL}/events"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"Accept": "application/json"},
            ) as resp:
                print(f"[polymarket] {url} params={params} → {resp.status}")
                if resp.status != 200:
                    print(f"[polymarket] error: {await resp.text()[:200]}")
                    return []

                data = await resp.json()
                items = data if isinstance(data, list) else data.get("data", [])
                print(f"[polymarket] {len(items)} events found")

                for event in items:
                    try:
                        event_markets = event.get("markets", [])
                        for item in event_markets:
                            home = item.get("homeTeam", "")
                            away = item.get("awayTeam", "")
                            question = item.get("question", "")
                            game_id = str(item.get("gameId", event.get("id", "")))

                            players = _parse_players(home, away, question)
                            if not players:
                                continue

                            raw_tokens = item.get("clobTokenIds", "[]")
                            if isinstance(raw_tokens, str):
                                token_ids = json.loads(raw_tokens)
                            else:
                                token_ids = raw_tokens or []

                            if len(token_ids) < 2:
                                continue

                            raw_prices = item.get("outcomePrices", "[0.5,0.5]")
                            if isinstance(raw_prices, str):
                                prices = json.loads(raw_prices)
                            else:
                                prices = raw_prices or [0.5, 0.5]

                            markets.append(Market(
                                condition_id=item.get("conditionId", ""),
                                token_id_p1=str(token_ids[0]),
                                token_id_p2=str(token_ids[1]),
                                player1_name=players[0],
                                player2_name=players[1],
                                game_id=game_id,
                                price_p1=float(prices[0]) if prices else 0.5,
                                price_p2=float(prices[1]) if len(prices) > 1 else 0.5,
                            ))

                    except Exception as e:
                        print(f"[polymarket parse] {e}")
                        continue

        except Exception as e:
            print(f"[polymarket] error: {e}")

    return markets


async def fetch_active_tennis_markets() -> list[Market]:
    markets = await _fetch_events({
        "tag_id": 864,
        "active": "true",
        "closed": "false",
        "limit": 100,
    })
    print(f"[polymarket] total {len(markets)} tennis markets")
    return markets


async def fetch_active_football_markets() -> list[Market]:
    """Query Polymarket events API for active football/soccer markets.

    Uses POLYMARKET_FOOTBALL_TAG_ID from config (env var POLYMARKET_FOOTBALL_TAG_ID).
    If set to 0 (default), discovers the soccer tag automatically via the /tags endpoint.
    To find the correct tag ID manually: GET https://gamma-api.polymarket.com/tags
    """
    tag_id = POLYMARKET_FOOTBALL_TAG_ID

    if tag_id == 0:
        tag_id = await _discover_soccer_tag_id()

    if tag_id == 0:
        print("[polymarket] could not determine football tag_id, skipping football markets")
        return []

    markets = await _fetch_events({
        "tag_id": tag_id,
        "active": "true",
        "closed": "false",
        "limit": 100,
    })
    print(f"[polymarket] total {len(markets)} football markets")
    return markets


async def _discover_soccer_tag_id() -> int:
    """Fetch /tags from gamma API and return the ID for soccer/football."""
    url = f"{POLYMARKET_GAMMA_URL}/tags"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return 0
                tags = await resp.json()
                for tag in tags:
                    slug = tag.get("slug", "").lower()
                    label = tag.get("label", "").lower()
                    if slug in ("soccer", "football") or label in ("soccer", "football"):
                        tag_id = int(tag.get("id", 0))
                        print(f"[polymarket] discovered football tag_id={tag_id} (slug={slug})")
                        return tag_id
        except Exception as e:
            print(f"[polymarket tags] {e}")
    return 0


async def subscribe_prices(markets: list[Market]):
    """WebSocket price subscription for any list of Market objects."""
    while True:
        if not markets:
            print("[polymarket ws] no markets, sleeping 60s")
            await asyncio.sleep(60)
            continue

        try:
            token_to_market = {}
            token_to_side = {}
            for m in markets:
                token_to_market[m.token_id_p1] = m
                token_to_market[m.token_id_p2] = m
                token_to_side[m.token_id_p1] = "p1"
                token_to_side[m.token_id_p2] = "p2"

            asset_ids = list(token_to_market.keys())
            print(f"[polymarket ws] connecting, {len(asset_ids)} tokens")

            async with websockets.connect(
                POLYMARKET_CLOB_WSS,
                ping_interval=WS_PING_INTERVAL,
                ping_timeout=30,
            ) as ws:
                await ws.send(json.dumps({
                    "type": "market",
                    "assets_ids": asset_ids,
                }))

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
                        if token_to_side[asset_id] == "p1":
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

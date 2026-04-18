"""Polymarket feed - sports events discovery + WebSocket price updates."""
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
    game_id: str = ""
    price_p1: float = 0.5
    price_p2: float = 0.5
    last_updated: float = field(default_factory=time.time)


def _parse_players(home: str, away: str, question: str) -> Optional[tuple[str, str]]:
    """Extract player names from homeTeam/awayTeam or question string."""
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


async def fetch_active_tennis_markets() -> list[Market]:
    """Query Polymarket sports events API for active tennis markets."""
    markets = []

    # ATP=45, WTA=46, Challenger=? (try common IDs)
    sport_ids = [45, 46]

    async with aiohttp.ClientSession() as session:
        for sport_id in sport_ids:
            url = f"{POLYMARKET_GAMMA_URL}/sports/events?id={sport_id}"
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={"Accept": "application/json"},
                ) as resp:
                    print(f"[polymarket] {url} → {resp.status}")
                    if resp.status != 200:
                        continue

                    data = await resp.json()

                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        items = data.get("data", data.get("events", []))
                    else:
                        continue

                    print(f"[polymarket] sport_id={sport_id} → {len(items)} events")

                    if items:

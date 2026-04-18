"""Sofascore live tennis feed - polling every 2s."""
import asyncio
import time
from dataclasses import dataclass
from typing import Optional

import aiohttp

from config import SOFASCORE_LIVE_URL, SOFASCORE_HEADERS


@dataclass
class MatchState:
    match_id: str
    player1: str
    player2: str
    sets_p1: int
    sets_p2: int
    games_p1: int
    games_p2: int
    current_set: int
    format: str  # "bo3" or "bo5"
    tournament: str
    timestamp: float


def _parse_format(event: dict) -> str:
    tournament_name = (event.get("tournament", {}).get("name") or "").lower()
    category = (event.get("tournament", {}).get("category", {}).get("name") or "").lower()
    grand_slams = ["australian open", "roland garros", "french open", "wimbledon", "us open"]
    is_grand_slam = any(gs in tournament_name for gs in grand_slams)
    is_men = "men" in category or "atp" in category
    return "bo5" if (is_grand_slam and is_men) else "bo3"


def _parse_event(event: dict) -> Optional[MatchState]:
    try:
        sport_slug = (
            event.get("tournament", {})
            .get("category", {})
            .get("sport", {})
            .get("slug", "")
        )
        if sport_slug != "tennis":
            return None

        status_type = event.get("status", {}).get("type", "")
        if status_type != "inprogress":
            return None

        home_score = event.get("homeScore", {}) or {}
        away_score = event.get("awayScore", {}) or {}

        sets_p1 = 0
        sets_p2 = 0
        current_set = 1
        games_p1 = 0
        games_p2 = 0

        for i in range(1, 6):
            p1 = home_score.get(f"period{i}")
            p2 = away_score.get(f"period{i}")
            if p1 is None or p2 is None:
                break
            if (p1 >= 6 or p2 >= 6) and abs(p1 - p2) >= 2:
                if p1 > p2:
                    sets_p1 += 1
                else:
                    sets_p2 += 1
            elif p1 == 7 or p2 == 7:
                if p1 > p2:
                    sets_p1 += 1
                else:
                    sets_p2 += 1
            else:
                current_set = i
                games_p1 = p1
                games_p2 = p2
                break

        return MatchState(
            match_id=str(event["id"]),
            player1=event["homeTeam"]["name"],
            player2=event["awayTeam"]["name"],
            sets_p1=sets_p1,
            sets_p2=sets_p2,
            games_p1=games_p1,
            games_p2=games_p2,
            current_set=current_set,
            format=_parse_format(event),
            tournament=event.get("tournament", {}).get("name", ""),
            timestamp=time.time(),
        )
    except (KeyError, TypeError, ValueError) as e:
        print(f"[sofascore parse error] {e} for event {event.get('id')}")
        return None


async def fetch_live_matches(session: aiohttp.ClientSession) -> dict[str, MatchState]:
    try:
        async with session.get(
            SOFASCORE_LIVE_URL,
            headers=SOFASCORE_HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 429:
                print("[sofascore] rate limited, sleeping 5s")
                await asyncio.sleep(5)
                return {}
            if resp.status == 403:
                print("[sofascore] 403 forbidden - headers may need update")
                await asyncio.sleep(5)
                return {}
            if resp.status != 200:
                print(f"[sofascore] unexpected status {resp.status}")
                return {}

            data = await resp.json()
            events = data.get("events", [])
            matches = {}
            for event in events:
                match = _parse_event(event)
                if match:
                    matches[match.match_id] = match
            return matches

    except asyncio.TimeoutError:
        print("[sofascore] timeout")
        return {}
    except Exception as e:
        print(f"[sofascore error] {e}")
        return {}

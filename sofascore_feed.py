"""Live tennis feed via ESPN API - polling every 5s."""
import asyncio
import json
import time
from dataclasses import dataclass
from typing import Optional

import aiohttp

ESPN_URLS = [
    "http://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard",
    "http://site.api.espn.com/apis/site/v2/sports/tennis/wta/scoreboard",
]

ESPN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}


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
    format: str
    tournament: str
    timestamp: float


def _parse_format(tournament: str) -> str:
    grand_slams = ["australian open", "roland garros", "french open", "wimbledon", "us open"]
    return "bo5" if any(gs in tournament.lower() for gs in grand_slams) else "bo3"


def _parse_espn_event(event: dict) -> Optional[MatchState]:
    try:
        status_type = event.get("status", {}).get("type", {})
        if status_type.get("name") not in ("STATUS_IN_PROGRESS",):
            return None

        competitions = event.get("competitions", [])
        if not competitions:
            return None

        comp = competitions[0]
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            return None

        home = competitors[0]
        away = competitors[1]

        player1 = home.get("athlete", {}).get("displayName", "")
        player2 = away.get("athlete", {}).get("displayName", "")

        if not player1 or not player2:
            return None

        match_id = str(event.get("id", ""))
        tournament = event.get("name", "")

        home_lines = home.get("linescores", [])
        away_lines = away.get("linescores", [])

        sets_p1 = 0
        sets_p2 = 0
        games_p1 = 0
        games_p2 = 0
        current_set = 1

        for i, (h, a) in enumerate(zip(home_lines, away_lines)):
            s1 = int(h.get("value", 0) or 0)
            s2 = int(a.get("value", 0) or 0)

            is_complete = (
                (max(s1, s2) >= 6 and abs(s1 - s2) >= 2) or
                max(s1, s2) == 7
            )

            if is_complete:
                if s1 > s2:
                    sets_p1 += 1
                else:
                    sets_p2 += 1
                current_set = i + 2
            else:
                games_p1 = s1
                games_p2 = s2
                current_set = i + 1
                break

        return MatchState(
            match_id=match_id,
            player1=player1,
            player2=player2,
            sets_p1=sets_p1,
            sets_p2=sets_p2,
            games_p1=games_p1,
            games_p2=games_p2,
            current_set=current_set,
            format=_parse_format(tournament),
            tournament=tournament,
            timestamp=time.time(),
        )

    except Exception as e:
        print(f"[espn parse error] {e}")
        return None


_live_matches: dict[str, MatchState] = {}
_last_live_count = -1


async def fetch_live_matches(session=None) -> dict[str, MatchState]:
    return dict(_live_matches)


async def run_sports_feed():
    global _live_matches, _last_live_count

    print("[espn] starting feed")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                new_matches = {}

                for url in ESPN_URLS:
                    try:
                        async with session.get(
                            url,
                            headers=ESPN_HEADERS,
                            timeout=aiohttp.ClientTimeout(total=10),
                        ) as resp:
                            if resp.status != 200:
                                print(f"[espn] {url} → {resp.status}")
                                continue

                            data = await resp.json()
                            events = data.get("events", [])

                            for event in events:
                                match = _parse_espn_event(event)
                                if match:
                                    new_matches[match.match_id] = match

                    except Exception as e:
                        print(f"[espn error] {url}: {e}")
                        continue

                _live_matches = new_matches

                # הדפס רק כשמספר המשחקים משתנה
                if len(new_matches) != _last_live_count:
                    _last_live_count = len(new_matches)
                    if new_matches:
                        names = ", ".join(f"{m.player1} vs {m.player2}" for m in new_matches.values())
                        print(f"[espn] {len(new_matches)} live: {names}")
                    else:
                        print("[espn] no live matches")

            except Exception as e:
                print(f"[espn feed error] {e}")

            await asyncio.sleep(5)

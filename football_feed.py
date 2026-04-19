"""Live football feed via ESPN API - polling every 30s."""
import asyncio
import time
from dataclasses import dataclass
from typing import Optional

import aiohttp

from config import FOOTBALL_POLL_INTERVAL_SECONDS

ESPN_FOOTBALL_LEAGUES = [
    ("eng.1",    "Premier League"),
    ("esp.1",    "La Liga"),
    ("ger.1",    "Bundesliga"),
    ("ita.1",    "Serie A"),
    ("fra.1",    "Ligue 1"),
    ("UEFA.CL",  "Champions League"),
    ("UEFA.EL",  "Europa League"),
    ("usa.1",    "MLS"),
]

ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"
ESPN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}


@dataclass
class FootballMatch:
    match_id: str
    team1: str
    team2: str
    score1: int
    score2: int
    minute: int
    league: str
    timestamp: float


def _parse_minute(display_clock: str) -> int:
    """Parse minute from strings like '87:00', '90:00+2', '45:00+3'."""
    try:
        return int(display_clock.split(":")[0])
    except (ValueError, AttributeError):
        return 0


def _parse_football_event(event: dict, league_name: str) -> Optional[FootballMatch]:
    try:
        status = event.get("status", {})
        if status.get("type", {}).get("name") != "STATUS_IN_PROGRESS":
            return None

        competitions = event.get("competitions", [])
        if not competitions:
            return None

        competitors = competitions[0].get("competitors", [])
        if len(competitors) < 2:
            return None

        home, away = None, None
        for c in competitors:
            if c.get("homeAway") == "home":
                home = c
            else:
                away = c
        if not home or not away:
            home, away = competitors[0], competitors[1]

        team1 = home.get("team", {}).get("displayName", "")
        team2 = away.get("team", {}).get("displayName", "")
        if not team1 or not team2:
            return None

        score1 = int(home.get("score", 0) or 0)
        score2 = int(away.get("score", 0) or 0)
        minute = _parse_minute(status.get("displayClock", "0:00"))

        return FootballMatch(
            match_id=str(event.get("id", "")),
            team1=team1,
            team2=team2,
            score1=score1,
            score2=score2,
            minute=minute,
            league=league_name,
            timestamp=time.time(),
        )
    except Exception as e:
        print(f"[football parse error] {e}")
        return None


_live_football: dict[str, FootballMatch] = {}


async def fetch_live_football() -> dict[str, FootballMatch]:
    return dict(_live_football)


async def run_football_feed():
    global _live_football
    print("[football] starting feed")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                new_matches: dict[str, FootballMatch] = {}

                for league_slug, league_name in ESPN_FOOTBALL_LEAGUES:
                    url = ESPN_BASE_URL.format(league=league_slug)
                    try:
                        async with session.get(
                            url,
                            headers=ESPN_HEADERS,
                            timeout=aiohttp.ClientTimeout(total=10),
                        ) as resp:
                            if resp.status != 200:
                                continue
                            data = await resp.json()
                            for event in data.get("events", []):
                                match = _parse_football_event(event, league_name)
                                if match:
                                    new_matches[match.match_id] = match
                    except Exception as e:
                        print(f"[football] {league_slug}: {e}")

                _live_football = new_matches

                if new_matches:
                    for m in new_matches.values():
                        print(
                            f"[football] ⚽ {m.team1} {m.score1}-{m.score2} {m.team2}"
                            f" | min {m.minute} | {m.league}"
                        )
                else:
                    print("[football] no live matches")

            except Exception as e:
                print(f"[football feed error] {e}")

            await asyncio.sleep(FOOTBALL_POLL_INTERVAL_SECONDS)

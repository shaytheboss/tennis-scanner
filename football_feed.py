"""Live football feed.

Primary source: Sofascore API (global coverage, all leagues).
Fallback: ESPN soccer scoreboard for 30+ leagues if Sofascore is blocked.
"""
import asyncio
import time as _time
from dataclasses import dataclass
from typing import Optional

import aiohttp

from config import SOFASCORE_HEADERS, FOOTBALL_POLL_INTERVAL_SECONDS

SOFASCORE_FOOTBALL_URL = "https://api.sofascore.com/api/v1/sport/football/events/live"
SOFASCORE_RETRY_SECONDS = 300  # retry Sofascore every 5 minutes after a block

ESPN_FOOTBALL_LEAGUES = [
    # Top European
    ("eng.1",   "Premier League"),
    ("esp.1",   "La Liga"),
    ("ger.1",   "Bundesliga"),
    ("ita.1",   "Serie A"),
    ("fra.1",   "Ligue 1"),
    ("ned.1",   "Eredivisie"),
    ("por.1",   "Primeira Liga"),
    ("tur.1",   "Süper Lig"),
    ("bel.1",   "Belgian Pro League"),
    ("sco.1",   "Scottish Premiership"),
    ("gre.1",   "Super League Greece"),
    ("rus.1",   "Russian Premier League"),
    ("ukr.1",   "Ukrainian Premier League"),
    ("aut.1",   "Austrian Bundesliga"),
    ("sui.1",   "Swiss Super League"),
    ("den.1",   "Superliga Denmark"),
    ("swe.1",   "Allsvenskan"),
    ("nor.1",   "Eliteserien"),
    ("cze.1",   "Czech First League"),
    ("pol.1",   "Ekstraklasa"),
    ("rou.1",   "Liga 1 Romania"),
    ("cro.1",   "HNL Croatia"),
    ("srb.1",   "Super Liga Serbia"),
    # European cups
    ("UEFA.CL",  "Champions League"),
    ("UEFA.EL",  "Europa League"),
    ("UEFA.CONF", "Conference League"),
    # Middle East
    ("isr.1",   "Israeli Premier League"),
    ("sau.1",   "Saudi Pro League"),
    ("uae.1",   "UAE Arabian Gulf League"),
    # Americas
    ("usa.1",   "MLS"),
    ("mex.1",   "Liga MX"),
    ("bra.1",   "Brasileirao"),
    ("arg.1",   "Argentine Primera"),
    ("col.1",   "Liga Colombiana"),
    ("chi.1",   "Primera Chile"),
    ("uru.1",   "Uruguayan Primera"),
    ("ecu.1",   "Liga Pro Ecuador"),
    # Asia
    ("jpn.1",   "J1 League"),
    ("kor.1",   "K League 1"),
    ("chn.1",   "Chinese Super League"),
    ("aus.1",   "A-League"),
]

ESPN_FOOTBALL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}
ESPN_FOOTBALL_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard"


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


def _minute_from_sofascore(status: dict, time_data: dict) -> int:
    desc = status.get("description", "")
    if "'" in desc:
        try:
            main = desc.split("'")[0].strip()
            if "+" in main:
                parts = main.split("+")
                return int(parts[0]) + int(parts[1])
            return int(main)
        except (ValueError, IndexError):
            pass

    period = status.get("period", 1)
    start_ts = time_data.get("currentPeriodStartTimestamp", 0)
    if start_ts:
        elapsed = int((_time.time() - start_ts) / 60)
        if period == 1:
            return min(elapsed, 45)
        elif period == 2:
            return 45 + min(elapsed, 45)
        elif period == 3:
            return 90 + min(elapsed, 15)
        elif period == 4:
            return 105 + min(elapsed, 15)
    return 0


def _minute_from_espn(status: dict) -> int:
    clock = status.get("displayClock", "0:00")
    try:
        return int(clock.split(":")[0])
    except (ValueError, AttributeError):
        return 0


def _parse_sofascore_football(event: dict) -> Optional[FootballMatch]:
    try:
        status = event.get("status", {})
        status_type = status.get("type", "")
        if isinstance(status_type, dict):
            status_name = status_type.get("name", status_type.get("code", ""))
        else:
            status_name = str(status_type)
        if status_name not in ("inprogress", "halftime"):
            return None

        team1 = event.get("homeTeam", {}).get("name", "")
        team2 = event.get("awayTeam", {}).get("name", "")
        if not team1 or not team2:
            return None

        score1 = int(event.get("homeScore", {}).get("current", 0) or 0)
        score2 = int(event.get("awayScore", {}).get("current", 0) or 0)

        if status_name == "halftime":
            minute = 45
        else:
            minute = _minute_from_sofascore(status, event.get("time", {}))

        league = event.get("tournament", {}).get("name", "Unknown")
        return FootballMatch(
            match_id=str(event.get("id", "")),
            team1=team1,
            team2=team2,
            score1=score1,
            score2=score2,
            minute=minute,
            league=league,
            timestamp=_time.time(),
        )
    except Exception as e:
        print(f"[football parse error] {e}")
        return None


def _parse_espn_football(event: dict, league_name: str) -> Optional[FootballMatch]:
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

        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        team1 = home.get("team", {}).get("displayName", "")
        team2 = away.get("team", {}).get("displayName", "")
        if not team1 or not team2:
            return None

        score1 = int(home.get("score", 0) or 0)
        score2 = int(away.get("score", 0) or 0)
        minute = _minute_from_espn(status)

        return FootballMatch(
            match_id=f"espn_{event.get('id', '')}",
            team1=team1,
            team2=team2,
            score1=score1,
            score2=score2,
            minute=minute,
            league=league_name,
            timestamp=_time.time(),
        )
    except Exception as e:
        print(f"[espn football parse error] {e}")
        return None


_live_football: dict[str, FootballMatch] = {}


async def fetch_live_football() -> dict[str, FootballMatch]:
    return dict(_live_football)


async def _fetch_sofascore(session: aiohttp.ClientSession) -> Optional[dict[str, FootballMatch]]:
    try:
        async with session.get(
            SOFASCORE_FOOTBALL_URL,
            headers=SOFASCORE_HEADERS,
            timeout=aiohttp.ClientTimeout(total=8),
        ) as resp:
            if resp.status != 200:
                print(f"[football] Sofascore blocked ({resp.status}), using ESPN fallback")
                return None
            data = await resp.json()
            matches = {}
            for event in data.get("events", []):
                m = _parse_sofascore_football(event)
                if m:
                    matches[m.match_id] = m
            print(f"[football] Sofascore ✅ {len(matches)} live matches (of {len(data.get('events',[]))} events)")
            return matches
    except Exception as e:
        print(f"[football] Sofascore error: {e}, using ESPN fallback")
        return None


async def _fetch_espn(session: aiohttp.ClientSession) -> dict[str, FootballMatch]:
    matches: dict[str, FootballMatch] = {}
    for slug, league_name in ESPN_FOOTBALL_LEAGUES:
        url = ESPN_FOOTBALL_BASE.format(league=slug)
        try:
            async with session.get(
                url,
                headers=ESPN_FOOTBALL_HEADERS,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                for event in data.get("events", []):
                    m = _parse_espn_football(event, league_name)
                    if m:
                        matches[m.match_id] = m
        except Exception:
            continue
    print(f"[football] ESPN fallback: {len(matches)} live matches across {len(ESPN_FOOTBALL_LEAGUES)} leagues")
    return matches


async def run_football_feed():
    global _live_football
    print("[football] starting feed (Sofascore → ESPN fallback)")

    sofascore_blocked_until = 0.0

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                now = _time.time()
                if now >= sofascore_blocked_until:
                    result = await _fetch_sofascore(session)
                    if result is None:
                        sofascore_blocked_until = now + SOFASCORE_RETRY_SECONDS
                        new_matches = await _fetch_espn(session)
                    else:
                        sofascore_blocked_until = 0.0
                        new_matches = result
                else:
                    new_matches = await _fetch_espn(session)

                _live_football = new_matches

                if new_matches:
                    for m in new_matches.values():
                        print(
                            f"[football] ⚽ {m.team1} {m.score1}-{m.score2} {m.team2}"
                            f" | min {m.minute} | {m.league}"
                        )
                else:
                    print(f"[football] no live matches")

            except Exception as e:
                print(f"[football feed error] {e}")

            await asyncio.sleep(FOOTBALL_POLL_INTERVAL_SECONDS)

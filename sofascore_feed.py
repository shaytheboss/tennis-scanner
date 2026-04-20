"""Live tennis feed.

Primary source: Sofascore API (global coverage).
Fallback: ESPN ATP + WTA scoreboard if Sofascore is blocked.
"""
import asyncio
import time as _time
from dataclasses import dataclass
from typing import Optional

import aiohttp

from config import SOFASCORE_LIVE_URL, SOFASCORE_HEADERS

ESPN_TENNIS_URLS = [
    ("http://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard", "ATP"),
    ("http://site.api.espn.com/apis/site/v2/sports/tennis/wta/scoreboard", "WTA"),
]
ESPN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

SOFASCORE_RETRY_SECONDS = 300  # retry Sofascore every 5 minutes after a block


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


def _parse_sofascore_event(event: dict) -> Optional[MatchState]:
    try:
        status = event.get("status", {})
        status_type = status.get("type", "")
        if isinstance(status_type, dict):
            status_name = status_type.get("name", status_type.get("code", ""))
        else:
            status_name = str(status_type)
        if status_name != "inprogress":
            return None

        player1 = event.get("homeTeam", {}).get("name", "")
        player2 = event.get("awayTeam", {}).get("name", "")
        if not player1 or not player2:
            return None

        match_id = str(event.get("id", ""))
        tournament = event.get("tournament", {}).get("name", "")
        home_score = event.get("homeScore", {})
        away_score = event.get("awayScore", {})

        sets_p1 = sets_p2 = games_p1 = games_p2 = 0
        current_set = 1

        for i in range(1, 6):
            h = home_score.get(f"period{i}")
            a = away_score.get(f"period{i}")
            if h is None or a is None:
                break
            h, a = int(h), int(a)
            complete = (max(h, a) >= 6 and abs(h - a) >= 2) or max(h, a) == 7
            if complete:
                if h > a:
                    sets_p1 += 1
                else:
                    sets_p2 += 1
                current_set = i + 1
            else:
                games_p1, games_p2, current_set = h, a, i
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
            timestamp=_time.time(),
        )
    except Exception as e:
        print(f"[sofascore parse error] {e}")
        return None


def _parse_espn_event(event: dict) -> Optional[MatchState]:
    try:
        if event.get("status", {}).get("type", {}).get("name") != "STATUS_IN_PROGRESS":
            return None

        comp = (event.get("competitions") or [{}])[0]
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            return None

        home, away = competitors[0], competitors[1]
        player1 = home.get("athlete", {}).get("displayName", "")
        player2 = away.get("athlete", {}).get("displayName", "")
        if not player1 or not player2:
            return None

        match_id = str(event.get("id", ""))
        tournament = event.get("name", "")
        home_lines = home.get("linescores", [])
        away_lines = away.get("linescores", [])

        sets_p1 = sets_p2 = games_p1 = games_p2 = 0
        current_set = 1

        for i, (h_obj, a_obj) in enumerate(zip(home_lines, away_lines)):
            h = int(h_obj.get("value", 0) or 0)
            a = int(a_obj.get("value", 0) or 0)
            complete = (max(h, a) >= 6 and abs(h - a) >= 2) or max(h, a) == 7
            if complete:
                if h > a:
                    sets_p1 += 1
                else:
                    sets_p2 += 1
                current_set = i + 2
            else:
                games_p1, games_p2, current_set = h, a, i + 1
                break

        return MatchState(
            match_id=f"espn_{match_id}",
            player1=player1,
            player2=player2,
            sets_p1=sets_p1,
            sets_p2=sets_p2,
            games_p1=games_p1,
            games_p2=games_p2,
            current_set=current_set,
            format=_parse_format(tournament),
            tournament=tournament,
            timestamp=_time.time(),
        )
    except Exception as e:
        print(f"[espn tennis parse error] {e}")
        return None


_live_matches: dict[str, MatchState] = {}
_last_live_count = -1


async def fetch_live_matches(session=None) -> dict[str, MatchState]:
    return dict(_live_matches)


async def _fetch_sofascore(session: aiohttp.ClientSession) -> Optional[dict[str, MatchState]]:
    try:
        async with session.get(
            SOFASCORE_LIVE_URL,
            headers=SOFASCORE_HEADERS,
            timeout=aiohttp.ClientTimeout(total=8),
        ) as resp:
            if resp.status != 200:
                print(f"[sofascore] blocked ({resp.status}), using ESPN fallback")
                return None
            data = await resp.json()
            matches = {}
            for event in data.get("events", []):
                m = _parse_sofascore_event(event)
                if m:
                    matches[m.match_id] = m
            print(f"[sofascore] ✅ {len(matches)} live matches")
            return matches
    except Exception as e:
        print(f"[sofascore] error: {e}, using ESPN fallback")
        return None


async def _fetch_espn(session: aiohttp.ClientSession) -> dict[str, MatchState]:
    matches = {}
    for url, tour in ESPN_TENNIS_URLS:
        try:
            async with session.get(
                url,
                headers=ESPN_HEADERS,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    print(f"[espn tennis] {tour} → {resp.status}")
                    continue
                data = await resp.json()
                events = data.get("events", [])
                live = 0
                for event in events:
                    m = _parse_espn_event(event)
                    if m:
                        matches[m.match_id] = m
                        live += 1
                print(f"[espn tennis] {tour}: {len(events)} events, {live} live")
        except Exception as e:
            print(f"[espn tennis] {tour} error: {e}")
    return matches


async def run_sports_feed():
    global _live_matches, _last_live_count
    print("[tennis] starting feed (Sofascore → ESPN fallback)")

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

                _live_matches = new_matches

                if len(new_matches) != _last_live_count:
                    _last_live_count = len(new_matches)
                    if new_matches:
                        for m in new_matches.values():
                            print(
                                f"[tennis] 🎾 LIVE: {m.player1} vs {m.player2}"
                                f" | sets {m.sets_p1}-{m.sets_p2}"
                                f" | games {m.games_p1}-{m.games_p2}"
                                f" | {m.tournament}"
                            )
                    else:
                        print("[tennis] no live matches")

            except Exception as e:
                print(f"[tennis feed error] {e}")

            await asyncio.sleep(5)

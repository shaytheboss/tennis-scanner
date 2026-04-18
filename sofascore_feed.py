"""Live tennis feed via Polymarket sports WebSocket."""
import asyncio
import json
import time
from dataclasses import dataclass
from typing import Optional

import websockets

POLYMARKET_SPORTS_WSS = "wss://ws-live-data.polymarket.com"

TENNIS_LEAGUES = {"atp", "wta", "challenger", "itf", "tennis"}


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


def _parse_format(league: str, tournament: str) -> str:
    grand_slams = ["australian open", "roland garros", "french open", "wimbledon", "us open"]
    is_grand_slam = any(gs in tournament.lower() for gs in grand_slams)
    is_men = league.lower() in {"atp", "challenger"}
    return "bo5" if (is_grand_slam and is_men) else "bo3"


def _parse_score(score_str: str, period: str) -> tuple[int, int, int, int, int]:
    """
    Parse score like "6-2, 3-1" into sets and games.
    Returns: sets_p1, sets_p2, games_p1, games_p2, current_set
    """
    if not score_str:
        return 0, 0, 0, 0, 1

    try:
        set_scores = [s.strip() for s in score_str.split(",")]
        sets_p1 = 0
        sets_p2 = 0
        games_p1 = 0
        games_p2 = 0
        current_set = 1

        for i, set_score in enumerate(set_scores):
            if "-" not in set_score:
                continue
            parts = set_score.split("-")
            s1 = int(parts[0].strip())
            s2 = int(parts[1].strip().split("(")[0])

            is_complete = (
                (max(s1, s2) >= 6 and abs(s1 - s2) >= 2) or
                (max(s1, s2) == 7)
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

        return sets_p1, sets_p2, games_p1, games_p2, current_set

    except (ValueError, IndexError):
        return 0, 0, 0, 0, 1


def _parse_message(msg: dict) -> Optional[MatchState]:
    try:
        league = msg.get("leagueAbbreviation", "").lower()
        if league not in TENNIS_LEAGUES:
            return None

        status = msg.get("status", "").lower()
        if status != "inprogress":
            return None

        if msg.get("ended", False):
            return None

        game_id = str(msg.get("gameId", ""))
        player1 = msg.get("homeTeam", "")
        player2 = msg.get("awayTeam", "")
        score_str = msg.get("score", "")
        period = msg.get("period", "S1")

        if not player1 or not player2:
            return None

        sets_p1, sets_p2, games_p1, games_p2, current_set = _parse_score(score_str, period)

        try:
            if period.startswith("S"):
                current_set = int(period[1:])
        except (ValueError, IndexError):
            pass

        tournament = league.upper()

        return MatchState(
            match_id=game_id,
            player1=player1,
            player2=player2,
            sets_p1=sets_p1,
            sets_p2=sets_p2,
            games_p1=games_p1,
            games_p2=games_p2,
            current_set=current_set,
            format=_parse_format(league, tournament),
            tournament=tournament,
            timestamp=time.time(),
        )

    except Exception as e:
        print(f"[sports ws parse error] {e}")
        return None


_live_matches: dict[str, MatchState] = {}


async def fetch_live_matches(session=None) -> dict[str, MatchState]:
    return dict(_live_matches)


async def run_sports_feed():
    """Connect to Polymarket sports WebSocket and keep _live_matches updated."""
    global _live_matches

    while True:
        try:
            print(f"[sports ws] connecting to {POLYMARKET_SPORTS_WSS}")
            async with websockets.connect(
                POLYMARKET_SPORTS_WSS,
                ping_interval=None,
            ) as ws:
                print("[sports ws] connected")
                async for raw in ws:
                    if raw == "ping":
                        await ws.send("pong")
                        continue

                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    match = _parse_message(msg)
                    if match:
                        _live_matches[match.match_id] = match
                        print(f"[sports ws] {match.player1} vs {match.player2} | {match.sets_p1}-{match.sets_p2} sets | {match.games_p1}-{match.games_p2} games")
                    else:
                        game_id = str(msg.get("gameId", ""))
                        if game_id and msg.get("ended", False):
                            _live_matches.pop(game_id, None)

        except websockets.ConnectionClosed as e:
            print(f"[sports ws] closed: {e}, reconnecting in 5s")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[sports ws error] {e}, reconnecting in 10s")
            await asyncio.sleep(10)

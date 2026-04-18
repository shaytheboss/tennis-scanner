"""Live tennis feed via Flashscore (unofficial) - polling every 2s."""
import asyncio
import time
from dataclasses import dataclass
from typing import Optional
import aiohttp

from config import SOFASCORE_HEADERS


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


FLASHSCORE_URL = "https://local.flashscore.com/x/feed/f_1_0_3_en_1"

FLASHSCORE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/plain, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.flashscore.com/",
    "X-fsign": "SW9D1eZo",
    "Origin": "https://www.flashscore.com",
}

# Tennis sport ID in Flashscore is 2
TENNIS_SPORT_ID = "2"


def _parse_flashscore_line(line: str) -> Optional[dict]:
    """Parse a single Flashscore data line into a dict."""
    try:
        parts = line.split("¬")
        data = {}
        for part in parts:
            if "÷" in part:
                key, _, val = part.partition("÷")
                data[key] = val
        return data if data else None
    except Exception:
        return None


def _parse_format(tournament: str) -> str:
    grand_slams = ["australian open", "roland garros", "french open", "wimbledon", "us open"]
    t_lower = tournament.lower()
    return "bo5" if any(gs in t_lower for gs in grand_slams) else "bo3"


async def fetch_live_matches(session: aiohttp.ClientSession) -> dict[str, MatchState]:
    """Fetch live tennis matches from Flashscore."""
    try:
        async with session.get(
            FLASHSCORE_URL,
            headers=FLASHSCORE_HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status == 403:
                print("[flashscore] 403 forbidden")
                await asyncio.sleep(5)
                return {}
            if resp.status != 200:
                print(f"[flashscore] status {resp.status}")
                return {}

            text = await resp.text(encoding="utf-8", errors="replace")

        matches = {}
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue

            data = _parse_flashscore_line(line)
            if not data:
                continue

            # Sport ID check — tennis is "2"
            if data.get("AA") != TENNIS_SPORT_ID:
                continue

            # Status: 1 = in progress
            if data.get("AB") not in ("1", "2", "3", "4", "5"):
                continue

            try:
                match_id = data.get("AA", "") + data.get("AD", "")
                player1 = data.get("AE", "Unknown")
                player2 = data.get("AF", "Unknown")
                tournament = data.get("AL", "")

                # Scores: sets
                sets_p1 = int(data.get("AG", 0) or 0)
                sets_p2 = int(data.get("AH", 0) or 0)

                # Current set games
                games_p1 = int(data.get("AI", 0) or 0)
                games_p2 = int(data.get("AJ", 0) or 0)

                # Current set number
                current_set = sets_p1 + sets_p2 + 1

                matches[match_id] = MatchState(
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
            except (ValueError, KeyError):
                continue

        return matches

    except asyncio.TimeoutError:
        print("[flashscore] timeout")
        return {}
    except Exception as e:
        print(f"[flashscore error] {e}")
        return {}

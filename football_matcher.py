"""Match live football teams to Polymarket markets."""
from difflib import SequenceMatcher

from football_feed import FootballMatch
from polymarket_feed import Market

FOOTBALL_MATCH_THRESHOLD = 1.2

_PROP_KEYWORDS = [
    "o/u", "over", "under", "draw", "both teams", "btts",
    "handicap", "total", "spread", "1.5", "2.5", "3.5", "4.5",
]


def _is_winner_market(p1: str, p2: str) -> bool:
    combined = (p1 + " " + p2).lower()
    return not any(kw in combined for kw in _PROP_KEYWORDS)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _clean_team_name(raw: str) -> str:
    """Strip tournament prefix like 'Champions League: Real Madrid' → 'Real Madrid'.
    Does NOT strip suffix after ':' to avoid destroying 'Clermont Foot 63'."""
    parts = raw.split(":", 1)
    if len(parts) == 2:
        prefix, suffix = parts[0].strip(), parts[1].strip()
        # Only strip if prefix looks like a tournament (no spaces = short code/league)
        if " " not in prefix:
            return suffix
    return raw.strip()


def match_teams(match: FootballMatch, markets: list[Market]) -> Market | None:
    """Return the best Polymarket match winner market for the given live match."""
    best_market = None
    best_score = 0.0

    for market in markets:
        if not _is_winner_market(market.player1_name, market.player2_name):
            continue

        poly_t1 = _clean_team_name(market.player1_name)
        poly_t2 = _clean_team_name(market.player2_name)

        score_straight = _similarity(match.team1, poly_t1) + _similarity(match.team2, poly_t2)
        score_reversed = _similarity(match.team1, poly_t2) + _similarity(match.team2, poly_t1)
        score = max(score_straight, score_reversed)

        if score > best_score and score >= FOOTBALL_MATCH_THRESHOLD:
            best_score = score
            best_market = market

    if best_market:
        print(
            f"[football matcher] ✅ {match.team1} vs {match.team2}"
            f" → {best_market.player1_name} | score={best_score:.2f}"
        )

    return best_market

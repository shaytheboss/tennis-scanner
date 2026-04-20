"""Match ESPN football teams to Polymarket markets."""
from difflib import SequenceMatcher

from football_feed import FootballMatch
from polymarket_feed import Market

FOOTBALL_MATCH_THRESHOLD = 1.2


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _extract_team_name(raw: str) -> str:
    """Strip tournament prefix like 'Champions League: Real Madrid' → 'Real Madrid'."""
    if ":" in raw:
        raw = raw.split(":", 1)[1].strip()
    return raw.strip()


def match_teams(match: FootballMatch, markets: list[Market]) -> Market | None:
    """Return the best Polymarket market for the given live football match, or None."""
    best_market = None
    best_score = 0.0

    for market in markets:
        poly_t1 = _extract_team_name(market.player1_name)
        poly_t2 = _extract_team_name(market.player2_name)

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
    else:
        print(f"[football matcher] ❌ no match for {match.team1} vs {match.team2}")

    return best_market

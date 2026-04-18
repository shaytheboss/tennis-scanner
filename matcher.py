"""Match ESPN players to Polymarket markets."""
from difflib import SequenceMatcher
from sofascore_feed import MatchState
from polymarket_feed import Market


def _last_name(full_name: str) -> str:
    """Extract last name from full name."""
    parts = full_name.strip().split()
    if not parts:
        return ""
    return parts[-1].lower()


def _name_similarity(name_a: str, name_b: str) -> float:
    """Fuzzy similarity between two names."""
    return SequenceMatcher(None, name_a.lower(), name_b.lower()).ratio()


def _is_match_winner_market(p1: str, p2: str) -> bool:
    """
    Return True only for match winner markets.
    Filter out O/U, handicap, set winner markets.
    """
    combined = (p1 + " " + p2).lower()
    noise = ["o/u", "over", "under", "handicap", "games", "sets", "total", "spread", "+", "-1.", "-0."]
    return not any(n in combined for n in noise)


def _extract_player_name(raw: str) -> str:
    """
    Extract clean player name from polymarket question field.
    Examples:
      "Australian Open Women's: Laura Siegemund" -> "Laura Siegemund"
      "Siegemund" -> "Siegemund"
      "Set 1 Winner: Siegemund" -> "Siegemund"
    """
    if ":" in raw:
        raw = raw.split(":", 1)[1].strip()
    return raw.strip()


def match_players(match: MatchState, markets: list[Market]) -> Market | None:
    """
    Find the Polymarket market that matches the ESPN live match.
    Returns the best matching market or None.
    """
    espn_p1_last = _last_name(match.player1)
    espn_p2_last = _last_name(match.player2)

    best_market = None
    best_score = 0.0

    for market in markets:
        # Only consider match winner markets
        if not _is_match_winner_market(market.player1_name, market.player2_name):
            continue

        poly_p1 = _extract_player_name(market.player1_name)
        poly_p2 = _extract_player_name(market.player2_name)

        poly_p1_last = _last_name(poly_p1)
        poly_p2_last = _last_name(poly_p2)

        # Try both orderings
        score_straight = (
            _name_similarity(espn_p1_last, poly_p1_last) +
            _name_similarity(espn_p2_last, poly_p2_last)
        )
        score_reversed = (
            _name_similarity(espn_p1_last, poly_p2_last) +
            _name_similarity(espn_p2_last, poly_p1_last)
        )

        score = max(score_straight, score_reversed)

        if score > best_score and score >= 1.5:  # threshold: both names must match well
            best_score = score
            best_market = market

    if best_market:
        print(f"[matcher] ✅ {match.player1} vs {match.player2} → {best_market.player1_name} | score={best_score:.2f}")
    else:
        print(f"[matcher] ❌ no match for {match.player1} vs {match.player2}")

    return best_market

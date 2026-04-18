"""Fuzzy matching of player names between Sofascore and Polymarket."""
from difflib import SequenceMatcher
from typing import Optional

from sofascore_feed import MatchState
from polymarket_feed import Market
from config import FUZZY_MATCH_THRESHOLD


def extract_last_name(name: str) -> str:
    cleaned = name.strip().replace(".", "").replace(",", "")
    parts = [p for p in cleaned.split() if p]
    if not parts:
        return name.lower()
    long_parts = [p for p in parts if len(p) > 2]
    if not long_parts:
        return parts[-1].lower()
    if len(parts) >= 2 and len(parts[0]) > 2 and len(parts[-1]) <= 2:
        return parts[0].lower()
    return long_parts[-1].lower()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def match_players(match: MatchState, markets: list[Market]) -> Optional[Market]:
    p1_last = extract_last_name(match.player1)
    p2_last = extract_last_name(match.player2)
    best_market = None
    best_score = 0.0
    for market in markets:
        m1_last = extract_last_name(market.player1_name)
        m2_last = extract_last_name(market.player2_name)
        score_a = min(similarity(p1_last, m1_last), similarity(p2_last, m2_last))
        score_b = min(similarity(p1_last, m2_last), similarity(p2_last, m1_last))
        score = max(score_a, score_b)
        if score > best_score:
            best_score = score
            best_market = market
    if best_score >= FUZZY_MATCH_THRESHOLD:
        return best_market
    return None


def sofascore_leader_side_in_market(match: MatchState, market: Market, leader: str) -> str:
    leader_name = match.player1 if leader == "p1" else match.player2
    leader_last = extract_last_name(leader_name)
    m1_last = extract_last_name(market.player1_name)
    m2_last = extract_last_name(market.player2_name)
    if similarity(leader_last, m1_last) > similarity(leader_last, m2_last):
        return "p1"
    return "p2"

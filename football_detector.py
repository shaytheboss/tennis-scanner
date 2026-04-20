"""Football opportunity detection logic."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from football_feed import FootballMatch
from polymarket_feed import Market
from config import FOOTBALL_MIN_GOAL_LEAD, FOOTBALL_MIN_MINUTE, FOOTBALL_MAX_LEADER_PRICE


@dataclass
class FootballAlert:
    timestamp: str
    team1: str
    team2: str
    score1: int
    score2: int
    minute: int
    league: str
    leader_team: str
    trailer_team: str
    leader_price: float
    condition_id: str
    token_id: str


def check_football_opportunity(
    match: FootballMatch, market: Market
) -> Optional[FootballAlert]:
    if match.score1 > match.score2:
        lead = match.score1 - match.score2
        leader_team = match.team1
        trailer_team = match.team2
        leader_price = market.price_p1
        token_id = market.token_id_p1
    elif match.score2 > match.score1:
        lead = match.score2 - match.score1
        leader_team = match.team2
        trailer_team = match.team1
        leader_price = market.price_p2
        token_id = market.token_id_p2
    else:
        return None  # draw

    if lead < FOOTBALL_MIN_GOAL_LEAD:
        return None

    if match.minute < FOOTBALL_MIN_MINUTE:
        return None

    if leader_price < 0.5:
        return None

    if leader_price > FOOTBALL_MAX_LEADER_PRICE:
        return None

    return FootballAlert(
        timestamp=datetime.now().strftime("%H:%M:%S"),
        team1=match.team1,
        team2=match.team2,
        score1=match.score1,
        score2=match.score2,
        minute=match.minute,
        league=match.league,
        leader_team=leader_team,
        trailer_team=trailer_team,
        leader_price=leader_price,
        condition_id=market.condition_id,
        token_id=token_id,
    )

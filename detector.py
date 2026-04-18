"""Opportunity detection logic."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sofascore_feed import MatchState
from polymarket_feed import Market
from matcher import sofascore_leader_side_in_market
from config import THRESHOLDS, STAT_PROBS


@dataclass
class Alert:
    timestamp: str
    player1: str
    player2: str
    leader: str
    situation_type: str
    situation_text: str
    price_leader: float
    price_trailer: float
    statistical_prob: float
    edge: float
    condition_id: str
    token_id: str
    tournament: str


def _build_situation_text(situation, g_lead, g_trail, s_lead, s_trail, current_set, fmt):
    if situation == "lead_5_0":
        return f"leads {g_lead}-{g_trail} in set {current_set}"
    if situation == "lead_5_1":
        return f"leads {g_lead}-{g_trail} in set {current_set}"
    if situation == "lead_2_0_sets":
        return f"leads {s_lead}-{s_trail} in sets ({fmt})"
    if situation == "lead_2_0_and_3_0":
        return f"leads {s_lead}-{s_trail} in sets + {g_lead}-{g_trail} in set {current_set}"
    return situation


def check_opportunity(match: MatchState, market: Market) -> Optional[Alert]:
    if match.sets_p1 > match.sets_p2:
        leader = "p1"
    elif match.sets_p2 > match.sets_p1:
        leader = "p2"
    else:
        if match.games_p1 > match.games_p2:
            leader = "p1"
        elif match.games_p2 > match.games_p1:
            leader = "p2"
        else:
            return None

    if leader == "p1":
        g_lead, g_trail = match.games_p1, match.games_p2
        s_lead, s_trail = match.sets_p1, match.sets_p2
        leader_name = match.player1
    else:
        g_lead, g_trail = match.games_p2, match.games_p1
        s_lead, s_trail = match.sets_p2, match.sets_p1
        leader_name = match.player2

    situation = None
    if match.format == "bo3" and s_lead == 2 and s_trail == 0 and g_lead == 3 and g_trail == 0:
        situation = "lead_2_0_and_3_0"
    elif match.format == "bo3" and s_lead == 2 and s_trail == 0:
        situation = "lead_2_0_sets"
    elif g_lead == 5 and g_trail == 0:
        situation = "lead_5_0"
    elif g_lead == 5 and g_trail == 1:
        situation = "lead_5_1"

    if not situation:
        return None

    poly_side = sofascore_leader_side_in_market(match, market, leader)
    if poly_side == "p1":
        price_leader = market.price_p1
        price_trailer = market.price_p2
        token_id = market.token_id_p1
    else:
        price_leader = market.price_p2
        price_trailer = market.price_p1
        token_id = market.token_id_p2

    if not (0.01 < price_leader < 0.99):
        return None

    if price_trailer < THRESHOLDS[situation]:
        return None

    stat_prob = STAT_PROBS[situation]
    edge = stat_prob - price_leader
    if edge <= 0:
        return None

    return Alert(
        timestamp=datetime.now().strftime("%H:%M:%S"),
        player1=match.player1,
        player2=match.player2,
        leader=leader_name,
        situation_type=situation,
        situation_text=_build_situation_text(
            situation, g_lead, g_trail, s_lead, s_trail,
            match.current_set, match.format
        ),
        price_leader=price_leader,
        price_trailer=price_trailer,
        statistical_prob=stat_prob,
        edge=edge,
        condition_id=market.condition_id,
        token_id=token_id,
        tournament=match.tournament,
    )

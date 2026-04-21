"""Polymarket CLOB REST API — price verification and market resolution."""
import json
import aiohttp

CLOB_BASE  = "https://clob.polymarket.com"
GAMMA_BASE = "https://gamma-api.polymarket.com"


async def get_best_ask(token_id: str) -> float | None:
    """Return the cheapest available ask from the live order book, or None."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{CLOB_BASE}/book",
                params={"token_id": token_id},
                timeout=aiohttp.ClientTimeout(total=5),
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    print(f"[clob] book {resp.status} for {token_id[:12]}…")
                    return None
                data = await resp.json()
                asks = data.get("asks", [])
                if not asks:
                    return None
                return min(float(a["price"]) for a in asks)
    except Exception as e:
        print(f"[clob] get_best_ask error: {e}")
        return None


async def check_market_resolved(
    condition_id: str,
    token_id: str,
    buy_price: float,
) -> tuple[str, float] | None:
    """
    Return (outcome, pnl) when the market has closed, else None.
    outcome: 'win' | 'loss' | 'void'
    pnl: profit/loss per 1 unit staked at buy_price
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GAMMA_BASE}/markets",
                params={"conditionIds": condition_id},
                timeout=aiohttp.ClientTimeout(total=8),
                headers={"Accept": "application/json"},
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                items = data if isinstance(data, list) else data.get("data", [])
                if not items:
                    return None
                market = items[0]

                if not market.get("closed", False):
                    return None

                raw_tokens = market.get("clobTokenIds", "[]")
                token_ids = json.loads(raw_tokens) if isinstance(raw_tokens, str) else (raw_tokens or [])

                raw_prices = market.get("outcomePrices", "[0.5,0.5]")
                prices = json.loads(raw_prices) if isinstance(raw_prices, str) else (raw_prices or [0.5, 0.5])

                if token_id not in token_ids:
                    return None

                idx = token_ids.index(token_id)
                final = float(prices[idx]) if idx < len(prices) else 0.5

                if final >= 0.9:
                    return "win", round(1.0 - buy_price, 4)
                elif final <= 0.1:
                    return "loss", round(-buy_price, 4)
                else:
                    return "void", 0.0

    except Exception as e:
        print(f"[clob] check_market_resolved error: {e}")
    return None

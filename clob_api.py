"""Polymarket CLOB REST API helpers."""
import json
import aiohttp

CLOB_BASE = "https://clob.polymarket.com"
GAMMA_BASE = "https://gamma-api.polymarket.com"


def _extract_price(item: dict) -> float:
    for key in ("price", "p", "px"):
        if key in item:
            return float(item[key])
    raise KeyError(f"No price key in {list(item.keys())}")


async def get_best_ask(token_id: str) -> float | None:
    """Fetch the lowest price at which someone is willing to sell (best ask)."""
    async with aiohttp.ClientSession() as session:

        # Primary: order book
        try:
            async with session.get(
                f"{CLOB_BASE}/book",
                params={"token_id": token_id},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    asks = data.get("asks", [])
                    bids = data.get("bids", [])

                    if asks:
                        best_ask = min(_extract_price(a) for a in asks)
                        print(f"[clob] best_ask={best_ask:.3f} ({len(asks)} asks, {len(bids)} bids)")
                        return best_ask

                    if bids:
                        best_bid = max(_extract_price(b) for b in bids)
                        if best_bid >= 0.95:
                            # No sellers because token is essentially $1 (resolved win)
                            print(f"[clob] no asks, best_bid={best_bid:.3f} → near $1")
                            return best_bid

                    print(f"[clob] empty book for {token_id[:12]}..., trying last-trade-price")
                else:
                    print(f"[clob] book status={resp.status}")
        except Exception as e:
            print(f"[clob] book error: {e}")

        # Fallback: last trade price
        try:
            async with session.get(
                f"{CLOB_BASE}/last-trade-price",
                params={"token_id": token_id},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price_str = data.get("price") or data.get("p")
                    if price_str:
                        price = float(price_str)
                        print(f"[clob] last_trade_price={price:.3f} (fallback)")
                        return price
        except Exception as e:
            print(f"[clob] last-trade-price error: {e}")

    return None


async def check_market_resolved(condition_id: str, token_id: str, buy_price: float) -> tuple[str, float] | None:
    """
    Returns (outcome, pnl) if the market has resolved, else None.
    outcome: 'win' | 'loss' | 'void'
    pnl: e.g. +0.92 for a win bought at 8¢, -0.08 for a loss
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{GAMMA_BASE}/markets",
                params={"conditionId": condition_id},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    print(f"[clob] Gamma status={resp.status} for {condition_id[:12]}...")
                    return None

                data = await resp.json()
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict) and "data" in data:
                    items = data["data"]
                elif isinstance(data, dict):
                    items = [data]
                else:
                    return None

                if not items:
                    return None

                market = items[0]
                closed = bool(market.get("closed") or market.get("settled") or False)

                raw_tokens = market.get("clobTokenIds", "[]")
                token_ids = json.loads(raw_tokens) if isinstance(raw_tokens, str) else (raw_tokens or [])
                raw_prices = market.get("outcomePrices", "[0.5,0.5]")
                prices = json.loads(raw_prices) if isinstance(raw_prices, str) else (raw_prices or [0.5, 0.5])

                if token_id not in token_ids:
                    print(f"[clob] token {token_id[:12]}... not in market tokens")
                    return None

                idx = token_ids.index(token_id)
                final_price = float(prices[idx]) if idx < len(prices) else 0.5

                # Resolved if: officially closed OR price is clearly at terminal value
                is_terminal = final_price >= 0.97 or final_price <= 0.03
                if not closed and not is_terminal:
                    return None

                print(f"[clob] market resolved: closed={closed}, final_price={final_price:.3f}")

                if final_price >= 0.9:
                    return ("win", round(1.0 - buy_price, 4))
                elif final_price <= 0.1:
                    return ("loss", round(-buy_price, 4))
                else:
                    return ("void", 0.0)

    except Exception as e:
        print(f"[clob] check_market_resolved error: {e}")
        return None

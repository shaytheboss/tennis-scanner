"""Web dashboard for paper trade tracking."""
import asyncio
import os

from aiohttp import web

from database import get_all_trades

PORT = int(os.getenv("PORT", "8080"))


def _render_html(trades: list[dict]) -> str:
    total = len(trades)
    wins = sum(1 for t in trades if t["outcome"] == "win")
    losses = sum(1 for t in trades if t["outcome"] == "loss")
    pending = sum(1 for t in trades if t["outcome"] == "pending")
    total_pnl = sum(t["pnl"] or 0 for t in trades if t["outcome"] in ("win", "loss"))

    rows = ""
    for t in trades:
        emoji = {"win": "✅", "loss": "❌", "void": "↩️", "pending": "⏳"}.get(t["outcome"], "?")
        pnl_str = f"{t['pnl']:+.1%}" if t["pnl"] is not None else "—"
        ask_str = f"{t['verified_ask']:.0%}" if t["verified_ask"] is not None else "—"
        rows += (
            f"<tr>"
            f"<td>{t['created_at'][:16]}</td>"
            f"<td>{t['player1']} vs {t['player2']}</td>"
            f"<td>{t['tournament'] or '—'}</td>"
            f"<td>{t['leader']}</td>"
            f"<td>{t['situation']}</td>"
            f"<td>{t['ws_price']:.0%}</td>"
            f"<td>{ask_str}</td>"
            f"<td>{t['stat_prob']:.0%}</td>"
            f"<td>{emoji} {t['outcome']}</td>"
            f"<td>{pnl_str}</td>"
            f"</tr>"
        )

    pnl_color = "#4f4" if total_pnl >= 0 else "#f44"
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="30">
<title>Tennis Scanner Dashboard</title>
<style>
  body {{ font-family: monospace; background: #111; color: #eee; padding: 20px; margin: 0; }}
  h1 {{ color: #4af; margin-bottom: 20px; }}
  .stats {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 24px; }}
  .stat {{ background: #1e1e1e; padding: 16px 24px; border-radius: 8px; text-align: center; min-width: 100px; }}
  .stat .val {{ font-size: 2em; font-weight: bold; color: #4af; }}
  .stat .lbl {{ color: #888; font-size: 0.85em; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #222; padding: 10px 8px; text-align: left; color: #aaa; }}
  td {{ padding: 7px 8px; border-bottom: 1px solid #1e1e1e; }}
  tr:hover td {{ background: #1a1a1a; }}
  .footer {{ color: #444; font-size: 0.8em; margin-top: 16px; }}
</style>
</head>
<body>
<h1>🎾 Tennis Scanner — Paper Trades</h1>
<div class="stats">
  <div class="stat"><div class="val">{total}</div><div class="lbl">Total</div></div>
  <div class="stat"><div class="val" style="color:#4f4">{wins}</div><div class="lbl">Wins</div></div>
  <div class="stat"><div class="val" style="color:#f44">{losses}</div><div class="lbl">Losses</div></div>
  <div class="stat"><div class="val" style="color:#fa4">{pending}</div><div class="lbl">Pending</div></div>
  <div class="stat"><div class="val" style="color:{pnl_color}">{total_pnl:+.1%}</div><div class="lbl">Total P&L</div></div>
</div>
<table>
<tr>
  <th>Time</th><th>Match</th><th>Tournament</th><th>Leader</th>
  <th>Situation</th><th>WS Price</th><th>Ask</th><th>Stat%</th>
  <th>Outcome</th><th>P&L</th>
</tr>
{rows if rows else '<tr><td colspan="10" style="text-align:center;color:#555;padding:40px">No trades yet</td></tr>'}
</table>
<p class="footer">Auto-refreshes every 30s</p>
</body>
</html>"""


async def handle_index(request):
    trades = get_all_trades()
    return web.Response(text=_render_html(trades), content_type="text/html")


async def handle_api(request):
    return web.json_response(get_all_trades())


async def run_dashboard():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/trades", handle_api)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"[dashboard] running on port {PORT}")
    while True:
        await asyncio.sleep(3600)

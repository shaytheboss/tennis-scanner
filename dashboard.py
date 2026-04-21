"""Web dashboard for paper trade tracking."""
import asyncio
import os
from aiohttp import web
from database import get_all_trades

PORT = int(os.getenv("PORT", "8080"))


def _c(v, suffix="¢"):
    if v is None:
        return "—"
    return f"{v * 100:.1f}{suffix}"


def _pnl_html(v):
    if v is None:
        return "—"
    color = "#22c55e" if v >= 0 else "#ef4444"
    sign = "+" if v >= 0 else ""
    return f'<span style="color:{color}">{sign}{v:.4f}</span>'


def _badge(outcome):
    cfg = {
        "win":     ("#22c55e", "WIN"),
        "loss":    ("#ef4444", "LOSS"),
        "pending": ("#f59e0b", "PENDING"),
        "void":    ("#94a3b8", "VOID"),
    }
    color, label = cfg.get(outcome, ("#6b7280", outcome.upper()))
    return f'<span style="color:{color};font-weight:700">{label}</span>'


async def handle_index(request):
    trades = get_all_trades(500)
    resolved = [t for t in trades if t["outcome"] in ("win", "loss")]
    wins     = [t for t in resolved if t["outcome"] == "win"]
    wr       = len(wins) / len(resolved) * 100 if resolved else 0
    pnl_tot  = sum(t["pnl"] or 0 for t in resolved)
    avg_edge = (
        sum((t["edge_verified"] or t["edge_ws"] or 0) for t in trades) / len(trades)
        if trades else 0
    )

    rows = "".join(f"""
      <tr>
        <td>{t['created_at'][:16]}</td>
        <td><b>{t['leader']}</b></td>
        <td title="{t['player1']} vs {t['player2']}" style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
            {t['player1']} vs {t['player2']}</td>
        <td title="{t['tournament']}" style="max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
            {t['tournament']}</td>
        <td>{t['situation']}</td>
        <td>{_c(t['ws_price'])}</td>
        <td>{_c(t['verified_ask'])}</td>
        <td>{_c(t.get('edge_verified') or t.get('edge_ws'), '%')}</td>
        <td>{_c(t['stat_prob'], '%')}</td>
        <td>{_badge(t['outcome'])}</td>
        <td>{_pnl_html(t['pnl'])}</td>
      </tr>""" for t in trades)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>Polly Scanner</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        background:#0f172a;color:#e2e8f0;padding:24px;font-size:13px}}
  h1{{color:#38bdf8;margin-bottom:20px;font-size:20px;font-weight:700}}
  .cards{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:28px}}
  .card{{background:#1e293b;border-radius:12px;padding:14px 20px;min-width:120px}}
  .card .lbl{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.8px}}
  .card .val{{font-size:24px;font-weight:700;margin-top:4px}}
  .wrap{{overflow-x:auto}}
  table{{border-collapse:collapse;width:100%;background:#1e293b;
         border-radius:12px;overflow:hidden;min-width:860px}}
  th{{background:#0f172a;padding:9px 11px;text-align:left;font-size:11px;
      color:#64748b;text-transform:uppercase;white-space:nowrap}}
  td{{padding:8px 11px;border-bottom:1px solid #0f172a;white-space:nowrap}}
  tr:last-child td{{border-bottom:none}}
  tr:hover td{{background:#273344}}
  .empty{{text-align:center;color:#64748b;padding:60px!important;white-space:normal!important}}
  .sub{{font-size:11px;color:#64748b;margin-top:2px}}
</style>
</head>
<body>
<h1>🎾 Polly Scanner — Paper Trades</h1>
<div class="sub" style="margin-bottom:20px">Auto-refreshes every 30s</div>
<div class="cards">
  <div class="card">
    <div class="lbl">Total Trades</div>
    <div class="val">{len(trades)}</div>
  </div>
  <div class="card">
    <div class="lbl">Resolved</div>
    <div class="val">{len(resolved)}</div>
  </div>
  <div class="card">
    <div class="lbl">Win Rate</div>
    <div class="val" style="color:{'#22c55e' if wr>=50 else '#ef4444'}">{wr:.0f}%</div>
  </div>
  <div class="card">
    <div class="lbl">Total P&L</div>
    <div class="val" style="color:{'#22c55e' if pnl_tot>=0 else '#ef4444'}">{'+' if pnl_tot>=0 else ''}{pnl_tot:.3f}</div>
  </div>
  <div class="card">
    <div class="lbl">Avg Edge</div>
    <div class="val" style="color:#38bdf8">+{avg_edge*100:.1f}%</div>
  </div>
  <div class="card">
    <div class="lbl">Pending</div>
    <div class="val" style="color:#f59e0b">{len(trades)-len(resolved)}</div>
  </div>
</div>
<div class="wrap">
<table>
<thead><tr>
  <th>Time</th><th>Leader</th><th>Match</th><th>Tournament</th>
  <th>Situation</th><th>WS¢</th><th>Ask¢</th><th>Edge</th>
  <th>Prob</th><th>Outcome</th><th>P&L (units)</th>
</tr></thead>
<tbody>
{rows or '<tr><td class="empty" colspan="11">No trades recorded yet</td></tr>'}
</tbody>
</table>
</div>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


async def handle_api(request):
    return web.json_response(get_all_trades(500))


async def run_dashboard():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/trades", handle_api)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"[dashboard] listening on port {PORT}")
    while True:
        await asyncio.sleep(3600)

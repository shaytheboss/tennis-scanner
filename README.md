# Tennis Scanner — Polymarket Opportunity Detector

Scans live tennis matches and alerts via Telegram when Polymarket prices lag behind near-certain outcomes.

## Detection rules

| Situation | Statistical probability | Alert threshold |
|-----------|------------------------|-----------------|
| Leading 5-0 in current set | ~98% | Trailer still priced > 3¢ |
| Leading 5-1 in current set | ~95% | Trailer still priced > 6¢ |
| Leading 2-0 sets (best-of-3) | ~95% | Trailer still priced > 6¢ |
| Leading 2-0 sets + 3-0 in set 3 | ~99% | Trailer still priced > 2¢ |

## Setup

### 1. Create Telegram bot
- Chat with `@BotFather` → `/newbot` → save the token
- Send a message to your bot, then open:
  `https://api.telegram.org/bot<TOKEN>/getUpdates`
- Find `"chat":{"id": ...}` — that's your CHAT_ID

### 2. Local testing
```bash
cp .env.example .env
# Fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
pip install -r requirements.txt
python main.py
```

### 3. Deploy to Railway
1. Push repo to GitHub
2. railway.app → New Project → Deploy from GitHub
3. Variables → add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
4. Watch Deployments → Logs

## Notes
- **Polymarket blocks US IPs** — Railway runs in US by default. If the WebSocket fails, try Render.com (choose EU region) instead.
- Sofascore uses an unofficial API — if you get 403s, the User-Agent in config.py may need updating.

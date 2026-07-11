# DealBot MK v2

Scrapes all car listings from **reklama5.mk** and **pazar3.mk**, stores them in Supabase, flags underpriced deals, and sends Telegram alerts. Zero paid infrastructure.

## Architecture

| Layer | Tool | Notes |
|-------|------|-------|
| Compute | GitHub Actions (free public repo) | No minute cap |
| Database | Supabase free tier (500 MB Postgres) | |
| Alerts | Telegram Bot API | One HTTP call per alert |

## One-time setup

### 1. Supabase

1. Create a project at supabase.com (free tier).
2. Open **SQL Editor** and paste the contents of `supabase_schema.sql` — run it.

### 2. Telegram bot

1. Message `@BotFather` on Telegram, run `/newbot`, copy the token.
2. Send any message to the bot, then visit  
   `https://api.telegram.org/bot<TOKEN>/getUpdates`  
   to find your `chat.id`.

### 3. GitHub repo secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret name | Value |
|------------|-------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Your Supabase anon key |
| `TELEGRAM_BOT_TOKEN` | Token from BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat/user ID |
| `SCRAPING_PROXY_URL` | *(optional)* Only needed if Phase 0 fails |

### 4. Run Phase 0 probe

Actions → **Phase 0 — IP Viability Probe** → Run workflow.

- If it **passes**: proceed to the full crawl.
- If it **fails**: add a free scraping-proxy URL as `SCRAPING_PROXY_URL`  
  (e.g. ScraperAPI: `http://scraperapi:<API_KEY>@proxy-server.scraperapi.com:8001`)  
  and re-run the probe.

### 5. Run the full crawl

Actions → **Full Crawl (chunked)** → Run workflow.

The job scrapes for up to 5 hours, saves a checkpoint to Supabase, then automatically triggers itself again. Repeat until the final run prints `Crawl done: true` and sends a Telegram completion message.

### 6. Incremental runs

The **Incremental Crawl + Analysis + Alerts** workflow runs automatically every 4 hours via cron. It scrapes newest listings, scores all data, and fires Telegram alerts for fresh deals.

## Tuning

### Change the deal threshold

Edit `run_analysis.py`'s `--threshold` flag in `incremental.yml`:

```yaml
- name: Run analysis and send deal alerts
  run: python scripts/run_analysis.py --threshold 0.20 --min-comp 5
```

`0.20` = flag listings 20% or more below the group median price.

### Re-run the full crawl from scratch

1. Delete all rows in `crawl_checkpoints` via Supabase SQL Editor:
   ```sql
   DELETE FROM crawl_checkpoints;
   ```
2. Trigger **Full Crawl (chunked)** again.

### Add a new source site

1. Create `scraper/<newsite>.py` following the pattern of `reklama5.py`.
2. Import and add it to `scripts/run_scraper.py`.
3. Add a probe entry to `scripts/probe.py`.

## Keepalive

GitHub disables scheduled workflows after 60 days without a commit.  
The **Keepalive** workflow runs on the 1st and 15th of every month, writes the current timestamp to `.keepalive`, and pushes the commit — resetting the timer automatically.

No manual action is needed to keep the bot alive.

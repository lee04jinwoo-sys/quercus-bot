# Quercus Telegram Alert Bot

[![tests](https://github.com/lee04jinwoo-sys/quercus-bot/actions/workflows/tests.yml/badge.svg)](https://github.com/lee04jinwoo-sys/quercus-bot/actions/workflows/tests.yml)

A small always-on daemon that polls the University of Toronto's Canvas LMS (**Quercus**) every 30 minutes and pushes what changed to Telegram: new announcements, approaching assignment deadlines, newly published grades, and newly uploaded course files.

(한국어: U of T Quercus의 공지·마감·성적·강의자료 변경을 30분마다 확인해 텔레그램으로 알려주는 봇입니다.)

## What it does

| Alert | Trigger |
|---|---|
| Announcement | A new announcement ID appears in any active course |
| Deadline | An **unsubmitted** assignment enters the D-3, D-1, 12h-left or final-3.5h window; each window fires once per assignment |
| Grade | An assignment gets a score for the first time |
| File | A new file ID appears in a course's Files tab (a hidden Files tab, HTTP 403, is skipped) |

The first run only indexes existing items silently, so you are not flooded with old content.

## Design notes

- **State** lives in `sent_history.json` (written atomically via a temp file) so restarts never resend alerts.
- **A failed Telegram send does not mark the item as sent.** The alert is retried on the next poll. (An earlier version marked announcements, grades and files as sent even when delivery failed, which silently dropped them.)
- **API errors are not "no news".** The client raises `QuercusAPIError` instead of returning an empty list. A failed poll never completes the initial sync and never updates `last_check_at`.
- **Expired token** (HTTP 401) sends one Telegram message asking you to renew it, not one per poll, and re-arms after the API recovers.
- Telegram messages HTML-escape all course-supplied text.

## Setup

```bash
cp .env.example .env     # QUERCUS_API_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
uv sync
uv run quercus-bot --test-msg   # verify Telegram wiring
uv run quercus-bot --once       # one poll (first run = silent index)
uv run quercus-bot --dry-run --once
uv run quercus-bot              # daemon, POLL_INTERVAL_SECONDS (default 1800)
```

The token is a Canvas personal access token (Quercus > Account > Settings > New Access Token). `.env` and `sent_history.json` are git-ignored.

### Running 24/7 with systemd

`quercus-bot.service` is a ready unit file. Adjust `User` and paths, then:

```bash
sudo cp quercus-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now quercus-bot
sudo journalctl -u quercus-bot -f
```

## Development

```bash
uv sync
uv run pytest
```

Tests use a fake client for `check_once()` and `respx` for the HTTP layer, so they never touch Quercus or Telegram. They cover the deadline windows, dedupe, delivery-failure retry, initial-sync safety and token-expiry handling.

## Limitations

- Polling, not push: alerts can lag by up to one poll interval.
- Grade *changes* after the first score are not reported.
- Only the first page of results is fetched (30 announcements, 50 assignments, 15 files per course).
- Course display names are an alias table in `daemon.py`; other courses fall back to their Canvas names.
- Single user, single Telegram chat.

## Layout

```
src/quercus_bot/
  client.py    Canvas REST client (QuercusAPIError / QuercusAuthError)
  daemon.py    check_once() polling logic and the run loop
  notifier.py  Telegram sender and message formatting
  storage.py   sent_history.json persistence
  models.py    Pydantic models
tests/         pytest suite
```

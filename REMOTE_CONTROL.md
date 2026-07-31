# 📱 Remote Control

Control the AI Video Factory from your phone with a Telegram bot.

The factory's real production pipeline (the **Genesis Content Engine**) runs in
GitHub Actions on a schedule. `remote_control.py` lets you reach into that
pipeline from anywhere — trigger a batch on demand, check whether the last run
succeeded, and get pinged when a run finishes — all from a Telegram chat.

It's **zero-infrastructure**: long-polling, no public URL, no webhook, and no
extra dependencies beyond `requests` (already in `requirements.txt`).

---

## Commands

| Command | What it does |
| --- | --- |
| `/run [batch]` | Trigger the Genesis pipeline. `batch` = `full` (default), `morning`, `evening`, `trends-only`, `post-only` |
| `/status` | Show the latest workflow run (status + result) |
| `/runs` | List the last few runs with links |
| `/id` | Show your Telegram chat id (used to authorise you) |
| `/ping` | Check the bot is alive |
| `/help` | Show the command list |

`/id` and `/ping` work for anyone; every other command is restricted to the
chat ids in `TELEGRAM_ALLOWED_CHAT_IDS`.

---

## Setup (5 minutes)

### 1. Create the Telegram bot
1. In Telegram, message [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, pick a name and username.
3. Copy the **bot token** it gives you (looks like `123456:ABC-DEF...`).

### 2. Create a GitHub token
The bot triggers the workflow via the GitHub API, so it needs a token:

- **Fine-grained PAT** (recommended): repository access = `penuelmdluli/ai-video-factory`,
  permission **Actions → Read and write**.
- **Classic PAT**: `repo` scope.

Create it at <https://github.com/settings/tokens>.

### 3. Configure `.env`
Add to your `.env` (copy the block from `.env.example`):

```dotenv
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_ALLOWED_CHAT_IDS=              # leave blank for the first run
GITHUB_TOKEN=ghp_...
GITHUB_REPO=penuelmdluli/ai-video-factory
GENESIS_WORKFLOW_FILE=genesis-content-engine.yml
GENESIS_WORKFLOW_REF=main
```

### 4. Get your chat id
```bash
python remote_control.py
```
Open your bot in Telegram, send `/id`. It replies with your chat id. Paste it
into `TELEGRAM_ALLOWED_CHAT_IDS` (comma-separate multiple owners), then restart
the bot. That's it — you now have `/run`, `/status`, and `/runs`.

---

## Running it

```bash
python remote_control.py                     # start the bot (long-polling)
python remote_control.py --notify "hello ✅"  # send one message to all owners and exit
```

Keep it running on any always-on machine — a Raspberry Pi, a small VPS, or a
`screen`/`systemd` service. Because it uses long-polling it needs **no public
IP and no webhook**.

### Run as a systemd service (optional)
```ini
# /etc/systemd/system/factory-remote.service
[Unit]
Description=AI Video Factory Remote Control
After=network-online.target

[Service]
WorkingDirectory=/path/to/ai-video-factory
ExecStart=/usr/bin/python3 remote_control.py
Restart=always
EnvironmentFile=/path/to/ai-video-factory/.env

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now factory-remote
```

---

## Get notified when a batch finishes

The GitHub Actions workflow can ping your phone at the end of every run. Add
these repository **secrets** (Settings → Secrets and variables → Actions):

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_CHAT_IDS`

The workflow's final "Notify Telegram" step is already wired up and simply
skips itself if the secrets aren't set — so notifications are opt-in.

You can also call it from any Python code in the pipeline:

```python
from remote_control import notify
notify("✅ Evening batch finished — 4 videos posted.")
```

---

## Security notes

- Only chat ids in `TELEGRAM_ALLOWED_CHAT_IDS` can trigger runs. Keep it tight.
- The `GITHUB_TOKEN` only needs Actions access to this one repo — scope it down.
- Never commit real tokens. `.env` is git-ignored; `.env.example` holds
  placeholders only.

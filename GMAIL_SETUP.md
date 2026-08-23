# Gmail as a monitoring channel

Set up 2026-08-21. Two things: the inbox routes itself, and the health check
reads it.

Background: RunPod deleted the network volume on 2026-08-18 and the warning
went unseen for four days — it landed in an inbox holding ~63,900 unread
messages. Nothing here is cosmetic.

---

## 1. Import the filters (one-off, ~1 min)

Gmail → Settings → **See all settings** → **Filters and Blocked Addresses**
→ **Import filters** → choose `gmail_filters.xml` → **Open file** →
**Create filters**.

16 rules. The shape of them:

| Routed to | What lands there | Inbox? |
|---|---|---|
| `Ops/Infra` | RunPod, ElevenLabs, HuggingFace, OpenAI, Anthropic, Replicate | stays, starred |
| `Ops/Platforms` | Facebook/Meta, TikTok, YouTube | stays |
| `Ops/Billing` | anything saying declined / past due / low balance | stays, starred |
| `Money/Bank` | FNB — declines starred, routine alerts archived | split |
| `Money/Fines` | AARTO notices | stays, starred |
| `Money/Subscriptions` | Google Play receipts | archived |
| `Work/Absa-Builds` | Firebase build notifications | archived, unread |
| `Careers/Leads` | Pnet, Indeed, Careers24, LinkedIn job alerts | archived, unread |
| `Bulk/*` | shopping, newsletters, LinkedIn social, GoBid | archived, read |

Deliberate: nothing operational is ever auto-archived, and nothing is ever
auto-deleted. Bulk mail is marked read; work and career mail is not, so it
still registers as something you haven't looked at.

## 2. Clear the backlog (one-off)

Imported filters only apply to **new** mail. For the existing pile, run each
search, hit the select-all box, click *"Select all conversations that match
this search"*, then apply the label and archive.

```
from:firebase-noreply@google.com                                    -> Work/Absa-Builds
from:linkedin.com -jobalerts                                        -> Bulk/Social
from:(shein.com OR temu.com OR temuemail.com OR takealot.com)       -> Bulk/Shopping
from:(mybroadband.co.za OR oreilly.com OR docker.com OR vidiq.com)  -> Bulk/Newsletters
from:gobid.co.za                                                    -> Bulk/Auctions
from:(pnet.co.za OR indeed.com OR careers24.com OR jobmail.co.za)   -> Careers/Leads
from:fnb.co.za -declined -insufficient                              -> Money/Bank
from:runpod.io                                                      -> Ops/Infra
```

## 3. Turn on the email alerts in the health check

```
python auth_gmail.py
```

Opens a browser once, asks for **read-only** Gmail access, writes
`tokens/gmail_token.json`. It reuses the existing desktop OAuth client in
`tokens/youtube_client_secret.json`, so there is no new app to register — but
the Gmail API must be enabled on that same Google Cloud project. If it errors
with *"Gmail API has not been used in project ..."*, open the link in the
error, enable it, run again.

Verify any time with `python auth_gmail.py --check`.

The token is `gmail.readonly`: it can read mail and nothing else. It cannot
send, delete, or modify.

### What it watches

`modules/gmail_alerts.py` runs six queries over the last 2 days and hands any
hit to `build_health_check.py`, which WhatsApps you through the existing
`notify_failure` path with its 6-hour per-tag cooldown:

- `mail-runpod` — low balance, past due, volume deleted, payment failed
- `mail-billing` — any declined/failed payment, anything about to cancel
- `mail-fb-page` — Meta violations, restrictions, disabled pages, appeals
- `mail-tiktok-auth` — new device logins (your `TIKTOK_SESSION_ID` likely died)
- `mail-youtube` — strikes, copyright, removals
- `mail-api-quota` — provider quota, rate limit, credit and expiry notices

Already wired into `Genesis Health Check` (Task Scheduler, every 2h, currently
Ready). No new task needed. Until the token exists the check is a no-op — the
rest of the health check runs exactly as before.

To widen coverage, add to `RULES` in `modules/gmail_alerts.py`. Keep the tag
strings stable: renaming a tag resets its cooldown and re-pages you for a
problem you already know about.

"""
The roll-call ask, rotated. Same proven reel, never the same words twice.

Owner call 2026-08-28: "we also need to post more of the show some love - who
still loves Kaizer Chiefs, comment with love or say Love and Peace. This also
trends."

Owner call 2026-09-11, after one roll call took 3,332 likes and 1,025 comments
(HOW LONG HAVE YOU BEEN KHOSI? - roughly twenty times anything else that week):
"the fans pride works better... add more that will cause Pirates fans and Kaizer
Chiefs debate... the argument, the pride, who are the best fans... discuss
trophies, hopes... go with what works now."

So there are three banks now, all rendered by the same reel:

    pride     belonging - a year, a city, a name only a real supporter has
    rivalry   Chiefs fans against Pirates fans. Chiefs stay the SUBJECT and
              Pirates are the foil (see the Chiefs-only page rule); the post
              invites both sides into one comment box, which is the point
    hopes     trophies, the log, the season - opinions, so nobody is wrong

What made the winner work is worth keeping in view when adding to these: it
asked for something every supporter HAS (the year they started), it was
answerable in one word, and nobody could get it wrong. Most of the new asks
copy that shape - a number, an era, one name.

RULES FOR THE WORDS, because this page lives on being trusted:
  * no statistics, trophy counts or derby records - claims like that are
    instantly checkable and we have no source wired in here. Opinions only.
  * rival claims are attributed banter ("Pirates fans say..."), never stated
    as our fact, and never an insult - the reply persona says the same.
  * no "LIKE if / SHARE this / TAG a friend / react with X for Y". Facebook
    demotes engagement bait in distribution, which costs exactly the views the
    owner wants. One real question does the work; a single soft share nudge
    rides in the pinned comment (share_nudge below), not on the video.

WHICH ask runs is learned, not round-robin. Every reel caption carries the ask
lines verbatim, so format_intel's post_metrics table already says how each ask
did. Asks that earned more come back more often; unmeasured asks keep a
neutral weight so new words still get tried; nothing repeats inside
COOLDOWN_H, so even the winner cannot become wallpaper.

Each entry is (on-screen lines, call to action, spoken ask). Three lines on
screen because that is what the reel lays out; each is shrunk to the frame
width by the renderer.
"""
import json
import random
import sqlite3
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATE = ROOT / "data" / "rollcall_asks.json"
DB = ROOT / "data" / "growth_analytics.db"
SAST = timezone(timedelta(hours=2))

COOLDOWN_H = 72         # an ask stays off the page this long after it runs
MIN_AGE_H = 12          # same maturity rule as format_intel
W_LIKE, W_COMMENT, W_SHARE = 1.0, 3.0, 5.0

# Only reels count towards an ask's score. The same prompts once ran as flat
# love cards that took three likes; letting those drag an ask down would be
# scoring the old format, not the words.
REEL_HEADERS = ("ROLL CALL", "MATCHDAY", "FAN DEBATE", "THE BIG QUESTION")

PRIDE = [
    (["HOW MANY", "KAIZER CHIEFS", "FANS ARE HERE?"],
     "COMMENT  ·  SAY KHOSI",
     "How many Kaizer Chiefs fans are here? Say Khosi and let us count."),

    (["WHO STILL", "LOVES KAIZER", "CHIEFS?"],
     "COMMENT  ·  SAY LOVE",
     "Who still loves Kaizer Chiefs? Not who is happy - who still LOVES "
     "them. Comment love."),

    (["SAY", "LOVE AND PEACE", "IF YOU ARE KHOSI"],
     "LOVE AND PEACE  💛✌️",
     "If you are Khosi, say it with me. Love and peace."),

    (["DROP A HEART", "IF YOU LOVE", "THIS CLUB"],
     "JUST A HEART  ·  NOTHING ELSE",
     "Drop a heart if you love this club. Just a heart, nothing else. "
     "We want to see the numbers."),

    (["STILL HERE?", "THROUGH", "EVERYTHING?"],
     "COMMENT  ·  I AM STILL HERE",
     "Through everything, are you still here? Comment - I am still here."),

    (["AMAKHOSI", "FOR LIFE.", "WHO IS WITH ME?"],
     "COMMENT  ·  AMAKHOSI 4 LIFE",
     "Amakhosi for life. Who is with me? Say it below."),

    # 3,332 likes and 1,025 comments on 7 Sep 2026. The model for the rest.
    (["HOW LONG", "HAVE YOU", "BEEN KHOSI?"],
     "DROP THE YEAR  ·  JUST THE YEAR",
     "How long have you been Khosi? Drop the year you started supporting "
     "Amakhosi. Just the year."),

    (["ONE WORD", "FOR", "AMAKHOSI"],
     "ONE WORD  ·  NOT TWO",
     "One word for Amakhosi. Not two. What is this club to you?"),

    (["WHERE DO YOU", "WATCH", "FROM?"],
     "DROP YOUR CITY  ·  OR YOUR TOWNSHIP",
     "Where do you watch from? Drop your city or your township, and let us "
     "see how far Khosi Nation reaches."),

    (["WHO MADE YOU", "LOVE", "THIS CLUB?"],
     "SAY WHO  ·  AND SAY WHY",
     "Who made you love this club? A parent, a neighbour, a player? Say who, "
     "and say why."),

    # Same shape as the winner: a fact about yourself only a supporter has.
    (["WHICH ERA", "OF KHOSI", "ARE YOU?"],
     "70s  ·  80s  ·  90s  ·  2000s  ·  2010s",
     "Which era of Khosi are you? The seventies, the eighties, the nineties, "
     "the two thousands, or the new generation? Drop your era."),

    (["HOW OLD WERE", "YOU WHEN YOU", "CHOSE KHOSI?"],
     "JUST THE AGE  ·  NOTHING ELSE",
     "How old were you when you chose Kaizer Chiefs? Just the age. "
     "Nothing else."),

    (["YOUR FIRST", "CHIEFS HERO.", "ONE NAME."],
     "ANY ERA  ·  ONE NAME",
     "Your first Kaizer Chiefs hero. Any era. Just one name."),

    (["YOUR FIRST", "CHIEFS GAME:", "WHAT YEAR?"],
     "DROP THE YEAR  ·  AND THE STADIUM",
     "Your first Kaizer Chiefs game, on TV or in the stadium. What year was "
     "it? Drop the year."),
]

RIVALRY = [
    (["PIRATES FANS SAY", "THEY ARE THE", "BIGGEST CLUB"],
     "KHOSI  ·  PROVE THEM WRONG",
     "Pirates fans say they are the biggest club in the country. Kaizer "
     "Chiefs fans, prove them wrong. One word. Khosi."),

    (["WHO HAS THE", "BIGGEST FANS", "IN MZANSI?"],
     "KHOSI  OR  BUCS  ·  PICK ONE",
     "Who has the biggest fans in Mzansi? Kaizer Chiefs or Orlando Pirates. "
     "Pick one, and only one."),

    (["CHIEFS FANS", "OR PIRATES FANS:", "WHO IS LOUDER?"],
     "COMMENT  ·  KHOSI OR BUCS",
     "Kaizer Chiefs fans or Orlando Pirates fans. Who is louder? Let us "
     "settle it in the comments."),

    (["THEY SAY", "CHIEFS FANS", "HAVE GONE QUIET"],
     "SAY KHOSI  ·  SHOW THEM",
     "They say Kaizer Chiefs fans have gone quiet. Let us show them how "
     "wrong they are. Say Khosi."),

    (["BORN KHOSI", "OR BORN", "A PIRATE?"],
     "NO NEUTRALS  ·  SAY IT",
     "Were you born Khosi, or born a Pirate? No neutrals allowed. Say it."),

    (["ONE CLUB", "FOR THE REST", "OF YOUR LIFE"],
     "CHIEFS OR PIRATES  ·  NO SWITCHING",
     "One club for the rest of your life. Kaizer Chiefs or Orlando Pirates. "
     "No switching, ever."),

    (["PIRATES FANS:", "WHAT DO YOU", "ENVY ABOUT CHIEFS?"],
     "BE HONEST  ·  WE ARE WAITING",
     "Pirates fans, be honest. What do you secretly envy about Kaizer "
     "Chiefs? We are waiting."),

    (["SOWETO IS", "GOLD AND BLACK.", "AGREE?"],
     "YES OR NO  ·  BUCS FANS TOO",
     "Soweto is gold and black. Agree? Pirates fans, you are allowed to "
     "disagree. Below."),

    (["WHICH FANS", "STAYED LOYAL IN", "THE HARD YEARS?"],
     "CHIEFS OR PIRATES  ·  SAY WHY",
     "Which fans stayed loyal through the hard years? Kaizer Chiefs or "
     "Orlando Pirates? Say who, and say why."),

    (["THE SOWETO DERBY:", "WHOSE CITY", "IS IT?"],
     "KHOSI  OR  BUCS",
     "The Soweto derby. Whose city is it? Kaizer Chiefs or Orlando Pirates? "
     "Settle it."),

    (["WHO WINS", "THE NEXT", "SOWETO DERBY?"],
     "THE SCORE  ·  AND FIRST SCORER",
     "Who wins the next Soweto derby? Give us the score and the first "
     "scorer."),

    (["CHIEFS FANS:", "ONE LINE FOR", "PIRATES FANS"],
     "KEEP IT CLEAN  ·  KEEP IT FUNNY",
     "Kaizer Chiefs fans, one line for the Pirates fans reading this. Keep "
     "it clean, and keep it funny."),
]

HOPES = [
    (["WHICH TROPHY", "DO CHIEFS WIN", "THIS SEASON?"],
     "LEAGUE  ·  CUP  ·  OR NOTHING",
     "Which trophy do Kaizer Chiefs win this season? The league, a cup, or "
     "nothing? Your call, and one reason."),

    (["LEAGUE", "OR A CUP:", "WHICH ONE?"],
     "PICK ONE  ·  SAY WHY",
     "If Kaizer Chiefs could win only one this season, the league or a cup, "
     "which one do you take? Say why."),

    (["WHERE DO", "CHIEFS FINISH", "ON THE LOG?"],
     "JUST THE NUMBER",
     "Where do Kaizer Chiefs finish on the log this season? Just the number."),

    (["WHO IS OUR", "PLAYER OF THE", "SEASON SO FAR?"],
     "ONE NAME  ·  ONE REASON",
     "Who is the Kaizer Chiefs player of the season so far? One name, one "
     "reason."),

    (["BE HONEST:", "ARE CHIEFS TITLE", "CONTENDERS?"],
     "YES OR NO  ·  NO MAYBE",
     "Be honest. Are Kaizer Chiefs title contenders this season? Yes or no. "
     "No maybe."),

    (["WHAT DOES", "THIS SQUAD", "NEED MOST?"],
     "ONE POSITION  ·  ONE WORD",
     "What does this Kaizer Chiefs squad need most? One position."),

    (["RATE THE", "SEASON SO FAR", "OUT OF 10"],
     "JUST THE NUMBER",
     "Rate the Kaizer Chiefs season so far, out of ten. Just the number."),

    (["THE DAY CHIEFS", "LIFT THE LEAGUE,", "WHERE ARE YOU?"],
     "SAY WHERE  ·  AND WITH WHO",
     "The day Kaizer Chiefs lift the league again, where will you be, and "
     "who will you be with?"),

    (["WHO SCORES", "THE MOST GOALS", "FOR US?"],
     "ONE NAME",
     "Who scores the most goals for Kaizer Chiefs this season? One name."),
]

BANKS = {"pride": PRIDE, "rivalry": RIVALRY, "hopes": HOPES}
ASKS = PRIDE            # the name build_matchday_hype and older code imported

# One soft share nudge for the pinned comment, tied to the question rather
# than a bare "share this". See the engagement-bait note at the top.
SHARE_NUDGES = {
    "pride": [
        "💛 Send this to the Chiefs fan who got you into it.",
        "💛 Send this to your Khosi group chat and see who answers first.",
    ],
    "rivalry": [
        "⚔️ Got a Pirates friend who thinks otherwise? Send them this and let "
        "them answer here.",
        "⚔️ Send this to the Bucs fan in your group chat. We will wait.",
    ],
    "hopes": [
        "🏆 Send this to the friend who says 'this is our season' every season.",
        "🏆 Send this to the Chiefs fan who will disagree with you.",
    ],
}


def key_of(ask: tuple) -> str:
    """The ask as it appears in the caption - how its posts are found again."""
    return " ".join(ask[0])


def _load() -> dict:
    try:
        d = json.loads(STATE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _age_h(created: str):
    try:
        when = datetime.fromisoformat(created.replace("Z", "+00:00"))
        return (datetime.now(SAST) - when.astimezone(SAST)).total_seconds() / 3600
    except Exception:
        return None


def measured() -> dict:
    """{ask key: (posts, avg score)} from the page's own mature reel posts."""
    keys = {key_of(a).upper(): key_of(a) for bank in BANKS.values() for a in bank}
    try:
        c = sqlite3.connect(str(DB), timeout=10)
        rows = c.execute("""SELECT message, created_at, likes, comments, shares
                            FROM post_metrics WHERE niche='sa_pulse'""").fetchall()
        c.close()
    except Exception:
        return {}
    agg = {}
    for msg, created, likes, comments, shares in rows:
        up = (msg or "").upper()
        if not any(h in up for h in REEL_HEADERS):
            continue
        age = _age_h(created or "")
        if age is None or age < MIN_AGE_H:
            continue
        for k_up, k in keys.items():
            if k_up in up:
                s = (likes or 0) * W_LIKE + (comments or 0) * W_COMMENT \
                    + (shares or 0) * W_SHARE
                n, tot = agg.get(k, (0, 0.0))
                agg[k] = (n + 1, tot + s)
                break
    return {k: (n, tot / n) for k, (n, tot) in agg.items()}


def weights(kind: str) -> dict:
    """{ask key: weight} for one bank, relative to the page's median ask.

    The MEDIAN, not the mean: one post took 6,492 points against a typical
    ask's 60-120, and a mean that size would score every other ask as a
    failure. Clamped so a winner comes back often without taking over, and a
    weak ask still gets the odd second chance. Unmeasured asks sit at 1.0.
    """
    m = measured()
    mid = statistics.median([avg for _, avg in m.values()]) if m else 0
    out = {}
    for ask in BANKS[kind]:
        k = key_of(ask)
        if k in m and mid > 0:
            out[k] = round(min(3.0, max(0.5, m[k][1] / mid)), 2)
        else:
            out[k] = 1.0
    return out


def next_ask(kind: str = "pride") -> tuple:
    """Pick and record the next ask for a bank. Returns (lines, cta, spoken).

    Weighted random over asks that are off cooldown: proven asks come back
    more, but the page never reads as a loop, which is the owner's standing
    "dynamic and unpredictable" call.
    """
    bank = BANKS.get(kind, PRIDE)
    st = _load()
    history = st.get("history", [])
    now = datetime.now()

    last_used = {}
    for h in history:
        last_used[h.get("key", "")] = h.get("at", "")

    def cooled(ask) -> bool:
        at = last_used.get(key_of(ask))
        if not at:
            return False
        try:
            return now - datetime.fromisoformat(at) < timedelta(hours=COOLDOWN_H)
        except Exception:
            return False

    eligible = [a for a in bank if not cooled(a)]
    if not eligible:
        # every ask ran inside the window - take the one rested longest
        eligible = [min(bank, key=lambda a: last_used.get(key_of(a), ""))]

    w = weights(kind)
    pick = random.choices(eligible, weights=[w.get(key_of(a), 1.0)
                                             for a in eligible])[0]

    history.append({"kind": kind, "key": key_of(pick),
                    "at": now.isoformat(timespec="seconds")})
    st["history"] = history[-300:]
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2, ensure_ascii=False),
                     encoding="utf-8")
    return pick


def share_nudge(kind: str = "pride") -> str:
    return random.choice(SHARE_NUDGES.get(kind, SHARE_NUDGES["pride"]))

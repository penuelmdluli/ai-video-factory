"""How each position is played at the top level, in beats a board can draw.

Owner call 2026-09-02, describing a creator's video: "they are analysing a
position, like how a modern left back should play. We need to transform this
style where we are analysing the Chiefs team, a specific player, on how they
should play for the best of the team."

The format is a ROLE explained, then a real player placed inside it. That order
matters and it is what makes the format safe as well as good: the teaching half
is general football, true of any league, and owes nobody a statistic. The only
player-specific claim the reel makes is WHERE HE LINES UP, and that comes from
the ESPN team sheet via psl_squads.recent_positions - the same published
LB/CD-R/RM data that fixed Monyane's slot on the line-up cards.

So the page never says "Monyane completed 3.2 tackles per game". It says: this
is the job, these are the three things it demands, and this is the man Chiefs
put there. Everything asserted is either textbook or on a team sheet. That is
the difference between punditry a supporter argues with and a page inventing
numbers it will be caught on - and this repo has a standing rule that XIs and
facts come only from verified sheets.

Coordinates are the Board's: x 0..1 left to right, y 0..1 where y=0 is the
OPPONENT goal, so attacking runs move UP the frame like a TV graphic.
"""

# Each beat is one thing the role demands, with the movement that shows it.
#   from/to  : the run, as (x, y) fractions
#   zone     : optional rectangle to pulse (x0, y0, x1, y1)
#   label    : short text on the arrow
#   say      : the narration line
ROLES = {
    "RB": {
        "title": "THE MODERN RIGHT-BACK",
        "job": "Defend a touchline, then attack the same one.",
        "home": (0.86, 0.72),
        "beats": [
            {"label": "OVERLAP", "from": (0.86, 0.72), "to": (0.88, 0.26),
             "say": "First, he has to get up the pitch. A modern right back is "
                    "the widest attacker on his side, and when the winger comes "
                    "inside, that whole touchline is his to run."},
            {"label": "RECOVER", "from": (0.88, 0.26), "to": (0.80, 0.78),
             "zone": (0.62, 0.62, 0.98, 0.92),
             "say": "Then he has to get back. That is the hard part. The space "
                    "he leaves behind him is the space every counter attack "
                    "aims at, so the run forward is only worth it if the run "
                    "back is just as quick."},
            {"label": "TUCK IN", "from": (0.80, 0.78), "to": (0.68, 0.80),
             "say": "And when the ball is on the far side, he tucks in and "
                    "becomes a third centre back. A full back who stays wide "
                    "when the danger is central is defending nobody."},
        ],
    },
    "LB": {
        "title": "THE MODERN LEFT-BACK",
        "job": "Defend a touchline, then attack the same one.",
        "home": (0.14, 0.72),
        "beats": [
            {"label": "OVERLAP", "from": (0.14, 0.72), "to": (0.12, 0.26),
             "say": "First, he has to get up the pitch. A modern left back is "
                    "the widest attacker on his side, and when the winger cuts "
                    "inside, that touchline belongs to him."},
            {"label": "RECOVER", "from": (0.12, 0.26), "to": (0.20, 0.78),
             "zone": (0.02, 0.62, 0.38, 0.92),
             "say": "Then he has to get back, and that is the hard part. The "
                    "space behind him is exactly where every counter attack is "
                    "aimed, so the run forward only pays if the run back is "
                    "just as quick."},
            {"label": "TUCK IN", "from": (0.20, 0.78), "to": (0.32, 0.80),
             "say": "And when the ball is on the far side he tucks in as a "
                    "third centre back. A full back standing wide while the "
                    "danger is central is defending nobody."},
        ],
    },
    "CB": {
        "title": "THE MODERN CENTRE-BACK",
        "job": "Win the duel, then start the attack.",
        "home": (0.40, 0.80),
        "beats": [
            {"label": "STEP UP", "from": (0.40, 0.80), "to": (0.42, 0.62),
             "zone": (0.20, 0.56, 0.80, 0.86),
             "say": "He decides where the team defends. Step up and the whole "
                    "line steps with him, squeezing sixty metres into thirty. "
                    "Drop off and the midfield is playing on its own."},
            {"label": "COVER", "from": (0.42, 0.62), "to": (0.30, 0.82),
             "say": "When his partner goes to the ball, he does not follow. He "
                    "covers behind him. Two centre backs attacking the same "
                    "ball is how a striker ends up running into an empty half."},
            {"label": "BREAK THE LINE", "from": (0.30, 0.82), "to": (0.46, 0.48),
             "say": "And when he has it, the first look is forward. A pass that "
                    "takes out one opponent is worth more than five that take "
                    "out none."},
        ],
    },
    "CDM": {
        "title": "THE HOLDING MIDFIELDER",
        "job": "Protect the back four and turn the game around.",
        "home": (0.50, 0.62),
        "beats": [
            {"label": "SCREEN", "from": (0.50, 0.62), "to": (0.50, 0.70),
             "zone": (0.28, 0.58, 0.72, 0.80),
             "say": "His first job is the space in front of the centre backs. "
                    "Not a man, a space. If that pocket is empty, the other "
                    "team's best player is standing in it."},
            {"label": "RECEIVE", "from": (0.50, 0.70), "to": (0.36, 0.66),
             "say": "He drops to take the ball off the defenders so they are "
                    "never trapped. Every good side has one player who always "
                    "shows for it when nobody else wants it."},
            {"label": "SWITCH", "from": (0.36, 0.66), "to": (0.74, 0.56),
             "say": "Then he changes the picture. One pass across the pitch "
                    "moves eight opponents. That is the pass that turns a "
                    "blocked attack into a two on one."},
        ],
    },
    "CM": {
        "title": "THE CENTRAL MIDFIELDER",
        "job": "Link every phase, and arrive when it matters.",
        "home": (0.50, 0.52),
        "beats": [
            {"label": "HALF TURN", "from": (0.50, 0.52), "to": (0.44, 0.58),
             "say": "Everything starts with how he receives it. Open his body "
                    "before the ball arrives and he can play forward. Take it "
                    "flat and his only option is backwards."},
            {"label": "THIRD MAN", "from": (0.44, 0.58), "to": (0.56, 0.36),
             "say": "He is rarely the man who plays the killer pass. He is the "
                    "one who makes it possible, then runs past to collect the "
                    "return."},
            {"label": "ARRIVE", "from": (0.56, 0.36), "to": (0.52, 0.20),
             "zone": (0.34, 0.10, 0.66, 0.30),
             "say": "And late, he arrives in the box. Defenders track the "
                    "striker. The midfielder running in behind them is the one "
                    "nobody picks up."},
        ],
    },
    "CAM": {
        "title": "THE NUMBER TEN",
        "job": "Live between the lines and break them.",
        "home": (0.50, 0.38),
        "beats": [
            {"label": "BETWEEN LINES", "from": (0.50, 0.38), "to": (0.52, 0.32),
             "zone": (0.30, 0.24, 0.70, 0.42),
             "say": "He plays in the gap between their midfield and their "
                    "defence. Stand there and nobody knows whose job he is. "
                    "That confusion is the whole position."},
            {"label": "TURN", "from": (0.52, 0.32), "to": (0.48, 0.24),
             "say": "The moment he gets it facing forward, the game changes. "
                    "One turn takes four opponents out of the picture."},
            {"label": "RELEASE", "from": (0.48, 0.24), "to": (0.68, 0.16),
             "say": "Then the ball goes early. A ten who takes a touch too many "
                    "gives the defence the second it needed."},
        ],
    },
    "RW": {
        "title": "THE MODERN RIGHT WINGER",
        "job": "Pin the full-back, then punish him.",
        "home": (0.84, 0.30),
        "beats": [
            {"label": "STAY WIDE", "from": (0.84, 0.30), "to": (0.90, 0.32),
             "say": "He holds the touchline until the ball comes. Standing wide "
                    "and still looks lazy and is not: it drags a defender out "
                    "and opens the whole middle for everyone else."},
            {"label": "CUT INSIDE", "from": (0.90, 0.32), "to": (0.64, 0.20),
             "say": "Then he goes inside, onto his stronger foot, into the "
                    "shooting angle. That is why the full back behind him has "
                    "to overlap - somebody must take the outside."},
            {"label": "BACK POST", "from": (0.64, 0.20), "to": (0.74, 0.10),
             "zone": (0.58, 0.04, 0.92, 0.20),
             "say": "And when the attack goes the other way, he attacks the "
                    "back post. Most crosses from the far side end up there, "
                    "and most wingers are still watching."},
        ],
    },
    "LW": {
        "title": "THE MODERN LEFT WINGER",
        "job": "Pin the full-back, then punish him.",
        "home": (0.16, 0.30),
        "beats": [
            {"label": "STAY WIDE", "from": (0.16, 0.30), "to": (0.10, 0.32),
             "say": "He holds that touchline until the ball comes. Wide and "
                    "still is not lazy - it drags a defender out and opens the "
                    "middle for everybody else."},
            {"label": "CUT INSIDE", "from": (0.10, 0.32), "to": (0.36, 0.20),
             "say": "Then inside, onto the stronger foot, into the shooting "
                    "angle. Which is exactly why the full back behind him must "
                    "overlap: somebody has to take the outside."},
            {"label": "BACK POST", "from": (0.36, 0.20), "to": (0.26, 0.10),
             "zone": (0.08, 0.04, 0.42, 0.20),
             "say": "And when it goes the other way he attacks the back post. "
                    "That is where far side crosses land, and where most "
                    "wingers are still watching."},
        ],
    },
    "ST": {
        "title": "THE MODERN STRIKER",
        "job": "Occupy two defenders, and finish the one chance.",
        "home": (0.50, 0.16),
        "beats": [
            {"label": "PIN", "from": (0.50, 0.16), "to": (0.50, 0.20),
             "zone": (0.34, 0.08, 0.66, 0.26),
             "say": "He holds both centre backs. Every second he keeps them "
                    "occupied is a second the midfield runs into space he will "
                    "never touch. Most of his work never reaches the highlights."},
            {"label": "BEND THE RUN", "from": (0.50, 0.20), "to": (0.30, 0.12),
             "say": "The run is bent, not straight. Across the defender's face "
                    "he is onside a fraction longer and the goalkeeper cannot "
                    "see him."},
            {"label": "ATTACK THE SIX", "from": (0.30, 0.12), "to": (0.48, 0.07),
             "say": "And he ends up in the six yard box. Not admiring the "
                    "cross. In front of the man marking him, where the tap in "
                    "lives."},
        ],
    },
    "GK": {
        "title": "THE MODERN GOALKEEPER",
        "job": "Defend a goal, and start the attack from inside it.",
        "home": (0.50, 0.92),
        "beats": [
            {"label": "SWEEP", "from": (0.50, 0.92), "to": (0.50, 0.80),
             "zone": (0.28, 0.74, 0.72, 0.92),
             "say": "He starts high. The space between him and his defenders is "
                    "the space a through ball is aimed at, and if he is on his "
                    "line it is the striker who gets there first."},
            {"label": "SET", "from": (0.50, 0.80), "to": (0.50, 0.88),
             "say": "Then he is set before the shot. Feet still, weight "
                    "forward. A keeper still moving when the ball is struck is "
                    "diving after it, not to it."},
            {"label": "PLAY OUT", "from": (0.50, 0.88), "to": (0.22, 0.74),
             "say": "And he is the first passer. The team that beats a press "
                    "usually does it because the goalkeeper was brave enough to "
                    "be an option."},
        ],
    },
}

# ESPN publishes finer labels than we hold roles for; map them onto one.
ESPN_TO_ROLE = {
    "GK": "GK", "G": "GK",
    "RB": "RB", "RWB": "RB",
    "LB": "LB", "LWB": "LB",
    "CD": "CB", "CD-L": "CB", "CD-R": "CB", "D": "CB", "SW": "CB",
    "DM": "CDM", "CDM": "CDM", "DM-L": "CDM", "DM-R": "CDM",
    "CM": "CM", "CM-L": "CM", "CM-R": "CM", "M": "CM",
    "LM": "LW", "RM": "RW",
    "AM": "CAM", "CAM": "CAM", "AM-L": "CAM", "AM-R": "CAM",
    "LW": "LW", "RW": "RW", "LF": "LW", "RF": "RW",
    "CF": "ST", "CF-L": "ST", "CF-R": "ST", "ST": "ST", "F": "ST", "FW": "ST",
}


def role_for(espn_abbrev: str) -> str:
    """The role key for a published ESPN position, or '' if we cannot tell."""
    a = (espn_abbrev or "").upper().strip()
    if a in ESPN_TO_ROLE:
        return ESPN_TO_ROLE[a]
    # "CD-L" style labels we have not listed explicitly: fall back to the stem.
    stem = a.split("-")[0]
    return ESPN_TO_ROLE.get(stem, "")


def describe(role_key: str) -> dict | None:
    return ROLES.get(role_key)

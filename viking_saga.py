#!/usr/bin/env python
"""SAGA OF THE NORTH — Season 1. A serialised Viking saga in ten episodes.

This is a SERIES, not a pile of shorts. Episode 1 is a man launching a ship alone; episode 10 is
what he became. Each episode stands on its own for a cold scroller, but carries the thread forward
so anyone who watches two wants the third.

Every episode is built to the same shape, because it is the shape that holds a viewer to the end:

    BADGE     EP. 05 — THE SHIELD WALL         (says "there are more of these")
    HOOK      (0-2.5s)  one line that makes stopping cheaper than scrolling
    ACTION    (3 shots) the Viking does the thing — kinetic, physical, loud
    LESSON    (the turn) the narrator names the law the action just proved
    CHALLENGE (the end)  the law aimed straight at the viewer: "your wall", "your oar"
    NEXT      (end card) EP. 06 — THE BETRAYAL

`saga` is written to be SPOKEN — short sentences, hard stops, ~50 words so it lands in ~22s.
`lesson` is the quote card that holds on the freeze frame. That card is what gets screenshotted,
so it is always second person and always actionable.
`impact` marks which shot gets the camera shake + low boom in the edit.
"""

# Locked look for every shot — the hero comes from the reference image so his face never drifts
# across ten episodes. Continuity is what makes it read as a series instead of stock clips.
STYLE = ("Epic cinematic Viking action film, photorealistic, FULL-BODY, anamorphic 35mm film look, "
         "dramatic cold Nordic light, storm and mist, film grain, ultra sharp 4k. REAL ACTION-MOVIE "
         "MOTION: constant kinetic moving camera, real fight choreography, physical stunt action, "
         "motion blur, fast dynamic movement in every shot — never a static or frozen shot. "
         "AUDIO: natural action foley and ambient sound ONLY — wind, sea, footsteps, hammer, shield "
         "and axe impacts, and wordless roars. Absolutely NO spoken dialogue, NO chanting, NO "
         "singing, NO discernible words, and NEVER the word 'Valhalla'. No on-screen text. "
         "The SAME Viking warrior from the reference image. ")

SERIES = "SAGA OF THE NORTH"
SEASON = 1

EPISODES = [
    {
        "ep": 1,
        "slug": "firstlight",
        "title": "FIRST LIGHT",
        "hook": "NOBODY CAME TO HELP HIM PUSH.",
        "impact": 1,
        "shots": [
            "Freezing blue pre-dawn on an empty shoreline. The warrior alone drags a heavy longship down "
            "the shingle toward the water, boots slipping, every muscle straining — no crew, no help, "
            "his breath steaming in the cold.",
            "LOW WATER-LEVEL SHOT as he SHOVES the ship into the breaking surf and hauls himself aboard, "
            "takes up a single oar and begins to row out alone into the grey open sea.",
            "WIDE CRANE-UP: the lone ship pulling for the horizon as the sun cracks the clouds — and "
            "behind him, one by one, other ships begin launching from the shore to follow.",
        ],
        "beats": [
            "He launched alone. Nobody helped him push.",
            "No crew. No witnesses. Nobody clapping. He put his back into the oar anyway.",
            "And here is the part nobody tells you. The ships that follow you only launch after they "
             "watch you go first. So go first.",
        ],
        "lesson": "THEY FOLLOW\nAFTER YOU LAUNCH.\nGO FIRST.",
        "comment": "Waiting for a crew, or rowing out alone?",
        "caption": ("EP.1 — FIRST LIGHT \U0001F6A2  The ships that follow you only launch after they watch "
                    "you go first.\n\nAre you waiting for a crew, or rowing out alone?"),
    },
    {
        "ep": 2,
        "slug": "forge",
        "title": "THE FORGE",
        "hook": "THE IRON BEGGED TO BREAK.",
        "impact": 1,
        "shots": [
            "Night forge, firelight only. EXTREME CLOSE PUSH-IN on white-hot iron pulled from the coals, "
            "the warrior's scarred hands turning it on the anvil, sparks crawling across his face.",
            "HAMMER STRIKES in hard rhythm — sparks EXPLODING off the anvil with every blow, the iron "
            "flattening and folding, his arm driving down again and again, sweat and firelight.",
            "SLOW REVEAL: the finished axe quenched in a hiss of steam, then raised into the firelight — "
            "MATCH CUT to that same axe swinging in daylight, splitting an enemy shield clean in half.",
        ],
        "beats": [
            "Iron does not become a blade in the fire.",
            "It becomes a blade under the hammer. Every blow it survives is a blow it can deliver.",
            "So when it hurts, understand what is happening to you. You are not being broken. You are "
             "being finished.",
        ],
        "lesson": "YOU ARE NOT\nBEING BROKEN.\nYOU ARE BEING FORGED.",
        "comment": "What's the hammer in your life right now?",
        "caption": ("EP.2 — THE FORGE \U0001F528  Iron becomes a blade under the hammer, not in the fire.\n\n"
                    "You are not being broken. You are being forged. What's your hammer?"),
    },
    {
        "ep": 3,
        "slug": "oath",
        "title": "THE OATH",
        "hook": "FORTY MEN KNELT. ONE WAS LYING.",
        "impact": 1,
        "shots": [
            "Night, roaring bonfire. LOW-ANGLE PUSH-IN on the warrior kneeling before the flames, his axe "
            "raised across both palms; around him forty warriors kneel in a ring, firelight flickering on "
            "their faces as they chant low.",
            "The warrior RISES and ROARS, thrusting the axe at the black sky — the warband ERUPT to their "
            "feet, pounding shields in unison, sparks and embers whirling up into the night.",
            "SLOW ORBIT around the standing warband, shields still pounding as one — and the orbit settles "
            "on ONE man at the back who is not shouting, his eyes down, half in shadow.",
        ],
        "beats": [
            "Before the blood, there is the oath.",
            "Sworn out loud. Sworn in front of men who will check on you. That is the only reason it "
             "holds.",
            "A promise made in the dark to yourself is a wish. Say it out loud and it becomes a debt. "
             "But look closely. One of them is already lying.",
        ],
        "lesson": "A PROMISE IN SILENCE\nIS A WISH.\nSAY IT OUT LOUD.",
        "comment": "Say your oath in the comments. Out loud.",
        "caption": ("EP.3 — THE OATH \U0001F525  A promise made in silence is a wish. Sworn out loud, it "
                    "becomes a debt.\n\nSay your oath in the comments — make it real. (Watch the man at "
                    "the back...)"),
    },
    {
        "ep": 4,
        "slug": "storm",
        "title": "THE STORM",
        "hook": "EVERY MAN ABOARD WANTED TO TURN BACK.",
        "impact": 1,
        "shots": [
            "Dawn on a black freezing sea. SWEEPING CRANE SHOT over the longship climbing a towering storm "
            "wave, warriors hauling the oars through freezing spray, faces raw with cold and fear.",
            "The wave BREAKS over the ship — a wall of white water smashes across the deck, men thrown "
            "sideways, an oar ripped loose; at the dragon-prow the warrior grips the rail and ROARS into "
            "the storm, refusing to give the sea his back.",
            "LOW HERO ANGLE from the deck: the ship punches through the crest into open grey water, the "
            "warrior pointing his axe forward, the crew finding the rhythm and hauling again as one.",
        ],
        "beats": [
            "Every man on that deck wanted to turn back.",
            "The sea does not care what you want. It asks one question, over and over. Do you keep "
             "rowing.",
            "Fear is not the storm. Fear is the moment you stop pulling the oar. Keep pulling.",
        ],
        "lesson": "FEAR IS NOT THE STORM.\nFEAR IS WHEN YOU\nSTOP ROWING.",
        "comment": "What storm are you rowing through right now?",
        "caption": ("EP.4 — THE STORM \U0001F30A  The sea only asks one question: do you keep rowing?\n\n"
                    "What storm are you rowing through right now?"),
    },
    {
        "ep": 5,
        "slug": "shieldwall",
        "title": "THE SHIELD WALL",
        "hook": "THEY BROKE. HE DIDN'T.",
        "impact": 1,
        "shots": [
            "Grey muddy battlefield under a bruised sky. LOW TRACKING SHOT along the Viking shield wall "
            "locking together shield by shield, the warrior at dead center driving his boot into the mud, "
            "jaw set, as a thunderous enemy charge storms toward them through the rain.",
            "Kinetic HANDHELD SHOT, the camera slammed by the hit: the charge CRASHES into the shield "
            "wall — a brutal crush of shields, splintering spears and bodies, the warrior roaring and "
            "heaving forward, mud and blood exploding into the air, men buckling either side of him.",
            "PUSH-IN on the warrior alone at the center — bleeding, shield splintered, one boot still "
            "planted — as the broken enemy line falls back and his brothers re-lock the wall around him.",
        ],
        "beats": [
            "A thousand men came to break one line.",
            "The wall bent. Men fell. He did not step back.",
            "This is the law of the North. One shield is a man. A thousand shields is a storm. You "
             "are not weak. You are alone. Go and build your wall.",
        ],
        "lesson": "YOU ARE NOT WEAK.\nYOU ARE ALONE.\nBUILD YOUR WALL.",
        "comment": "Who's in your shield wall? Tag them.",
        "caption": ("EP.5 — THE SHIELD WALL ⚔️  One shield is a man. A thousand shields is a storm.\n\n"
                    "You are not weak — you are alone. Tag the person who holds the line with you."),
    },
    {
        "ep": 6,
        "slug": "betrayal",
        "title": "THE BETRAYAL",
        "hook": "THE MAN WHO OPENED THE GATE HAD SWORN.",
        "impact": 2,
        "shots": [
            "Dead of night inside a Viking stronghold. A hooded figure moves through sleeping warriors and "
            "quietly LIFTS THE BAR from the great gate — the same man who stood at the back of the oath fire.",
            "The gate SWINGS OPEN and enemy raiders pour through with torches — chaos, fire catching the "
            "thatch, warriors scrambling from their furs for weapons, the warrior waking to a hall already burning.",
            "The warrior FIGHTS THROUGH the smoke to the gate and finds the traitor there — a frozen "
            "half-second between them in the firelight — then he raises his axe and the man runs.",
        ],
        "beats": [
            "The gate was not broken.",
            "It was opened from the inside, by a man who knelt at that fire and swore.",
            "Learn this early. Not everyone standing in your wall is holding a shield. Some are just "
             "standing close enough to see where the bar is.",
        ],
        "lesson": "NOT EVERYONE\nIN YOUR WALL\nIS HOLDING A SHIELD.",
        "comment": "Ever had a gate opened from the inside?",
        "caption": ("EP.6 — THE BETRAYAL \U0001F5E1️  The gate wasn't broken. It was opened from the inside.\n\n"
                    "Not everyone in your wall is holding a shield. Who found that out the hard way?"),
    },
    {
        "ep": 7,
        "slug": "fall",
        "title": "THE FALL",
        "hook": "HE COULDN'T STAND. HE STOOD.",
        "impact": 0,
        "shots": [
            "Rain-hammered battlefield at dusk. The warrior is SMASHED to the ground by a shield bash, "
            "hitting the mud hard, his axe skidding out of his hand, the enemy already closing on him.",
            "LOW-ANGLE from the mud: his shaking hand drags through the muck, closes on the axe haft, and "
            "he FORCES himself onto one knee — then to his feet, blood running down his face, breathing "
            "like a bellows.",
            "HERO SHOT, slow rising crane: the warrior stands to full height in the downpour and ROARS, "
            "raising the axe, the advancing enemy line faltering in front of him.",
        ],
        "beats": [
            "They put him face down in the mud.",
            "His hand would not close. His legs would not hold him. He stood up anyway.",
            "That is the whole secret, and it is not glamorous. Strength is not never falling. "
             "Strength is the getting up that nobody claps for.",
        ],
        "lesson": "STRENGTH IS NOT\nNEVER FALLING.\nIT'S GETTING UP.",
        "comment": "What knocked you down this year?",
        "caption": ("EP.7 — THE FALL \U0001F525  Strength is not never falling. It's the getting up nobody "
                    "claps for.\n\nWhat knocked you down this year?"),
    },
    {
        "ep": 8,
        "slug": "outnumbered",
        "title": "OUTNUMBERED",
        "hook": "FORTY MEN. AGAINST SIX HUNDRED.",
        "impact": 1,
        "shots": [
            "Wide desolate valley at grey first light. A tiny Viking warband stands shoulder to shoulder "
            "as an enemy host of hundreds pours over the far ridge; SLOW PUSH-IN on the warrior at the "
            "front, counting them, unafraid.",
            "The warrior BREAKS INTO A CHARGE straight at the host — kinetic handheld running shot, his "
            "warband roaring after him, the two lines closing and COLLIDING in a shock of shields, axes "
            "and dust.",
            "PUSH-IN through the chaos onto the warrior mid-fight, axe swinging, absolutely calm in the "
            "middle of a storm of men.",
        ],
        "beats": [
            "Forty men. Six hundred. He counted them.",
            "And he charged anyway. The odds have never once decided a battle.",
            "They only decide who shows up. Everyone still waiting for fair conditions is standing on "
             "the ridge, watching. Charge.",
        ],
        "lesson": "THE ODDS DON'T DECIDE.\nTHEY ONLY DECIDE\nWHO SHOWS UP.",
        "comment": "Who else is done waiting for perfect timing?",
        "caption": ("EP.8 — OUTNUMBERED ⚔️  The odds never decided a battle — they decided who showed up.\n\n"
                    "Who else is done waiting for perfect conditions?"),
    },
    {
        "ep": 9,
        "slug": "pyre",
        "title": "THE PYRE",
        "hook": "NOBODY ASKED HOW LONG HE LIVED.",
        "impact": 2,
        "shots": [
            "Dawn over a misty fjord. SLOW DOLLY across the water as a burning longship drifts out to sea, "
            "a fallen warrior laid upon it wrapped in furs, flames climbing the mast.",
            "On the black shore the warrior stands watching, grief hard on his face, his warband gathered "
            "silent behind him, ravens circling in the grey sky.",
            "CRANE-UP as the warrior RAISES HIS AXE in salute and the whole warband lift their weapons at "
            "once with a single shout, the burning ship blazing against the dawn.",
        ],
        "beats": [
            "They gave him to the sea and the fire.",
            "And not one man there asked how long he had lived. They only asked what he did with it.",
            "You will get a morning like this one day. The only question is what they will be able to "
             "say. Go and earn it.",
        ],
        "lesson": "THEY WON'T ASK\nHOW LONG YOU LIVED.\nONLY WHAT YOU DID.",
        "comment": "What will they be able to say about you?",
        "caption": ("EP.9 — THE PYRE \U0001F525  Nobody asked how long he lived — only what he did with it.\n\n"
                    "What will they be able to say about you?"),
    },
    {
        "ep": 10,
        "slug": "return",
        "title": "THE RETURN",
        "hook": "HE LEFT ALONE. LOOK WHO CAME BACK.",
        "impact": 0,
        "shots": [
            "Golden evening light over the home fjord. WIDE CRANE SHOT: an entire FLEET of longships rows "
            "into the bay in formation, sails full — and at the prow of the lead ship stands the warrior, "
            "scarred, older, silent.",
            "The village floods down to the shore to meet them, cheering; the warrior steps off into the "
            "shallows and walks up the beach through his own people as they part for him.",
            "CLOSE, quiet: the warrior kneels in front of a young boy at the front of the crowd and PLACES "
            "HIS AXE in the boy's hands, closing the small fingers around the haft — then stands and looks "
            "out at the sea.",
        ],
        "beats": [
            "He left this beach alone, pushing one ship into the water with nobody watching.",
            "He came back with a fleet.",
            "And then he gave the axe away. Because you are not building a legend. You are building "
             "the men who come after you. Start your saga.",
        ],
        "lesson": "YOU'RE NOT BUILDING\nA LEGEND. YOU'RE BUILDING\nWHO COMES AFTER YOU.",
        "comment": "Season 1 done. Who should the axe go to next?",
        "caption": ("EP.10 — THE RETURN ⚔️  He left alone and came back with a fleet — then gave the "
                    "axe away.\n\nYou're not building a legend. You're building who comes after you. "
                    "SEASON 1 COMPLETE — who should carry the axe into Season 2?"),
    },
]

BY_SLUG = {e["slug"]: e for e in EPISODES}
BY_EP = {e["ep"]: e for e in EPISODES}


def next_tease(ep):
    """End-card text pointing at the next episode — the reason someone follows instead of scrolling."""
    nxt = BY_EP.get(ep["ep"] + 1)
    if nxt:
        return f"NEXT  EP.{nxt['ep']}  {nxt['title']}"
    return "SEASON 1 COMPLETE"


def badge(ep):
    """On-screen episode badge, e.g. 'EP.5 — THE SHIELD WALL'."""
    return f"EP.{ep['ep']}  {ep['title']}"


def get(slugs=None, eps=None, count=None):
    """Episodes by slug, by episode number, or the first `count` in season order."""
    if slugs:
        return [BY_SLUG[s] for s in slugs if s in BY_SLUG]
    if eps:
        return [BY_EP[n] for n in eps if n in BY_EP]
    return EPISODES[:count] if count else EPISODES

# The spoken script is the beats joined; kept as `saga` for callers that want one blob.
for _e in EPISODES:
    _e["saga"] = " ".join(_e["beats"])

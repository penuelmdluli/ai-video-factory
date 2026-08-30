"""
Hashtags for the dance posts — measured, rotated, and regional.

Owner call 2026-08-30: reuse the tags that were working, and widen past South
Africa into Swaziland, Botswana and the amapiano audience.

The set below is not invented. It comes from reading 83 hashtagged reels off
the profile on 2026-08-30 and pairing every tag with the views of the posts
carrying it.

READ THE NUMBERS CAREFULLY, BECAUSE THEY MISLEAD
------------------------------------------------
Sorting tags by average views per post puts #zinhleshutitdown top at 1.3M and
#sandton, #sastreets and #squidboycally joint second at 1.03M. All four are
noise: they appear on three or four posts each and simply happen to sit on the
same viral cluster. A tag used four times has not proven anything; it has
inherited the score of one good video.

The tags worth trusting are the ones used often AND averaging well:

    #southafrica     45 posts   292K avg
    #mzansi          40 posts   296K avg
    #trending        28 posts   344K avg
    #mzansivibes     29 posts   269K avg
    #sareels         19 posts   443K avg
    #amapiano        46 posts   186K avg
    #fyp             59 posts   199K avg
    #viral           52 posts   203K avg

#mzansibabystars is the most-used tag on the profile at 75 posts, and it is
deliberately absent below: the owner is moving this content off that brand.

WHY THE POOLS ROTATE
--------------------
Posting an identical block of twenty tags on every upload is a spam signal,
and it also means every post competes in exactly the same feeds. CORE goes on
everything because it is what reliably works; the rest is drawn from pools
that rotate with the post, so two consecutive posts never carry the same tag
set while both stay on-topic.
"""
import random

# Always. High volume AND high average — the ones that earned it.
CORE = ["southafrica", "mzansi", "amapiano", "fyp", "viral", "trending"]

# Regional widening, owner call 2026-08-30. Unproven on this profile so far —
# they are a bet on the same content travelling across the border, not a
# measured result, and should be reviewed once there are numbers behind them.
REGIONAL = ["swaziland", "eswatini", "botswana", "lesotho", "namibia",
            "zimbabwe", "africa", "africandance"]

# Format and content pools — one slice of each per post.
POOLS = {
    "reach":   ["sareels", "reels", "mzansivibes", "southafricantiktok",
                "explorepage", "foryou"],
    "dance":   ["amapianodance", "dancechallenge", "pantsula", "dancevideo",
                "sadance", "amapianovibes"],
    "family":  ["safamily", "africanfamily", "familygoals", "mzansifamily",
                "gogo", "mkhulu"],
    "hook":    ["waitforit", "watchtillend", "funny", "comedy", "mustwatch"],
    "place":   ["soweto", "johannesburg", "sastreets", "sabraai", "kasi",
                "township"],
}

# Per-character tags so a recurring face builds its own searchable identity —
# the same logic that makes the cast worth locking in the first place.
CHARACTER_TAGS = {
    "mkhulu": ["mkhulu", "grandpa", "gogoandmkhulu"],
    "gogo":   ["gogo", "gogolove", "grandma"],
    "auntie": ["auntie", "mzansiauntie", "africanauntie"],
    "cousin": ["cousin", "amapianoboy", "sayouth"],
    "kids":   ["cutebaby", "babydance", "babyreels", "twins"],
}


def build(character: str = "", count: int = 18, seed=None) -> list:
    """Return a rotated tag list: CORE + character + one slice per pool.

    count caps the total. The proven posts on this profile carry roughly
    15-25 tags, so the default sits inside what already works rather than
    inventing a new convention.
    """
    rng = random.Random(seed)
    tags = list(CORE)

    for t in CHARACTER_TAGS.get(character, [])[:2]:
        if t not in tags:
            tags.append(t)

    # Two regional per post, rotated — enough to reach across the border
    # without burying the South African core that actually performs.
    for t in rng.sample(REGIONAL, min(2, len(REGIONAL))):
        if t not in tags:
            tags.append(t)

    for pool in POOLS.values():
        for t in rng.sample(pool, min(2, len(pool))):
            if t not in tags and len(tags) < count:
                tags.append(t)

    return tags[:count]


def as_text(character: str = "", count: int = 18, seed=None) -> str:
    return " ".join("#" + t for t in build(character, count, seed))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", default="")
    ap.add_argument("--count", type=int, default=18)
    ap.add_argument("--n", type=int, default=3, help="show N rotations")
    a = ap.parse_args()
    for i in range(a.n):
        print(f"{i+1}. {as_text(a.character, a.count, seed=i)}\n")

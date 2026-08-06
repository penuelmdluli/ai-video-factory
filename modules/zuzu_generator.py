"""Zuzu & Friends — dynamic content engine for ENDLESS variety.

Instead of a handful of fixed lessons, this generates a fresh educational song
every run: a rotating cast of friends, dozens of topics, varied settings, and
Claude-written lyrics/scenes. So the channel never repeats and always teaches.

- Each CHARACTER has a fixed image seed -> that character looks consistent across
  all its videos (brand consistency), while topic/setting/song vary for freshness.
- generate_lesson() returns a dict compatible with make_zuzu.py.
"""
import json, random
from config import ANTHROPIC_API_KEY

STYLE = "vibrant colors, soft lighting, wholesome, cinematic kids animation, wide shot"

# Rotating cast — each visually locked + a fixed seed for cross-video consistency.
CAST = {
    "zuzu":  {"name": "Zuzu",  "seed": 777,
              "desc": "Zuzu the baby elephant, round chubby body, lavender-grey skin, big sparkly eyes, yellow star bib, cute 3D Pixar cartoon"},
    "bella": {"name": "Bella", "seed": 101,
              "desc": "Bella the baby bunny, fluffy soft pink and white fur, long floppy ears, big round eyes, little blue bow, cute 3D Pixar cartoon"},
    "leo":   {"name": "Leo",   "seed": 202,
              "desc": "Leo the lion cub, fluffy golden fur, soft round mane, big friendly eyes, cheerful smile, cute 3D Pixar cartoon"},
    "gigi":  {"name": "Gigi",  "seed": 303,
              "desc": "Gigi the baby giraffe, soft yellow fur with gentle brown spots, long neck, big eyelashes, happy face, cute 3D Pixar cartoon"},
    "momo":  {"name": "Momo",  "seed": 404,
              "desc": "Momo the baby monkey, soft brown fur, big curious eyes, round ears, tiny green scarf, cute 3D Pixar cartoon"},
    "pip":   {"name": "Pip",   "seed": 505,
              "desc": "Pip the baby penguin, fluffy black and white, round belly, tiny orange feet, big happy eyes, cute 3D Pixar cartoon"},
}
# Zuzu stars most often (brand mascot); friends rotate in.
STAR_WEIGHTS = [("zuzu", 5), ("bella", 2), ("leo", 2), ("gigi", 2), ("momo", 2), ("pip", 2)]

SETTINGS = [
    "a sunny green meadow full of flowers", "a cozy starry night sky",
    "a colorful sandy beach by the sea", "a fun green jungle with big leaves",
    "a bright cheerful playground park", "outer space with planets and stars",
    "a magical forest with glowing mushrooms", "a snowy winter wonderland",
    "a friendly farmyard with a red barn", "a rainbow candy land",
]
SONG_STYLES = ["cheerful upbeat", "gentle sweet", "bouncy playful",
               "calm soothing", "fun marching-band", "happy sing-along"]

# Big rotating topic bank — every one teaches something useful.
TOPICS = [
    "the ABC alphabet song", "counting from 1 to 10", "counting from 1 to 20",
    "learning colors of the rainbow", "learning shapes: circle, square, triangle",
    "days of the week", "the four seasons", "weather: sun, rain, wind, snow",
    "farm animals and their sounds", "jungle animals", "sea animals under the ocean",
    "learning body parts: head, arms, legs", "how to brush your teeth",
    "washing your hands to stay clean", "healthy fruits to eat", "yummy vegetables",
    "the magic words please and thank you", "sharing and being kind to friends",
    "feelings: happy, sad, excited", "saying sorry and forgiving",
    "opposites: big and small", "opposites: fast and slow", "opposites: up and down",
    "getting dressed in the morning", "cleaning up our toys", "bath time fun",
    "going to sleep at bedtime", "the sun, the moon and the stars",
    "how plants and flowers grow", "cars, trains, buses and planes",
    "community helpers: doctor, firefighter, teacher", "counting backwards from 10",
    "the five senses: see, hear, smell, taste, touch", "hello and goodbye in a friendly way",
    "Twinkle Twinkle Little Star", "Old MacDonald Had a Farm", "The Wheels on the Bus",
    "Itsy Bitsy Spider", "Row Row Row Your Boat", "If You're Happy and You Know It",
    "Five Little Ducks", "Baa Baa Black Sheep",
]

_GEN_PROMPT = """You are a children's educational songwriter for a toddler/preschool YouTube channel (like CoComelon). Write a short, fun, SAFE, EDUCATIONAL sing-along song.

Topic to teach: {topic}
Star character (already drawn, do NOT redescribe their look): {star_name}
Setting: {setting}

Return ONLY valid JSON (no prose) with EXACTLY these keys:
{{
 "title": "short catchy title (max 6 words, no emoji)",
 "category": "one or two words, e.g. letters, numbers, colors, animals, manners, bedtime",
 "lyrics": "song lyrics with \\n line breaks and [verse] tags; simple, repetitive, teaches the topic clearly and correctly; 6-10 short lines; wholesome and age 2-5 appropriate",
 "captions": ["12 very short on-screen caption chunks of 2-3 words each, in singing order, matching the lyrics"],
 "scenes": ["6 short visual scene ACTIONS for {star_name} that illustrate the lesson (e.g. 'points at a big letter A', 'counts three red apples'); do NOT describe the character's appearance, only the action/props; keep each under 14 words"],
 "song_style": "{song_style}",
 "tags": ["8 lowercase youtube tags: kids learning + the specific topic"]
}}
Rules: factually correct, gentle, positive. No scary or unsafe content. Numbers/letters/colors must be accurate."""

def _pick(weighted):
    pool = []
    for k, w in weighted: pool += [k] * w
    return random.choice(pool)

def generate_lesson(topic=None, star_id=None, setting=None, rng=None):
    """Generate a fresh lesson dict. Falls back to a simple template if Claude
    is unavailable so the pipeline never hard-fails."""
    r = rng or random
    topic = topic or r.choice(TOPICS)
    star_id = star_id or _pick(STAR_WEIGHTS)
    setting = setting or r.choice(SETTINGS)
    song_style = r.choice(SONG_STYLES)
    star = CAST[star_id]

    lesson = None
    if ANTHROPIC_API_KEY:
        try:
            import anthropic
            claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            prompt = _GEN_PROMPT.format(topic=topic, star_name=star["name"],
                                        setting=setting, song_style=song_style)
            msg = claude.messages.create(model="claude-haiku-4-5-20251001",
                    max_tokens=1600, messages=[{"role": "user", "content": prompt}])
            txt = msg.content[0].text
            js = txt[txt.find("{"): txt.rfind("}") + 1]
            data = json.loads(js)
            lesson = data
        except Exception as e:
            print(f"[zuzu-gen] Claude gen failed ({e}); using template fallback")

    if not lesson:  # safe fallback
        lesson = {
            "title": topic.title()[:60], "category": "learning",
            "lyrics": f"[verse]\nLet's learn about {topic} today,\nwith {star['name']} we sing and play!\n[verse]\nLearning is so much fun,\nsinging together, everyone!",
            "captions": ["Let's learn!", topic.split()[0], "with", star["name"], "Sing", "and play!",
                         "Learning", "is fun!", "Together", "we sing!", "Yay!", star["name"] + "!"],
            "scenes": [f"happily introducing today's lesson about {topic}",
                       "pointing at colorful learning props, smiling",
                       "counting or showing the lesson items joyfully",
                       "clapping and dancing while learning",
                       "celebrating with sparkles and confetti",
                       "waving goodbye happily"],
            "song_style": song_style, "tags": ["kids learning", "nursery rhymes", "educational", "toddler"],
        }

    # attach production metadata the pipeline needs
    lesson["id"] = f"{star_id}_{abs(hash(topic)) % 100000}"
    lesson["star_id"] = star_id
    lesson["star_name"] = star["name"]
    lesson["star_desc"] = star["desc"]
    lesson["star_seed"] = star["seed"]
    lesson["setting"] = setting
    lesson["song_prompt"] = (f"{lesson.get('song_style', song_style)} children's educational song, "
                             f"cute gentle kids voice, playful melody, wholesome, catchy")
    # scene prompts = locked character + action + setting + style
    lesson["scene_prompts"] = [f"{star['desc']}, {a}, in {setting}, {STYLE}"
                               for a in lesson["scenes"][:6]]
    return lesson

def build_description(lesson):
    lyric = str(lesson.get("lyrics", "")).replace("[verse]", "").strip()
    star = lesson.get("star_name", "Zuzu")
    return (f"{lesson['title']} with {star} and friends! Sing, learn and play along with Zuzu & Friends.\n\n"
            f"A fun, gentle way for toddlers and preschoolers to learn while singing. Safe and made for kids.\n\n"
            f"Lyrics:\n{lyric}\n\nSubscribe to Zuzu & Friends for a new learning song every day!")

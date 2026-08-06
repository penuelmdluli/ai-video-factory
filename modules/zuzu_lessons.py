"""Zuzu & Friends — edutainment lesson library.

Each lesson teaches something useful (letters, numbers, colors, animals,
manners) through a sung rhyme with Zuzu the baby elephant demonstrating it.
Public-domain melodies only. Scene prompts keep the locked character + a wide
16:9 teaching moment. Add lessons freely — the auto-pipeline rotates through them.
"""

# Locked character anchor — identical in every scene (consistency).
ZUZU = ("Zuzu the baby elephant, round chubby body, lavender-grey skin, big "
        "sparkly eyes, yellow star bib, cute 3D Pixar cartoon")
STYLE = "vibrant colors, soft lighting, wholesome, cinematic kids animation, wide shot"

LESSONS = [
    {
        "id": "abc",
        "title": "ABC Song",
        "category": "letters",
        "song_prompt": "cheerful children's alphabet song, cute gentle kids voice, playful piano and bells, upbeat, wholesome",
        "lyrics": (
            "[verse]\nA B C D E F G,\nH I J K L M N O P,\nQ R S T U V,\n"
            "W X Y and Z.\n[verse]\nNow I know my ABCs,\nnext time won't you sing with me!"
        ),
        "captions": ["A B C","D E F G","H I J K","L M N O P","Q R S T U V","W X Y Z",
                     "Now I know","my ABCs!","Next time","sing with me!","A B C","with Zuzu!"],
        "scenes": [
            "pointing happily at three giant colorful floating letters A B C, bright classroom sky",
            "standing beside glowing letter blocks D E F G on soft grass, smiling",
            "hopping between big rainbow letters H I J K L, cheerful meadow",
            "at a cute chalkboard showing letters M N O P, holding a pointer with its trunk",
            "juggling floating letters Q R S T U V, sparkles around, joyful",
            "clapping in front of a big rainbow alphabet A to Z, confetti, celebrating",
        ],
        "tags": ["abc song","alphabet","learn letters","phonics","kids learning","preschool"],
    },
    {
        "id": "numbers",
        "title": "Count to 10",
        "category": "numbers",
        "song_prompt": "happy children's counting song, cute gentle kids voice, bouncy playful melody, wholesome",
        "lyrics": (
            "[verse]\nOne, two, three, four, five,\nZuzu counts the stars alive!\n"
            "[verse]\nSix, seven, eight, nine, ten,\nlet us count them all again!"
        ),
        "captions": ["One, two","three, four, five!","Count with","Zuzu!","Six, seven","eight,",
                     "nine, ten!","Count them","all again!","1 2 3","4 5... 10!","Great job!"],
        "scenes": [
            "pointing at one big glowing number 1 and one star, night meadow",
            "counting two then three sparkling stars floating, numbers 2 and 3 glowing",
            "with four and five golden stars, big numbers 4 5, wide starry field",
            "counting six seven eight stars, glowing numbers, joyful",
            "reaching for nine and ten stars, big number 10 glowing bright",
            "surrounded by all ten stars and a big number 10, clapping, celebrating",
        ],
        "tags": ["counting song","numbers 1 to 10","learn to count","123","kids learning","preschool"],
    },
    {
        "id": "colors",
        "title": "Colors Song",
        "category": "colors",
        "song_prompt": "cheerful children's colors song, cute gentle kids voice, playful bright melody, wholesome",
        "lyrics": (
            "[verse]\nRed and yellow, green and blue,\nZuzu loves these colors too!\n"
            "[verse]\nPurple, orange, pink so bright,\nlearning colors feels so right!"
        ),
        "captions": ["Red","and yellow","green","and blue!","Purple","orange","pink!","So bright!",
                     "Learn colors","with Zuzu!","Red green blue","Yay!"],
        "scenes": [
            "holding a big shiny red apple, bright cheerful meadow",
            "under a big yellow sun holding a yellow balloon, happy",
            "sitting on bright green grass hugging a green leaf, smiling",
            "reaching up to a big blue balloon in a blue sky",
            "smelling a big purple flower, sparkles, joyful",
            "in front of a huge rainbow with red orange yellow green blue purple, celebrating",
        ],
        "tags": ["colors song","learn colors","rainbow","kids learning","preschool","toddler"],
    },
    {
        "id": "animals",
        "title": "Animal Sounds",
        "category": "animals",
        "song_prompt": "fun children's animal sounds song, cute gentle kids voice, playful bouncy melody, wholesome",
        "lyrics": (
            "[verse]\nThe cow says moo, the duck says quack,\nthe dog says woof and barks right back!\n"
            "[verse]\nThe cat says meow, the sheep says baa,\nsinging with Zuzu, hurrah!"
        ),
        "captions": ["The cow","says MOO!","The duck","says QUACK!","The dog","says WOOF!",
                     "The cat","says MEOW!","The sheep","says BAA!","Sing with","Zuzu!"],
        "scenes": [
            "standing next to a friendly cartoon cow on a green farm, sunny",
            "beside a cute yellow duck near a little pond, cheerful",
            "playing with a happy puppy dog on the grass",
            "petting a soft cartoon cat, smiling, cozy farm",
            "next to a fluffy white sheep in a meadow",
            "surrounded by the cow duck dog cat and sheep, all happy together, celebrating",
        ],
        "tags": ["animal sounds","animals for kids","learn animals","farm animals","kids learning"],
    },
    {
        "id": "twinkle",
        "title": "Twinkle Twinkle Little Star",
        "category": "bedtime",
        "song_prompt": "gentle children's lullaby, cute soft kids voice, soft piano and twinkle bells, slow bedtime, warm",
        "lyrics": (
            "[verse]\nTwinkle, twinkle, little star,\nHow I wonder what you are.\n"
            "Up above the world so high,\nLike a diamond in the sky.\n"
            "[verse]\nTwinkle, twinkle, little star,\nHow I wonder what you are."
        ),
        "captions": ["Twinkle,","twinkle,","little star","How I wonder","what you are","Up above",
                     "the world","so high","Like a diamond","in the sky","Twinkle,","little star"],
        "scenes": [
            "standing in a wide dreamy meadow at night, waving, soft starry sky",
            "looking up in wonder at a big starry night sky, crescent moon",
            "pointing its trunk up at one big glowing yellow star, sparkles",
            "sitting on a grassy hill under a big glowing moon and stars",
            "hugging a big sparkly yellow star, soft night glow",
            "lying down sleepy and yawning under the moon and stars, cozy",
        ],
        "tags": ["twinkle twinkle little star","lullaby","bedtime songs","nursery rhymes","kids songs"],
    },
    # ── TEACHING lessons: carry an `edu` list -> the Remotion LEARNING layout actually
    # instructs (letter formation + phonic sounds + blending; counting + addition). Render
    # with:  python make_zuzu.py --lesson phonics_abc --remotion  (crisp, $0, GPU-free). ──
    {
        "id": "phonics_abc",
        "title": "Phonics: A B C",
        "category": "phonics letters",
        "mode": "learn",
        "song_prompt": "cheerful children's phonics song, cute gentle kids voice, playful piano and bells, upbeat, wholesome",
        "lyrics": (
            "[verse]\nA says ah, ah, ah, Apple starts with A!\n"
            "B says buh, buh, buh, Ball starts with B!\n"
            "C says cuh, cuh, cuh, Cat starts with C!\n"
            "[verse]\nSound them out and sing with me,\nlearning letters A B C!"
        ),
        "captions": ["A says ah","Apple!","B says buh","Ball!","C says cuh","Cat!",
                     "Sound them","out!","Sing with","Zuzu!","A B C","Yay!"],
        # edu drives the teaching scenes (formation trace + sound + example word):
        "edu": [
            {"type": "phonics", "letter": "A", "sound": "ah",  "word": "Apple", "emoji": "🍎"},
            {"type": "phonics", "letter": "B", "sound": "buh", "word": "Ball",  "emoji": "⚽"},
            {"type": "phonics", "letter": "C", "sound": "cuh", "word": "Cat",   "emoji": "🐱"},
        ],
        # scenes are only used by the SDXL->LTX fallback route, not the --remotion learning layout:
        "scenes": [
            "pointing at a giant letter A next to a red apple, bright classroom",
            "beside a big letter B and a bouncy ball, cheerful",
            "next to a big letter C and a cute cat, smiling",
            "tracing letters A B C in the air with its trunk, sparkles",
            "clapping in front of glowing letters A B C, confetti",
            "waving happily beside A B C, celebrating",
        ],
        "tags": ["phonics","letter sounds","learn to read","abc phonics","how to write letters","preschool"],
    },
    {
        "id": "count_add",
        "title": "Count & Add 1-5",
        "category": "numbers maths counting",
        "mode": "learn",
        "song_prompt": "happy children's counting and adding song, cute gentle kids voice, bouncy playful melody, wholesome",
        "lyrics": (
            "[verse]\nOne, two, three, count with me,\ntwo plus one makes three, you see!\n"
            "[verse]\nFour and five, we're doing great,\nthree plus two makes five, that's great!\n"
            "Count and add with Zuzu, hooray!"
        ),
        "captions": ["One, two","three!","Count with","Zuzu!","Two plus one","is three!",
                     "Three plus two","is five!","Count and","add!","Numbers","Yay!"],
        "edu": [
            {"type": "counting", "count": 3, "emoji": "🍎", "label": "apples"},
            {"type": "addition", "a": 2, "b": 1, "emoji": "🍎", "label": "apples"},
            {"type": "counting", "count": 5, "emoji": "⭐", "label": "stars"},
            {"type": "addition", "a": 3, "b": 2, "emoji": "⭐", "label": "stars"},
        ],
        "scenes": [
            "counting three red apples, big glowing number 3",
            "adding two apples and one apple to make three, big plus sign",
            "counting five golden stars, big glowing number 5",
            "adding three stars and two stars to make five, sparkles",
            "clapping with numbers 1 2 3 4 5 floating, joyful",
            "celebrating with stars and apples, confetti",
        ],
        "tags": ["counting","learn to count","kids maths","addition for kids","numbers 1 to 5","preschool"],
    },
    {
        "id": "phonics_def",
        "title": "Phonics: D E F",
        "category": "phonics letters",
        "mode": "learn",
        "song_prompt": "cheerful children's phonics song, cute gentle kids voice, playful piano and bells, upbeat, wholesome",
        "lyrics": (
            "[verse]\nD says duh, duh, duh, Dog starts with D!\n"
            "E says eh, eh, eh, Egg starts with E!\n"
            "F says fuh, fuh, fuh, Fish starts with F!\n"
            "[verse]\nSound them out and sing with me,\nlearning letters D E F!"
        ),
        "captions": ["D says duh","Dog!","E says eh","Egg!","F says fuh","Fish!",
                     "Sound them","out!","Sing with","Zuzu!","D E F","Yay!"],
        "edu": [
            {"type": "phonics", "letter": "D", "sound": "duh", "word": "Dog",  "emoji": "🐶"},
            {"type": "phonics", "letter": "E", "sound": "eh",  "word": "Egg",  "emoji": "🥚"},
            {"type": "phonics", "letter": "F", "sound": "fuh", "word": "Fish", "emoji": "🐟"},
        ],
        "scenes": [
            "pointing at a giant letter D next to a happy dog, bright classroom",
            "beside a big letter E and a smiling egg, cheerful",
            "next to a big letter F and a cute fish in a bowl, smiling",
            "tracing letters D E F in the air with its trunk, sparkles",
            "clapping in front of glowing letters D E F, confetti",
            "waving happily beside D E F, celebrating",
        ],
        "tags": ["phonics","letter sounds d e f","learn to read","abc phonics","how to write letters","preschool"],
    },
    {
        "id": "phonics_ghi",
        "title": "Phonics: G H I",
        "category": "phonics letters",
        "mode": "learn",
        "song_prompt": "cheerful children's phonics song, cute gentle kids voice, playful piano and bells, upbeat, wholesome",
        "lyrics": (
            "[verse]\nG says guh, guh, guh, Goat starts with G!\n"
            "H says huh, huh, huh, Hat starts with H!\n"
            "I says ih, ih, ih, Igloo starts with I!\n"
            "[verse]\nSound them out and sing with me,\nlearning letters G H I!"
        ),
        "captions": ["G says guh","Goat!","H says huh","Hat!","I says ih","Igloo!",
                     "Sound them","out!","Sing with","Zuzu!","G H I","Yay!"],
        "edu": [
            {"type": "phonics", "letter": "G", "sound": "guh", "word": "Goat",  "emoji": "🐐"},
            {"type": "phonics", "letter": "H", "sound": "huh", "word": "Hat",   "emoji": "🎩"},
            {"type": "phonics", "letter": "I", "sound": "ih",  "word": "Igloo", "emoji": "🧊"},
        ],
        "scenes": [
            "pointing at a giant letter G next to a friendly goat, bright classroom",
            "beside a big letter H wearing a fancy hat, cheerful",
            "next to a big letter I beside a cute snowy igloo, smiling",
            "tracing letters G H I in the air with its trunk, sparkles",
            "clapping in front of glowing letters G H I, confetti",
            "waving happily beside G H I, celebrating",
        ],
        "tags": ["phonics","letter sounds g h i","learn to read","abc phonics","how to write letters","preschool"],
    },
    {
        "id": "phonics_jkl",
        "title": "Phonics: J K L",
        "category": "phonics letters",
        "mode": "learn",
        "song_prompt": "cheerful children's phonics song, cute gentle kids voice, playful piano and bells, upbeat, wholesome",
        "lyrics": (
            "[verse]\nJ says juh, juh, juh, Juice starts with J!\n"
            "K says kuh, kuh, kuh, Kite starts with K!\n"
            "L says luh, luh, luh, Lion starts with L!\n"
            "[verse]\nSound them out and sing with me,\nlearning letters J K L!"
        ),
        "captions": ["J says juh","Juice!","K says kuh","Kite!","L says luh","Lion!",
                     "Sound them","out!","Sing with","Zuzu!","J K L","Yay!"],
        "edu": [
            {"type": "phonics", "letter": "J", "sound": "juh", "word": "Juice", "emoji": "🧃"},
            {"type": "phonics", "letter": "K", "sound": "kuh", "word": "Kite",  "emoji": "🪁"},
            {"type": "phonics", "letter": "L", "sound": "luh", "word": "Lion",  "emoji": "🦁"},
        ],
        "scenes": [
            "pointing at a giant letter J next to a cup of juice, bright classroom",
            "beside a big letter K and a colorful kite in the sky, cheerful",
            "next to a big letter L and a friendly lion, smiling",
            "tracing letters J K L in the air with its trunk, sparkles",
            "clapping in front of glowing letters J K L, confetti",
            "waving happily beside J K L, celebrating",
        ],
        "tags": ["phonics","letter sounds j k l","learn to read","abc phonics","how to write letters","preschool"],
    },
    {
        "id": "phonics_mno",
        "title": "Phonics: M N O",
        "category": "phonics letters",
        "mode": "learn",
        "song_prompt": "cheerful children's phonics song, cute gentle kids voice, playful piano and bells, upbeat, wholesome",
        "lyrics": (
            "[verse]\nM says muh, muh, muh, Moon starts with M!\n"
            "N says nuh, nuh, nuh, Nut starts with N!\n"
            "O says oh, oh, oh, Octopus starts with O!\n"
            "[verse]\nSound them out and sing with me,\nlearning letters M N O!"
        ),
        "captions": ["M says muh","Moon!","N says nuh","Nut!","O says oh","Octopus!",
                     "Sound them","out!","Sing with","Zuzu!","M N O","Yay!"],
        "edu": [
            {"type": "phonics", "letter": "M", "sound": "muh", "word": "Moon",     "emoji": "🌙"},
            {"type": "phonics", "letter": "N", "sound": "nuh", "word": "Nut",      "emoji": "🥜"},
            {"type": "phonics", "letter": "O", "sound": "oh",  "word": "Octopus",  "emoji": "🐙"},
        ],
        "scenes": [
            "pointing at a giant letter M next to a glowing moon, bright classroom",
            "beside a big letter N and a little nut, cheerful",
            "next to a big letter O and a friendly octopus, smiling",
            "tracing letters M N O in the air with its trunk, sparkles",
            "clapping in front of glowing letters M N O, confetti",
            "waving happily beside M N O, celebrating",
        ],
        "tags": ["phonics","letter sounds m n o","learn to read","abc phonics","how to write letters","preschool"],
    },
    {
        "id": "phonics_pqr",
        "title": "Phonics: P Q R",
        "category": "phonics letters",
        "mode": "learn",
        "song_prompt": "cheerful children's phonics song, cute gentle kids voice, playful piano and bells, upbeat, wholesome",
        "lyrics": (
            "[verse]\nP says puh, puh, puh, Pig starts with P!\n"
            "Q says kwuh, kwuh, kwuh, Queen starts with Q!\n"
            "R says rrr, rrr, rrr, Rabbit starts with R!\n"
            "[verse]\nSound them out and sing with me,\nlearning letters P Q R!"
        ),
        "captions": ["P says puh","Pig!","Q says kwuh","Queen!","R says rrr","Rabbit!",
                     "Sound them","out!","Sing with","Zuzu!","P Q R","Yay!"],
        "edu": [
            {"type": "phonics", "letter": "P", "sound": "puh",  "word": "Pig",    "emoji": "🐷"},
            {"type": "phonics", "letter": "Q", "sound": "kwuh", "word": "Queen",  "emoji": "👑"},
            {"type": "phonics", "letter": "R", "sound": "rrr",  "word": "Rabbit", "emoji": "🐰"},
        ],
        "scenes": [
            "pointing at a giant letter P next to a happy pig, bright classroom",
            "beside a big letter Q and a queen's crown, cheerful",
            "next to a big letter R and a cute rabbit, smiling",
            "tracing letters P Q R in the air with its trunk, sparkles",
            "clapping in front of glowing letters P Q R, confetti",
            "waving happily beside P Q R, celebrating",
        ],
        "tags": ["phonics","letter sounds p q r","learn to read","abc phonics","how to write letters","preschool"],
    },
    {
        "id": "phonics_stu",
        "title": "Phonics: S T U",
        "category": "phonics letters",
        "mode": "learn",
        "song_prompt": "cheerful children's phonics song, cute gentle kids voice, playful piano and bells, upbeat, wholesome",
        "lyrics": (
            "[verse]\nS says sss, sss, sss, Sun starts with S!\n"
            "T says tuh, tuh, tuh, Tiger starts with T!\n"
            "U says uh, uh, uh, Umbrella starts with U!\n"
            "[verse]\nSound them out and sing with me,\nlearning letters S T U!"
        ),
        "captions": ["S says sss","Sun!","T says tuh","Tiger!","U says uh","Umbrella!",
                     "Sound them","out!","Sing with","Zuzu!","S T U","Yay!"],
        "edu": [
            {"type": "phonics", "letter": "S", "sound": "sss", "word": "Sun",      "emoji": "☀️"},
            {"type": "phonics", "letter": "T", "sound": "tuh", "word": "Tiger",    "emoji": "🐯"},
            {"type": "phonics", "letter": "U", "sound": "uh",  "word": "Umbrella", "emoji": "☂️"},
        ],
        "scenes": [
            "pointing at a giant letter S next to a bright sun, bright classroom",
            "beside a big letter T and a friendly tiger, cheerful",
            "next to a big letter U and a colorful umbrella, smiling",
            "tracing letters S T U in the air with its trunk, sparkles",
            "clapping in front of glowing letters S T U, confetti",
            "waving happily beside S T U, celebrating",
        ],
        "tags": ["phonics","letter sounds s t u","learn to read","abc phonics","how to write letters","preschool"],
    },
    {
        "id": "phonics_vwx",
        "title": "Phonics: V W X",
        "category": "phonics letters",
        "mode": "learn",
        "song_prompt": "cheerful children's phonics song, cute gentle kids voice, playful piano and bells, upbeat, wholesome",
        "lyrics": (
            "[verse]\nV says vuh, vuh, vuh, Van starts with V!\n"
            "W says wuh, wuh, wuh, Web starts with W!\n"
            "X says ks, ks, ks, xylophone starts with X!\n"
            "[verse]\nSound them out and sing with me,\nlearning letters V W X!"
        ),
        "captions": ["V says vuh","Van!","W says wuh","Web!","X says ks","Xylophone!",
                     "Sound them","out!","Sing with","Zuzu!","V W X","Yay!"],
        "edu": [
            {"type": "phonics", "letter": "V", "sound": "vuh", "word": "Van", "emoji": "🚐"},
            {"type": "phonics", "letter": "W", "sound": "wuh", "word": "Web", "emoji": "🕸️"},
            {"type": "phonics", "letter": "X", "sound": "ks",  "word": "Xylophone", "emoji": "🎵"},
        ],
        "scenes": [
            "pointing at a giant letter V next to a little van, bright classroom",
            "beside a big letter W and a sparkly spider web, cheerful",
            "next to a big letter X and a clever fox, smiling",
            "tracing letters V W X in the air with its trunk, sparkles",
            "clapping in front of glowing letters V W X, confetti",
            "waving happily beside V W X, celebrating",
        ],
        "tags": ["phonics","letter sounds v w x","learn to read","abc phonics","how to write letters","preschool"],
    },
    {
        "id": "phonics_yz",
        "title": "Phonics: Y Z",
        "category": "phonics letters",
        "mode": "learn",
        "song_prompt": "cheerful children's phonics song, cute gentle kids voice, playful piano and bells, upbeat, wholesome",
        "lyrics": (
            "[verse]\nY says yuh, yuh, yuh, Yo-yo starts with Y!\n"
            "Z says zzz, zzz, zzz, Zebra starts with Z!\n"
            "[verse]\nNow we know the whole ABC,\nY and Z with Zuzu, yippee!"
        ),
        "captions": ["Y says yuh","Yo-yo!","Z says zzz","Zebra!","We know","them all!",
                     "The whole","ABC!","Y and Z","Yippee!","Great job","Zuzu!"],
        "edu": [
            {"type": "phonics", "letter": "Y", "sound": "yuh", "word": "Yo-yo", "emoji": "🪀"},
            {"type": "phonics", "letter": "Z", "sound": "zzz", "word": "Zebra", "emoji": "🦓"},
        ],
        "scenes": [
            "pointing at a giant letter Y next to a spinning yo-yo, bright classroom",
            "beside a big letter Z and a friendly zebra, cheerful",
            "tracing letters Y and Z in the air with its trunk, sparkles",
            "clapping in front of glowing letters Y Z, confetti",
            "in front of a big rainbow alphabet A to Z, celebrating",
            "waving happily, we know the whole ABC, celebrating",
        ],
        "tags": ["phonics","letter sounds y z","learn to read","abc phonics","how to write letters","preschool"],
    },
    {
        "id": "count_to_20",
        "title": "Count to 20",
        "category": "numbers counting maths",
        "mode": "learn",
        "song_prompt": "happy children's counting song, cute gentle kids voice, bouncy playful melody, wholesome",
        "lyrics": (
            "[verse]\nCount to ten with me, one to ten,\nZuzu counts them all again!\n"
            "[verse]\nThen to fifteen, then to twenty too,\ncounting big numbers, me and you!\n"
            "Ten, fifteen, twenty, we can do!"
        ),
        "captions": ["Count to","ten!","One to ten","with Zuzu!","Now to","fifteen!",
                     "Then to","twenty!","Big numbers","Yay!","Ten fifteen","twenty!"],
        "edu": [
            {"type": "counting", "count": 10, "emoji": "⭐", "label": "stars"},
            {"type": "counting", "count": 15, "emoji": "🍎", "label": "apples"},
            {"type": "counting", "count": 20, "emoji": "🎈", "label": "balloons"},
        ],
        "scenes": [
            "counting ten golden stars, big glowing number 10, starry field",
            "counting fifteen red apples, big glowing number 15, cheerful",
            "counting twenty colorful balloons, big glowing number 20, joyful",
            "hopping past floating numbers 10 15 20, sparkles",
            "clapping with stars apples and balloons all around, confetti",
            "celebrating counting all the way to twenty, celebrating",
        ],
        "tags": ["counting to 20","count to twenty","learn to count","big numbers for kids","preschool maths","kids learning"],
    },
    {
        "id": "add_to_10",
        "title": "Add to 10",
        "category": "numbers maths addition",
        "mode": "learn",
        "song_prompt": "happy children's adding song, cute gentle kids voice, bouncy playful melody, wholesome",
        "lyrics": (
            "[verse]\nFour plus three is seven, yay,\nfive plus five is ten today!\n"
            "[verse]\nSix plus two is eight, that's true,\nseven plus two is nine for you!\n"
            "Add it up with Zuzu, hooray!"
        ),
        "captions": ["Four plus three","is seven!","Five plus five","is ten!","Six plus two","is eight!",
                     "Seven plus two","is nine!","Add it up","with Zuzu!","Great maths","Yay!"],
        "edu": [
            {"type": "addition", "a": 4, "b": 3, "emoji": "🍎", "label": "apples"},
            {"type": "addition", "a": 5, "b": 5, "emoji": "⭐", "label": "stars"},
            {"type": "addition", "a": 6, "b": 2, "emoji": "🍌", "label": "bananas"},
            {"type": "addition", "a": 7, "b": 2, "emoji": "🐟", "label": "fish"},
        ],
        "scenes": [
            "adding four apples and three apples to make seven, big plus sign",
            "adding five stars and five stars to make ten, sparkles",
            "adding six bananas and two bananas to make eight, cheerful",
            "adding seven fish and two fish to make nine, joyful",
            "clapping with numbers and a big plus sign floating, confetti",
            "celebrating adding numbers up to ten, celebrating",
        ],
        "tags": ["addition for kids","adding to 10","learn to add","kids maths","math facts","preschool"],
    },
    # ── SOUTH AFRICAN LANGUAGE lessons ────────────────────────────────────────────
    # reviewed=False -> gated OUT of the auto-rotation until a NATIVE SPEAKER verifies the
    # words (spelling + the correct counting concord forms). Run explicitly for review:
    #   python make_zuzu.py --lesson count_zulu --remotion --dry-run
    # `lang` routes narration: zu/af use the authentic edge-tts voice; xh has NO TTS voice
    # yet, so isiXhosa renders the on-screen words but SILENT (needs a cloned Xhosa voice).
    {
        "id": "count_zulu",
        "title": "Count in isiZulu 1-10",
        "category": "numbers counting isizulu",
        "mode": "learn", "lang": "zu", "reviewed": False,
        "song_prompt": "gentle happy children's counting song, warm, wholesome",
        "lyrics": "[verse]\nAsibaleni ndawonye!\nkunye, kubili, kuthathu...\n",
        "captions": ["Kunye","Kubili","Kuthathu","Kune","Kuhlanu","Isithupha",
                     "Isikhombisa","Isishiyagalombili","Isishiyagalolunye","Ishumi","1-10","Yay!"],
        "edu": [
            {"type": "counting", "count": 1,  "emoji": "🍎", "label": "kunye"},
            {"type": "counting", "count": 2,  "emoji": "⭐", "label": "kubili"},
            {"type": "counting", "count": 3,  "emoji": "🎈", "label": "kuthathu"},
            {"type": "counting", "count": 4,  "emoji": "🐟", "label": "kune"},
            {"type": "counting", "count": 5,  "emoji": "🌸", "label": "kuhlanu"},
            {"type": "counting", "count": 6,  "emoji": "🍌", "label": "isithupha"},
            {"type": "counting", "count": 7,  "emoji": "⚽", "label": "isikhombisa"},
            {"type": "counting", "count": 8,  "emoji": "🐝", "label": "isishiyagalombili"},
            {"type": "counting", "count": 9,  "emoji": "🚗", "label": "isishiyagalolunye"},
            {"type": "counting", "count": 10, "emoji": "🎉", "label": "ishumi"},
        ],
        "scenes": ["counting objects with big numbers 1 to 10, joyful"] * 6,
        "tags": ["isizulu","learn to count zulu","kids zulu","south africa kids","counting","preschool"],
    },
    {
        "id": "count_xhosa",
        "title": "Count in isiXhosa 1-10",
        "category": "numbers counting isixhosa",
        "mode": "learn", "lang": "xh", "reviewed": False,   # no TTS voice yet -> visual only
        "song_prompt": "gentle happy children's counting song, warm, wholesome",
        "lyrics": "[verse]\nMasibale kunye!\ninye, zimbini, zintathu...\n",
        "captions": ["Inye","Zimbini","Zintathu","Zine","Zintlanu","Zintandathu",
                     "Isixhenxe","Isibhozo","Ithoba","Ishumi","1-10","Yay!"],
        "edu": [
            {"type": "counting", "count": 1,  "emoji": "🍎", "label": "inye"},
            {"type": "counting", "count": 2,  "emoji": "⭐", "label": "zimbini"},
            {"type": "counting", "count": 3,  "emoji": "🎈", "label": "zintathu"},
            {"type": "counting", "count": 4,  "emoji": "🐟", "label": "zine"},
            {"type": "counting", "count": 5,  "emoji": "🌸", "label": "zintlanu"},
            {"type": "counting", "count": 6,  "emoji": "🍌", "label": "zintandathu"},
            {"type": "counting", "count": 7,  "emoji": "⚽", "label": "isixhenxe"},
            {"type": "counting", "count": 8,  "emoji": "🐝", "label": "isibhozo"},
            {"type": "counting", "count": 9,  "emoji": "🚗", "label": "ithoba"},
            {"type": "counting", "count": 10, "emoji": "🎉", "label": "ishumi"},
        ],
        "scenes": ["counting objects with big numbers 1 to 10, joyful"] * 6,
        "tags": ["isixhosa","learn to count xhosa","kids xhosa","south africa kids","counting","preschool"],
    },
    {
        "id": "count_afrikaans",
        "title": "Count in Afrikaans 1-10",
        "category": "numbers counting afrikaans",
        "mode": "learn", "lang": "af", "reviewed": False,
        "song_prompt": "gentle happy children's counting song, warm, wholesome",
        "lyrics": "[verse]\nKom ons tel saam!\neen, twee, drie...\n",
        "captions": ["Een","Twee","Drie","Vier","Vyf","Ses",
                     "Sewe","Agt","Nege","Tien","1-10","Jippie!"],
        "edu": [
            {"type": "counting", "count": 1,  "emoji": "🍎", "label": "een"},
            {"type": "counting", "count": 2,  "emoji": "⭐", "label": "twee"},
            {"type": "counting", "count": 3,  "emoji": "🎈", "label": "drie"},
            {"type": "counting", "count": 4,  "emoji": "🐟", "label": "vier"},
            {"type": "counting", "count": 5,  "emoji": "🌸", "label": "vyf"},
            {"type": "counting", "count": 6,  "emoji": "🍌", "label": "ses"},
            {"type": "counting", "count": 7,  "emoji": "⚽", "label": "sewe"},
            {"type": "counting", "count": 8,  "emoji": "🐝", "label": "agt"},
            {"type": "counting", "count": 9,  "emoji": "🚗", "label": "nege"},
            {"type": "counting", "count": 10, "emoji": "🎉", "label": "tien"},
        ],
        "scenes": ["counting objects with big numbers 1 to 10, joyful"] * 6,
        "tags": ["afrikaans","learn to count afrikaans","kids afrikaans","south africa kids","counting","preschool"],
    },
]

def build_description(lesson: dict) -> str:
    """Kid-safe SEO description for a lesson."""
    lyric_plain = lesson["lyrics"].replace("[verse]", "").strip()
    return (
        f"{lesson['title']} with Zuzu the baby elephant! Sing, learn and play along "
        f"with Zuzu & Friends.\n\n"
        f"A fun, gentle way for toddlers, babies and preschoolers to learn "
        f"{lesson['category']} while singing along. Safe and made for kids.\n\n"
        f"Lyrics:\n{lyric_plain}\n\n"
        f"Subscribe to Zuzu & Friends for a new learning song every day!"
    )

def get_lesson(lesson_id: str) -> dict | None:
    for l in LESSONS:
        if l["id"] == lesson_id:
            return l
    return None

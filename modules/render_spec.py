"""How this factory delivers a frame. One place, so it is one decision.

Owner 2026-09-05: bring in a professional studio. Before any of that, the
settings that decide whether output looks made or drawn were scattered as
literals across nine files - `fps=30` written out by hand in every builder,
and no antialiasing setting at all because there was no antialiasing.

FPS = 60. Broadcast sports graphics run at 50 or 60, and this pipeline's
content is the case that needs it: a ball crossing a penalty area and eleven
tokens gliding between keyframes. At 30 both strobe slightly - the eye reads a
sequence of positions rather than movement, which is precisely the "diagram,
not football" impression the tactics formats exist to avoid.

The old value was not only low, it was applied LAST: the board rendered its
chapters and then build_role_analysis re-encoded the finished reel at 30,
so any smoothness upstream was discarded at the final write. Both ends read
this constant now, which is the actual reason this file exists rather than a
tidier set of literals.

SUPERSAMPLE = 2. PIL's ImageDraw antialiases nothing, so every circle, line
and polygon is drawn with hard pixels. Frames are drawn at 2x and box-averaged
back down, which is what turns a stair-stepped token edge into a smooth one.
See the note in modules/tactics_board for how it is applied.

Costs, measured on this machine at 1080x1920: a board frame went 37.1ms ->
11.3ms on caching fixes, then to 44.1ms with 2x supersampling on top. So a 60
second reel draws in about 160 seconds instead of 45. That is a real cost, and
it is paid on a scheduler at night rather than by anyone waiting.

Raise SUPERSAMPLE to 3 for a still (a cover, a card) where time does not
matter. Drop it to 1 to render a draft fast; nothing breaks, the edges just
come back.
"""

FPS = 60
SUPERSAMPLE = 2

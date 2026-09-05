"""Antialiasing for a library that has none.

PIL's ImageDraw rasterises every ellipse, line and polygon with hard pixels.
Text is smooth because FreeType draws it; nothing else is. That is why every
token, ball, arrow and corner arc this repo has ever produced carries visible
stair-stepping, and it is the clearest "drawn at home" signal on the output.

The fix is the one every renderer uses: draw larger, then average down. What
makes it awkward HERE is that the drawing code is written in delivery
coordinates and salted with pixel literals - `y = 108`, `width=3`, `radius=14`
- so multiplying the canvas means finding and scaling every one of them by
hand, across hundreds of calls, without missing any.

So the DRAW HANDLE is wrapped instead. ScaledDraw multiplies coordinates on
their way to a larger canvas, which means the layout code above it keeps
speaking 1080x1920 and never learns that the canvas grew.

Text measurement runs the other way: textlength divides back down, because
shrink-to-fit loops compare a measured width against a literal like `W - 44`.
Returning supersampled pixels there would silently mis-fit every title.

Fonts are the caller's job: ask for them at size * scale, or the glyphs will
be the one soft thing on a crisp frame. modules/typeface is where that
happens for this codebase.

    from modules.aa_draw import scaled_draw, canvas, resolve
    im = canvas(1080, 1350, 2)
    d = scaled_draw(im, 2)          # speak 1080x1350 at it
    ...
    im = resolve(im, 1080, 1350, 2) # box-average to delivery size
"""


def scale_pts(xy, s):
    """Scale any PIL coordinate shape: scalar, flat list, or list of points."""
    if isinstance(xy, (int, float)):
        return xy * s
    seq = list(xy)
    if seq and isinstance(seq[0], (list, tuple)):
        return [tuple(c * s for c in p) for p in seq]
    return [c * s for c in seq]


class ScaledDraw:
    """An ImageDraw that speaks base coordinates onto a supersampled canvas.

    Only the methods this codebase actually draws with are wrapped. Anything
    else falls through by __getattr__ UNSCALED, which is deliberate: a silent
    catch-all that guessed at coordinates would put things in the wrong place
    and be very hard to find. If a new call type is added, it should be added
    here on purpose.
    """

    __slots__ = ("_d", "_s")

    def __init__(self, d, s):
        self._d, self._s = d, s

    def _w(self, kw):
        """Line weights and corner radii are pixel counts, so they scale too."""
        s = self._s
        if kw.get("width"):
            kw["width"] = max(1, int(round(kw["width"] * s)))
        if kw.get("radius"):
            kw["radius"] = kw["radius"] * s
        return kw

    def rectangle(self, xy, **kw):
        self._d.rectangle(scale_pts(xy, self._s), **self._w(kw))

    def rounded_rectangle(self, xy, **kw):
        self._d.rounded_rectangle(scale_pts(xy, self._s), **self._w(kw))

    def ellipse(self, xy, **kw):
        self._d.ellipse(scale_pts(xy, self._s), **self._w(kw))

    def arc(self, xy, *a, **kw):
        self._d.arc(scale_pts(xy, self._s), *a, **self._w(kw))

    def pieslice(self, xy, *a, **kw):
        self._d.pieslice(scale_pts(xy, self._s), *a, **self._w(kw))

    def line(self, xy, **kw):
        self._d.line(scale_pts(xy, self._s), **self._w(kw))

    def polygon(self, xy, **kw):
        self._d.polygon(scale_pts(xy, self._s), **kw)

    def text(self, xy, *a, **kw):
        # The font must already be built at the supersampled size.
        self._d.text(tuple(scale_pts(xy, self._s)), *a, **kw)

    def textlength(self, *a, **kw):
        return self._d.textlength(*a, **kw) / self._s

    def textbbox(self, xy, *a, **kw):
        b = self._d.textbbox(tuple(scale_pts(xy, self._s)), *a, **kw)
        return tuple(c / self._s for c in b)

    def __getattr__(self, name):
        return getattr(self._d, name)


def scaled_draw(img, s):
    """An RGBA draw handle on `img` that accepts base coordinates."""
    from PIL import ImageDraw
    return ScaledDraw(ImageDraw.Draw(img, "RGBA"), s)


def canvas(w, h, s, fill=(0, 0, 0), mode="RGB"):
    from PIL import Image
    return Image.new(mode, (int(w * s), int(h * s)), fill)


def resolve(im, w, h, s):
    """Bring a supersampled image down to delivery size.

    Image.reduce box-averages each s x s block, which is exactly what
    resolving a supersample means and is roughly ten times faster than LANCZOS
    for a difference no eye can find (measured at 0.29 in 255 on a 2160x3840
    frame). LANCZOS is kept for the non-integer case, which should not arise.
    """
    from PIL import Image
    if s == 1 or im.size == (w, h):
        return im
    if im.width == w * s and im.height == h * s:
        return im.reduce(s)
    return im.resize((w, h), Image.LANCZOS)

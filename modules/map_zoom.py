"""
News map-zoom module — the Vox/Johnny-Harris "zoom to the region" signature move.

Renders a clean styled world map (dark ocean, muted land) with the TARGET country
filled in the channel accent colour, then animates a smooth cinematic zoom into that
region with a pulsing marker and a label that fades in. Vertical 1080x1920 by default
(reels) or 1920x1080 for long-form.

Offline + cheap: matplotlib renders the map ONCE, then the zoom is a Ken-Burns crop of
that pre-rendered image (PIL) — no per-frame map redraw, no external map/tile service.
Country geometry: public-domain Natural Earth 110m (assets/geo/world_countries.geojson).

Usage (lib):
    from modules.map_zoom import make_map_zoom_clip
    make_map_zoom_clip("Iran", "map.mp4", duration=4.0, accent="#FF3131")
    make_map_zoom_clip((-25.7, 28.2), "pretoria.mp4", label="PRETORIA")   # (lat, lon) point

CLI:
    python -m modules.map_zoom "Ukraine" out.mp4 4
"""
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path

_FEATURES = None

ROOT = Path(__file__).resolve().parent.parent
GEOJSON = ROOT / "assets" / "geo" / "world_countries.geojson"

# ── Style (serious-news palette) ──────────────────────────────────────────────
OCEAN = "#0b1620"     # deep dark ocean
LAND = "#25333f"      # muted land
BORDER = "#3a4b58"    # thin country borders
LABEL_FG = "#ffffff"

# Common name aliases → the Natural Earth NAME field.
_ALIASES = {
    "usa": "United States of America", "us": "United States of America",
    "u.s.": "United States of America", "america": "United States of America",
    "united states": "United States of America", "uk": "United Kingdom",
    "britain": "United Kingdom", "great britain": "United Kingdom",
    "england": "United Kingdom", "russia": "Russia", "russian federation": "Russia",
    "drc": "Dem. Rep. Congo", "dr congo": "Dem. Rep. Congo", "congo": "Dem. Rep. Congo",
    "democratic republic of the congo": "Dem. Rep. Congo",
    "south korea": "South Korea", "north korea": "North Korea",
    "uae": "United Arab Emirates", "car": "Central African Rep.", "drs": "Dem. Rep. Congo",
    "czech republic": "Czechia", "burma": "Myanmar", "ivory coast": "Côte d'Ivoire",
    "swaziland": "eSwatini", "cape verde": "Cabo Verde", "sa": "South Africa",
    "rsa": "South Africa", "palestine": "Palestine", "gaza": "Palestine",
}


def _ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _font(size):
    from PIL import ImageFont
    try:
        from matplotlib import font_manager
        return ImageFont.truetype(font_manager.findfont("DejaVu Sans:bold"), size)
    except Exception:
        try:
            return ImageFont.truetype("arialbd.ttf", size)
        except Exception:
            return ImageFont.load_default()


def _load_features():
    global _FEATURES
    if _FEATURES is None:
        if not GEOJSON.exists():
            raise FileNotFoundError(
                f"Missing {GEOJSON}. Fetch the public-domain Natural Earth 110m countries file:\n"
                "  https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
                "ne_110m_admin_0_countries.geojson  ->  assets/geo/world_countries.geojson"
            )
        _FEATURES = json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]
    return _FEATURES


def _has_word(text_low, phrase):
    return re.search(r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)", text_low) is not None


def detect_country(text):
    """Best-effort: find the country a news headline is about → canonical Natural Earth
    NAME (or None). Lets the news pipeline auto-insert a map-zoom for the story's region.
    Word-boundary matched so 'Chad' won't fire on 'attached'."""
    if not text:
        return None
    low = text.lower()
    for k in sorted(_ALIASES, key=len, reverse=True):
        if _has_word(low, k):
            return _ALIASES[k]
    for f in _load_features():
        nm = f.get("properties", {}).get("NAME", "")
        if nm and _has_word(low, nm):
            return nm
    return None


# Region views: (center_lat, center_lon, span_deg, LABEL, [member country NAMEs to fill]).
# Names match Natural Earth 110m; a name that doesn't match just isn't filled (harmless).
REGIONS = {
    "sahel":          (15,   8,  46, "SAHEL",           ["Mali", "Niger", "Chad", "Burkina Faso", "Mauritania", "Sudan", "Nigeria", "Senegal"]),
    "middle east":    (28,  45,  40, "MIDDLE EAST",     ["Iran", "Iraq", "Saudi Arabia", "Syria", "Yemen", "Israel", "Jordan", "United Arab Emirates", "Egypt", "Turkey", "Lebanon", "Oman", "Qatar", "Kuwait"]),
    "horn of africa": (8,   44,  36, "HORN OF AFRICA",  ["Ethiopia", "Somalia", "Eritrea", "Djibouti", "Kenya", "Sudan", "South Sudan"]),
    "west africa":    (11,  -4,  42, "WEST AFRICA",     ["Nigeria", "Ghana", "Mali", "Senegal", "Niger", "Burkina Faso", "Côte d'Ivoire", "Guinea", "Benin", "Togo", "Sierra Leone", "Liberia"]),
    "east africa":    (0,   37,  46, "EAST AFRICA",     ["Kenya", "Tanzania", "Uganda", "Ethiopia", "Somalia", "Rwanda", "Burundi", "South Sudan"]),
    "north africa":   (28,  15,  36, "NORTH AFRICA",    ["Egypt", "Libya", "Algeria", "Morocco", "Tunisia", "Sudan"]),
    "southern africa":(-25, 25,  40, "SOUTHERN AFRICA", ["South Africa", "Zimbabwe", "Zambia", "Mozambique", "Botswana", "Namibia", "Angola"]),
    "balkans":        (43,  20,  22, "THE BALKANS",     ["Serbia", "Croatia", "Bosnia and Herz.", "Kosovo", "Albania", "North Macedonia", "Montenegro", "Bulgaria", "Greece"]),
    "brics":          (5,   50, 150, "BRICS",           ["Brazil", "Russia", "India", "China", "South Africa"]),
    "europe":         (52,  15,  55, "EUROPE",          []),
    "asia":           (35,  90,  95, "ASIA",            []),
    "africa":         (2,   20, 118, "AFRICA",          []),   # continent view — the fallback
}

_REGION_ALIASES = {
    "sahel": "sahel", "middle east": "middle east", "mideast": "middle east",
    "the gulf": "middle east", "persian gulf": "middle east", "red sea": "horn of africa",
    "horn of africa": "horn of africa", "west africa": "west africa", "east africa": "east africa",
    "north africa": "north africa", "maghreb": "north africa", "southern africa": "southern africa",
    "sub-saharan": "africa", "sub saharan": "africa", "the balkans": "balkans", "balkans": "balkans",
    "brics": "brics", "european union": "europe", "the eu": "europe",
}


def detect_region(text):
    """Find a REGION mentioned in a headline → region key (or None). Word-boundary matched."""
    if not text:
        return None
    low = text.lower()
    for k in sorted(_REGION_ALIASES, key=len, reverse=True):
        if _has_word(low, k):
            return _REGION_ALIASES[k]
    return None


def make_news_map(headline, out_path, duration=3.5, size=(1080, 1920),
                  accent="#FF3131", fps=30):
    """ALWAYS returns a map-zoom for a news headline: a specific country if one is named,
    else the named region, else an Africa continent zoom (the Tech Pulse Africa fallback).
    Returns the path or None."""
    country = detect_country(headline)
    if country:
        return make_map_zoom_clip(country, out_path, duration=duration, size=size,
                                  accent=accent, label=country.upper(), fps=fps)
    key = detect_region(headline) or "africa"
    lat, lon, span, label, members = REGIONS[key]
    return make_map_zoom_clip((lat, lon), out_path, duration=duration, size=size,
                              accent=accent, label=label, fps=fps,
                              span_deg=span, fill_names=members)


def _rings(geom):
    """Exterior rings of a Polygon / MultiPolygon as lists of (lon, lat)."""
    t = geom.get("type"); c = geom.get("coordinates") or []
    out = []
    if t == "Polygon" and c:
        out.append(c[0])
    elif t == "MultiPolygon":
        for poly in c:
            if poly:
                out.append(poly[0])
    return out


def _match(features, target):
    """Return (feature or None, (lon, lat) centroid). target = country name or (lat, lon)."""
    if isinstance(target, (tuple, list)) and len(target) == 2:
        lat, lon = float(target[0]), float(target[1])
        return None, (lon, lat)
    name = str(target).strip()
    key = _ALIASES.get(name.lower(), name).lower()
    best = None
    for f in features:
        p = f.get("properties", {})
        cand = [str(p.get(k, "")).lower() for k in ("NAME", "NAME_LONG", "ADMIN", "SOVEREIGNT")]
        if key in cand:
            best = f; break
        if best is None and any(key in c and c for c in cand):
            best = f
    if not best:
        return None, (20.0, 20.0)  # fallback: gentle world-ish center
    xs, ys = [], []
    for ring in _rings(best["geometry"]):
        for lon, lat in ring:
            xs.append(lon); ys.append(lat)
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    return best, (cx, cy)


def _bbox(feature):
    xs, ys = [], []
    for ring in _rings(feature["geometry"]):
        for lon, lat in ring:
            xs.append(lon); ys.append(lat)
    return min(xs), min(ys), max(xs), max(ys)


def _render_base_map(features, fill_names, accent, map_w=4800, map_h=2400):
    """Render the styled world map ONCE → (numpy RGB array HxWx3). Square-degree pixels
    (map_w == 2*map_h) so geographic and pixel aspect match for clean cropping.
    fill_names: set of country NAMEs to highlight in the accent colour (one for a single
    country, several for a region, or empty for a plain continent/region view)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPoly
    from matplotlib.collections import PatchCollection
    import numpy as np

    fill_set = set(fill_names or [])
    dpi = 100
    fig, ax = plt.subplots(figsize=(map_w / dpi, map_h / dpi), dpi=dpi)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(-180, 180); ax.set_ylim(-90, 90); ax.set_aspect("equal"); ax.axis("off")
    fig.patch.set_facecolor(OCEAN); ax.set_facecolor(OCEAN)

    land, tgt = [], []
    for f in features:
        is_fill = f.get("properties", {}).get("NAME", "") in fill_set
        for ring in _rings(f["geometry"]):
            if len(ring) >= 3:
                (tgt if is_fill else land).append(MplPoly(ring, closed=True))
    ax.add_collection(PatchCollection(land, facecolor=LAND, edgecolor=BORDER, linewidths=0.25))
    if tgt:
        ax.add_collection(PatchCollection(tgt, facecolor=accent, edgecolor="#ffffff", linewidths=0.7))

    fig.canvas.draw()
    w, h = fig.canvas.get_width_height()
    arr = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
    plt.close(fig)
    return arr, w, h


def _ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


def make_map_zoom_clip(target, out_path, duration=4.0, size=(1080, 1920),
                       accent="#FF3131", label=None, fps=30, start_zoom=3.2,
                       span_deg=None, fill_names=None):
    """Render a cinematic map-zoom clip to `target` (country name or (lat, lon)).
    span_deg overrides the zoom extent (degrees tall) for regions/points; fill_names is a
    list of country NAMEs to highlight (e.g. all members of a region). Returns out_path or
    None. label=None auto-uses the country name; label="" hides it."""
    from PIL import Image, ImageDraw
    import numpy as np

    W_out, H_out = int(size[0]), int(size[1])
    aspect = W_out / H_out
    features = _load_features()
    feat, (clon, clat) = _match(features, target)

    fill_set = set(fill_names) if fill_names else ({feat["properties"].get("NAME", "")} if feat else set())
    base, map_w, map_h = _render_base_map(features, fill_set, accent)
    base_img = Image.fromarray(base)

    def lon2x(lon): return (lon + 180.0) / 360.0 * map_w
    def lat2y(lat): return (90.0 - lat) / 180.0 * map_h
    cx, cy = lon2x(clon), lat2y(clat)

    # end crop height (px): explicit span (regions), else fit the country bbox, else a default
    if span_deg:
        end_h = span_deg / 180.0 * map_h
    elif feat is not None:
        mnlon, mnlat, mxlon, mxlat = _bbox(feat)
        bbox_h = (lat2y(mnlat) - lat2y(mxlat))
        bbox_w = (lon2x(mxlon) - lon2x(mnlon))
        end_h = max(bbox_h * 1.7, bbox_w * 1.7 / aspect)
    else:
        end_h = map_h * 0.16          # point target → a ~29° tall view
    end_h = max(map_h * 0.06, min(end_h, map_h * 0.98))
    start_h = min(map_h * 0.98, end_h * start_zoom)

    label_text = (feat["properties"].get("NAME", "") if (label is None and feat) else (label or "")).upper()
    font = _font(int(H_out * 0.045))

    n_frames = max(2, int(round(duration * fps)))
    tmp = Path(tempfile.mkdtemp(prefix="mapzoom_"))
    try:
        for i in range(n_frames):
            t = i / (n_frames - 1)
            e = _ease(t)
            h = start_h + (end_h - start_h) * e
            w = h * aspect
            # keep target centred, clamp crop inside the map
            left = min(max(cx - w / 2.0, 0), max(0, map_w - w))
            top = min(max(cy - h / 2.0, 0), max(0, map_h - h))
            crop = base_img.crop((int(left), int(top), int(left + w), int(top + h)))
            frame = crop.resize((W_out, H_out), Image.LANCZOS).convert("RGB")

            draw = ImageDraw.Draw(frame, "RGBA")
            # target position in output coords
            mx = (cx - left) / w * W_out
            my = (cy - top) / h * H_out
            # pulsing marker
            pulse = 0.5 + 0.5 * math.sin(t * math.pi * 4)
            r = int(H_out * 0.012 + H_out * 0.010 * pulse)
            ac = tuple(int(accent.lstrip("#")[j:j + 2], 16) for j in (0, 2, 4))
            draw.ellipse([mx - r * 2.2, my - r * 2.2, mx + r * 2.2, my + r * 2.2],
                         outline=ac + (int(150 * (1 - pulse)),), width=max(2, int(r * 0.3)))
            draw.ellipse([mx - r, my - r, mx + r, my + r], fill=ac + (255,))
            draw.ellipse([mx - r * 0.4, my - r * 0.4, mx + r * 0.4, my + r * 0.4], fill=(255, 255, 255, 230))

            # label pill, fades in over the second half
            if label_text:
                a = int(255 * _ease((t - 0.4) / 0.35))
                if a > 0:
                    tb = draw.textbbox((0, 0), label_text, font=font)
                    tw, th = tb[2] - tb[0], tb[3] - tb[1]
                    px, py = mx, my + r * 2.6
                    pad = int(H_out * 0.014)
                    x0 = px - tw / 2 - pad; x1 = px + tw / 2 + pad
                    y0 = py; y1 = py + th + pad * 2
                    draw.rounded_rectangle([x0, y0, x1, y1], radius=pad,
                                           fill=(10, 16, 22, int(a * 0.8)))
                    draw.rectangle([x0, y0, x0 + int(H_out * 0.008), y1], fill=ac + (a,))
                    draw.text((px - tw / 2, y0 + pad), label_text, font=font,
                              fill=(255, 255, 255, a))

            frame.save(tmp / f"f{i:05d}.png")

        out_path = str(out_path)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        cmd = [_ffmpeg(), "-y", "-framerate", str(fps), "-i", str(tmp / "f%05d.png"),
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        ok = r.returncode == 0 and Path(out_path).exists() and Path(out_path).stat().st_size > 10000
        if not ok:
            print(f"[map_zoom] ffmpeg failed: {r.stderr[-300:]}")
            return None
        print(f"[map_zoom] {target} -> {out_path} ({n_frames} frames, {duration:.0f}s, {W_out}x{H_out})")
        return out_path
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    import sys
    tgt = sys.argv[1] if len(sys.argv) > 1 else "Iran"
    out = sys.argv[2] if len(sys.argv) > 2 else f"output/map_{tgt.replace(' ', '_')}.mp4"
    dur = float(sys.argv[3]) if len(sys.argv) > 3 else 4.0
    print("RESULT:", make_map_zoom_clip(tgt, out, duration=dur))

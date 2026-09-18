"""
Lead videos from iVideo Studio as dance drivers.

The owner adds trending dance clips on https://ivideostudio.ai/lead-videos.
Before every dance reel run, sync() pulls the ready ones, downloads each new
clip once, prepares it as a driver and registers it next to the hand-curated
library in dance_drivers. A lead that has never been used is picked FIRST,
newest first, so a clip added today is the next reel (owner call 2026-09-14).

Preparing is automatic: black bars removed, one or two dancers allowed - a
two-dancer clip is framed on the more prominent one, and skipped if they are
too close to separate (OpenCV person detector) - centre-cropped to 9:16, trimmed
to MAX_SECONDS (cost follows length), audio kept. A lead whose dancer is too
small or off-centre will be rejected by the motion model; dance_drivers'
failure ledger quarantines it after two failures, so a bad lead costs at most
two renders and never blocks the schedule.
"""
import json
import os
import re
import subprocess
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
REGISTRY = ROOT / "data" / "lead_drivers.json"
RAW_DIR = ROOT / "assets" / "dance_drivers" / "leads_raw"
SITE = os.getenv("IVS_SITE_URL", "https://ivideostudio.ai").rstrip("/")
MAX_SECONDS = 25.0
MIN_SECONDS = 6.0


def _secret() -> str:
    return (os.getenv("IVS_CRON_SECRET") or "").strip()


def _headers() -> dict:
    return {"x-cron-secret": _secret(), "User-Agent": "Genesis-Cron-Worker/1.0"}


def load_registry() -> dict:
    try:
        d = json.loads(REGISTRY.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_registry(d: dict) -> None:
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def _probe(path: Path) -> tuple[int, int, float]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=60).stdout
    d = json.loads(out or "{}")
    s = (d.get("streams") or [{}])[0]
    return int(s.get("width", 0)), int(s.get("height", 0)), float(d.get("format", {}).get("duration", 0) or 0)


def _bars(raw: Path) -> tuple[int, int, int, int] | None:
    """Black letterbox bars, found with ffmpeg cropdetect. Returns w,h,x,y."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-t", "6", "-i", str(raw), "-vf",
                        "cropdetect=limit=24:round=2:reset=0", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=120)
    found = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", r.stderr)
    if not found:
        return None
    w, h, x, y = (int(v) for v in found[-1])
    return (w, h, x, y) if w > 100 and h > 100 else None


def _people(raw: Path, box: tuple[int, int, int, int]) -> list:
    """Person boxes per sampled frame (OpenCV HOG), inside the bar crop."""
    import cv2
    bw, bh, bx, by = box
    cap = cv2.VideoCapture(str(raw))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    frames = []
    for i in range(8):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * (i + 0.5) / 8))
        ok, img = cap.read()
        if not ok:
            continue
        img = img[by:by + bh, bx:bx + bw]
        scale = 640 / max(img.shape[:2])
        small = cv2.resize(img, None, fx=scale, fy=scale)
        rects, weights = hog.detectMultiScale(small, winStride=(8, 8), padding=(8, 8), scale=1.05)
        keep = [(int(x / scale), int(y / scale), int(w / scale), int(h / scale))
                for (x, y, w, h), wt in zip(rects, weights) if float(wt) > 0.5 and h / scale > bh * 0.35]
        frames.append(keep)
    cap.release()
    return frames


def _prepare(raw: Path, out: Path) -> float | None:
    """Strip black bars, frame ONE dancer at 9:16, 720x1280, trimmed.

    The motion model needs a single clear figure with a complete upper body.
    Letterbox bars are removed first; if more than one person dances in the
    clip, the crop zooms onto the most prominent one (largest, then most
    central), found with OpenCV's person detector on sampled frames.
    """
    w, h, dur = _probe(raw)
    if not w or not h or dur < MIN_SECONDS:
        print(f"[Leads] {raw.name}: unusable ({w}x{h}, {dur:.1f}s)")
        return None
    box = _bars(raw) or (w, h, 0, 0)
    bw, bh, bx, by = box
    target = 9 / 16

    # Default: centre 9:16 inside the bar-free area.
    if bw / bh > target:
        cw, ch = int(bh * target), bh
    else:
        cw, ch = bw, int(bw / target)
    cx, cy = bx + (bw - cw) // 2, by + (bh - ch) // 2

    try:
        frames = _people(raw, box)
        counts = sorted(len(f) for f in frames)
        typical = counts[len(counts) // 2] if counts else 0
        if typical > 2:
            print(f"[Leads] {raw.name[:8]}: {typical} dancers in frame - skipped; "
                  f"a lead may have one or two dancers, not a crowd")
            return None
        if typical == 2:
            # The owner asked for one OR two dancers (2026-09-18). The motion
            # model still animates ONE character, and a frame holding two clear
            # figures is rejected by it (tested 2026-09-14), so a two-dancer clip
            # is kept but framed on the more prominent dancer - and only when
            # that crop leaves the other one behind. Pairs standing shoulder to
            # shoulder cannot be split, and those are still skipped.
            best = None
            for f in frames:
                for (x, y, w, h) in f:
                    score = w * h - abs((x + w / 2) - bw / 2) * h * 0.5
                    if best is None or score > best[0]:
                        best = (score, x, y, w, h)
            others = [r for f in frames for r in f
                      if best and not (r[0] == best[1] and r[1] == best[2])]
            if best:
                _, px, py, pw, ph = best
                cx = bx + max(0, min(bw - cw, int(px + pw / 2 - cw / 2)))
                cy = by + max(0, min(bh - ch, int(py + ph / 2 - ch / 2)))
                # does the second dancer still sit inside that crop?
                crowded = False
                for (ox, oy, ow, oh) in others:
                    overlap = max(0, min(cx - bx + cw, ox + ow) - max(cx - bx, ox))
                    if overlap > 0.35 * ow:
                        crowded = True
                        break
                if crowded:
                    print(f"[Leads] {raw.name[:8]}: two dancers too close to separate - skipped")
                    return None
                print(f"[Leads] {raw.name[:8]}: two dancers - framing the more prominent one")
    except Exception as e:
        print(f"[Leads] person framing skipped ({str(e)[:80]}); using centre crop")

    cw, ch = cw // 2 * 2, ch // 2 * 2
    seconds = min(dur, MAX_SECONDS)
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-t", f"{seconds:.2f}", "-i", str(raw),
         "-vf", f"crop={cw}:{ch}:{cx}:{cy},scale=720:1280:flags=lanczos,setsar=1",
         "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", str(out)],
        capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print(f"[Leads] prepare failed for {raw.name}: {r.stderr[-200:]}")
        return None
    return round(_probe(out)[2] or seconds, 1)


def sync(driver_dir: Path) -> dict:
    """Pull ready leads, prepare new ones, return the registry {key: driver}."""
    reg = load_registry()
    if not _secret():
        print("[Leads] IVS_CRON_SECRET not set; using registered leads only")
        return reg
    try:
        res = requests.get(f"{SITE}/api/admin/lead-drivers", headers=_headers(), timeout=30)
        res.raise_for_status()
        leads = res.json().get("leads", [])
    except Exception as e:
        print(f"[Leads] could not reach iVideo Studio ({str(e)[:120]}); using registered leads only")
        return reg

    live_ids = {l["id"] for l in leads}
    changed = False
    for lead in leads:
        key = f"lead_{lead['id'][:8]}"
        if key in reg and (driver_dir / reg[key]["file"]).exists():
            reg[key]["times_used_site"] = lead.get("times_used", 0)
            continue
        raw = RAW_DIR / f"{lead['id']}.mp4"
        try:
            if not raw.exists():
                RAW_DIR.mkdir(parents=True, exist_ok=True)
                with requests.get(lead["video_url"], stream=True, timeout=120) as r:
                    r.raise_for_status()
                    with open(raw, "wb") as f:
                        for chunk in r.iter_content(1 << 16):
                            f.write(chunk)
        except Exception as e:
            print(f"[Leads] download failed for {key}: {str(e)[:120]}")
            continue
        file = f"{key}.mp4"
        seconds = _prepare(raw, driver_dir / file)
        if not seconds:
            continue
        reg[key] = {
            "look": key,                    # every lead is its own look
            "file": file,
            "source": lead.get("source_url") or lead["video_url"],
            "views": int(lead.get("view_count") or 0),
            "seconds": seconds,
            "note": (lead.get("title") or "lead video")[:120],
            "lead_id": lead["id"],
            "added": lead.get("created_at", ""),
            "times_used_site": lead.get("times_used", 0),
        }
        changed = True
        print(f"[Leads] new driver {key}: {seconds}s, {reg[key]['views']:,} views")

    # A lead archived or deleted on the site stops being picked.
    for key in list(reg):
        if reg[key].get("lead_id") not in live_ids:
            reg[key]["retired"] = True
            changed = True
        elif reg[key].pop("retired", None):
            changed = True
    _save_registry(reg)
    return reg


def mark_used(lead_id: str) -> None:
    """Tell iVideo Studio the lead was used in a published reel."""
    if not lead_id or not _secret():
        return
    try:
        requests.post(f"{SITE}/api/admin/lead-drivers", headers=_headers(),
                      json={"id": lead_id}, timeout=30)
    except Exception as e:
        print(f"[Leads] could not mark {lead_id[:8]} used: {str(e)[:120]}")

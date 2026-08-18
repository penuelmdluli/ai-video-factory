"""
Subject-aware frame selection for covers.

Match footage is wide (16:9). Cropping it to a 9:16 cover throws away ~70%
of the width, so a blind centre crop lands on empty grass and looks soft.
This module picks the candidate frame that actually has a subject in it, and
returns the horizontal/vertical focus that keeps that subject inside the
crop.

Score per frame:
  subject   — people found (HOG), faces found (Haar), weighted by how big
              the biggest subject is
  sharpness — variance of Laplacian, so we skip motion-blurred frames
  framing   — penalty if the subject cannot fit inside the target crop
  exposure  — penalty for very dark or blown-out frames

pick_cover_frame() returns (path, focus_x, focus_y, debug) or None.
"""
from pathlib import Path

import cv2
import numpy as np

_HOG = None
_FACE = None


def _hog():
    global _HOG
    if _HOG is None:
        _HOG = cv2.HOGDescriptor()
        _HOG.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    return _HOG


def _face():
    global _FACE
    if _FACE is None:
        _FACE = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    return _FACE


def _subjects(img):
    """Return boxes (x, y, w, h) for people and faces."""
    h, w = img.shape[:2]
    scale = 640 / max(1, w)
    small = cv2.resize(img, (int(w * scale), int(h * scale)))
    boxes = []
    try:
        rects, weights = _hog().detectMultiScale(
            small, winStride=(8, 8), padding=(8, 8), scale=1.06)
        for (x, y, bw, bh), wt in zip(rects, weights):
            if wt > 0.35:
                boxes.append((x / scale, y / scale, bw / scale, bh / scale))
    except Exception:
        pass
    try:
        grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        for (x, y, bw, bh) in _face().detectMultiScale(grey, 1.1, 5,
                                                       minSize=(24, 24)):
            boxes.append((x / scale, y / scale, bw / scale, bh / scale))
    except Exception:
        pass
    return boxes


def _sharpness(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(g, cv2.CV_64F).var())


def score_frame(path, aspect=9 / 16):
    """Score one image for use as a cover at the given aspect ratio."""
    img = cv2.imread(str(path))
    if img is None:
        return None
    h, w = img.shape[:2]
    boxes = _subjects(img)
    sharp = _sharpness(img)

    crop_w = min(w, h * aspect)

    if boxes:
        # biggest subject wins the framing
        bx, by, bw, bh = max(boxes, key=lambda b: b[2] * b[3])
        cx, cy = bx + bw / 2, by + bh / 2
        subject = min(1.0, (bw * bh) / (w * h) * 12)
        fits = 1.0 if bw <= crop_w * 0.92 else 0.45
    else:
        cx, cy = w / 2, h / 2
        subject, fits = 0.0, 0.6

    mean = float(np.mean(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)))
    exposure = 1.0 if 45 <= mean <= 215 else 0.5

    # focus_x/_y are "where along the axis the crop window starts", 0..1
    fx = 0.5 if w <= crop_w else min(
        1.0, max(0.0, (cx - crop_w / 2) / (w - crop_w)))
    crop_h = min(h, crop_w / aspect)
    fy = 0.35 if h <= crop_h else min(
        1.0, max(0.0, (cy - crop_h / 2) / (h - crop_h)))

    total = (subject * 55) + (min(sharp, 400) / 400 * 30) + \
        (fits * 10) + (exposure * 5)
    return {"path": str(path), "score": round(total, 2),
            "subjects": len(boxes), "sharp": round(sharp, 1),
            "focus_x": round(fx, 3), "focus_y": round(fy, 3)}


def pick_cover_frame(candidates, aspect=9 / 16, min_score=0.0):
    """Best frame among candidates. Returns the score dict, or None."""
    scored = []
    for c in candidates:
        p = Path(c)
        if not p.exists():
            continue
        s = score_frame(p, aspect)
        if s:
            scored.append(s)
    if not scored:
        return None
    scored.sort(key=lambda s: s["score"], reverse=True)
    best = scored[0]
    return best if best["score"] >= min_score else best


def frames_for(media_dir):
    """All candidate stills under a framecands folder."""
    d = Path(media_dir)
    if not d.exists():
        return []
    return sorted(d.glob("*.jpg")) + sorted(d.glob("*.png"))

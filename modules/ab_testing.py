"""
A/B Testing Framework — Tests title variants, thumbnail layouts, CTAs, and hooks.

Tracks which variants perform best and learns over time.
Each video gets assigned a variant, and after performance data is collected,
the system identifies winners to inform future content.

Tests:
1. Title style (question vs statement vs number)
2. Thumbnail layout (5 existing layouts)
3. CTA style (question, command, tag-a-friend, save-this, type-keyword)
4. Hook style (question hook, stat hook, story hook, controversy hook)
"""
import json
import random
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from config import OUTPUT_DIR


AB_DATA_FILE = OUTPUT_DIR / "ab_test_data.json"


# ── Test Definitions ─────────────────────────────────────

TITLE_STYLES = {
    "question": "Make the title a compelling question that creates curiosity",
    "statement": "Make the title a bold, shocking statement",
    "number": "Make the title include a specific number or statistic",
    "how_to": "Make the title a 'How to...' or 'Why you should...' format",
}

HOOK_STYLES = {
    "question": "Start with a provocative question that stops the scroll. Example: 'Did you know 90% of traders lose money?'",
    "stat": "Start with a shocking statistic or data point. Example: 'This AI made 47% returns in just 30 days.'",
    "story": "Start with a mini-story or scenario. Example: 'Last week, a 22-year-old made $10K using just one AI tool.'",
    "controversy": "Start with a controversial or contrarian take. Example: 'Everything you've been told about investing is WRONG.'",
    "pattern_interrupt": "Start with something unexpected to break the scroll pattern. Example: 'STOP scrolling. This will change how you think about money.'",
}

CTA_STYLES = {
    "question": "End with an open-ended question to drive comments",
    "command": "End with a direct command: Follow, Save, Share",
    "tag": "End with 'Tag someone who needs this'",
    "type_keyword": "End with 'Type [KEYWORD] if you agree'",
    "save": "End with 'Save this for later — you'll need it'",
}

THUMBNAIL_LAYOUTS = ["classic", "centered", "diagonal", "split", "bottom_bar"]


def _load_ab_data() -> dict:
    """Load A/B testing data."""
    if AB_DATA_FILE.exists():
        try:
            return json.loads(AB_DATA_FILE.read_text())
        except Exception:
            pass
    return {"experiments": [], "variant_scores": {}}


def _save_ab_data(data: dict):
    """Save A/B testing data."""
    AB_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    AB_DATA_FILE.write_text(json.dumps(data, indent=2, default=str))


def select_variants(niche: str) -> dict:
    """
    Select A/B test variants for a new video.

    Uses Thompson sampling (exploration/exploitation) to balance
    trying new variants vs using known winners.

    Returns dict with selected variant for each test dimension.
    """
    data = _load_ab_data()
    scores = data.get("variant_scores", {})

    variants = {}

    # For each test dimension, choose a variant
    for dimension, options in [
        ("title_style", list(TITLE_STYLES.keys())),
        ("hook_style", list(HOOK_STYLES.keys())),
        ("cta_style", list(CTA_STYLES.keys())),
        ("thumbnail_layout", THUMBNAIL_LAYOUTS),
    ]:
        dim_scores = scores.get(f"{niche}_{dimension}", {})

        if not dim_scores or random.random() < 0.3:
            # 30% exploration: random choice
            variants[dimension] = random.choice(options)
        else:
            # 70% exploitation: weighted by performance
            # Use softmax-like selection
            total_score = sum(dim_scores.get(opt, 1) for opt in options)
            if total_score <= 0:
                variants[dimension] = random.choice(options)
            else:
                weights = [max(0.1, dim_scores.get(opt, 1)) for opt in options]
                variants[dimension] = random.choices(options, weights=weights, k=1)[0]

    return variants


def get_title_prompt_modifier(variant: str) -> str:
    """Get the prompt modifier for the selected title style."""
    return TITLE_STYLES.get(variant, "")


def get_hook_prompt_modifier(variant: str) -> str:
    """Get the hook style instruction for the script prompt."""
    return HOOK_STYLES.get(variant, "")


def get_cta_prompt_modifier(variant: str) -> str:
    """Get the CTA style instruction for the script prompt."""
    return CTA_STYLES.get(variant, "")


def record_experiment(
    niche: str,
    variants: dict,
    topic: str,
    title: str,
    video_id: str | None = None,
) -> str:
    """
    Record a new A/B test experiment.

    Returns experiment_id for later performance linking.
    """
    data = _load_ab_data()
    experiment_id = hashlib.md5(
        f"{niche}_{topic}_{datetime.now().isoformat()}".encode()
    ).hexdigest()[:12]

    data["experiments"].append({
        "id": experiment_id,
        "niche": niche,
        "variants": variants,
        "topic": topic,
        "title": title,
        "video_id": video_id,
        "created_at": datetime.now().isoformat(),
        "engagement_score": None,
    })

    _save_ab_data(data)
    return experiment_id


def update_experiment_score(experiment_id: str, engagement_score: float):
    """
    Update an experiment with actual engagement data.

    Also updates variant-level aggregate scores.
    """
    data = _load_ab_data()

    # Find and update the experiment
    for exp in data["experiments"]:
        if exp["id"] == experiment_id:
            exp["engagement_score"] = engagement_score
            niche = exp["niche"]
            variants = exp["variants"]

            # Update per-variant scores
            if "variant_scores" not in data:
                data["variant_scores"] = {}

            for dimension, variant in variants.items():
                key = f"{niche}_{dimension}"
                if key not in data["variant_scores"]:
                    data["variant_scores"][key] = {}
                if variant not in data["variant_scores"][key]:
                    data["variant_scores"][key][variant] = 0

                # Exponential moving average (more weight on recent data)
                old_score = data["variant_scores"][key][variant]
                alpha = 0.3  # Learning rate
                data["variant_scores"][key][variant] = (
                    old_score * (1 - alpha) + engagement_score * alpha
                )
            break

    _save_ab_data(data)


def get_winning_variants(niche: str) -> dict:
    """
    Get the current best-performing variant for each test dimension.

    Returns dict like: {"title_style": "question", "hook_style": "stat", ...}
    """
    data = _load_ab_data()
    scores = data.get("variant_scores", {})
    winners = {}

    for dimension in ["title_style", "hook_style", "cta_style", "thumbnail_layout"]:
        key = f"{niche}_{dimension}"
        dim_scores = scores.get(key, {})
        if dim_scores:
            winners[dimension] = max(dim_scores, key=dim_scores.get)
        else:
            winners[dimension] = None

    return winners


def cleanup_old_experiments(max_age_days: int = 60):
    """Remove experiments older than max_age_days."""
    data = _load_ab_data()
    cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
    data["experiments"] = [
        exp for exp in data["experiments"]
        if exp.get("created_at", "") > cutoff
    ]
    _save_ab_data(data)


def get_experiment_summary(niche: str | None = None) -> dict:
    """Get a summary of A/B test results."""
    data = _load_ab_data()
    experiments = data["experiments"]

    if niche:
        experiments = [e for e in experiments if e.get("niche") == niche]

    scored = [e for e in experiments if e.get("engagement_score") is not None]
    total = len(experiments)

    return {
        "total_experiments": total,
        "scored_experiments": len(scored),
        "winning_variants": get_winning_variants(niche) if niche else {},
        "variant_scores": data.get("variant_scores", {}),
    }

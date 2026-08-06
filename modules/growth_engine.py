"""
Growth Engine — Central orchestrator for all Facebook page growth activities.

Coordinates:
1. Facebook Insights collection (daily page metrics)
2. Community Management (AI-powered comment replies)
3. Cross-Page Promotion (leverage big pages for small ones)
4. Content Optimization (data-driven strategy)
5. Daily Growth Reports

Can run as standalone daemon or integrate into the scheduler.
"""
import os
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from config import ROOT_DIR, OUTPUT_DIR


# ── Constants ────────────────────────────────────────────────
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

ACTIVE_NICHES = [
    "ai_money", "tech_news", "motivation",
    "health_wellness", "blissful_moments", "limitless_you",
]

NICHE_PAGE_NAMES = {
    "ai_money": "Smart Money AI",
    "tech_news": "Tech Pulse Africa",
    "motivation": "Elevate You",
    "health_wellness": "Herbal Organic Life",
    "blissful_moments": "Blissful Moments",
    "limitless_you": "Limitless You",
}

# Growth phase schedule (hours in local time)
INSIGHTS_HOUR = 6           # 6 AM — collect yesterday's data
COMMUNITY_HOURS = [8, 10, 12, 14, 16, 18, 20]  # Every 2 hours
CROSS_PROMO_HOUR = 11       # 11 AM — between content slots
REPORT_HOUR = 22            # 10 PM — daily summary

# Daily goals by page tier
TIER_GOALS = {
    "large": {   # 10K+ followers
        "videos": 5, "engagement_posts": 5,
        "comment_replies": 20, "cross_promos": 1,
    },
    "medium": {  # 1K-10K followers
        "videos": 3, "engagement_posts": 4,
        "comment_replies": 10, "cross_promos": 0,
    },
    "small": {   # <1K followers
        "videos": 2, "engagement_posts": 3,
        "comment_replies": 999,  # Reply to ALL
        "cross_promos": 0,       # Receives promos
    },
}


# ── Page Tier Classification ────────────────────────────────

def _get_tier(niche: str) -> str:
    """Classify page into tier based on follower count."""
    try:
        from modules.facebook_insights import get_growth_rate
        data = get_growth_rate(niche, "daily")
        followers = data.get("current", 0)
        if followers >= 10000:
            return "large"
        elif followers >= 1000:
            return "medium"
        return "small"
    except Exception:
        # Default tiers based on known data
        defaults = {
            "blissful_moments": "large",
            "tech_news": "large",
            "ai_money": "medium",
            "health_wellness": "small",
            "motivation": "small",
            "limitless_you": "small",
        }
        return defaults.get(niche, "small")


def get_daily_goals(niche: str) -> dict:
    """Get daily targets for a niche based on its tier."""
    tier = _get_tier(niche)
    goals = TIER_GOALS[tier].copy()
    goals["niche"] = niche
    goals["tier"] = tier
    goals["page_name"] = NICHE_PAGE_NAMES.get(niche, niche)
    return goals


# ── Growth Cycle ─────────────────────────────────────────────

async def run_growth_cycle(phases: list[str] | None = None) -> dict:
    """
    Run a complete growth cycle.

    Args:
        phases: Specific phases to run. Default: all phases.
                Options: "insights", "community", "cross_promo", "optimize", "report"

    Returns: Summary dict with results from each phase.
    """
    if phases is None:
        phases = ["insights", "community", "cross_promo", "optimize", "report"]

    results = {
        "cycle_started": datetime.now().isoformat(),
        "phases_run": phases,
    }

    print("\n" + "=" * 60)
    print(f"  GROWTH ENGINE — Cycle Started at {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)

    # Phase 1: Collect Insights
    if "insights" in phases:
        print("\n--- Phase 1: Collecting Facebook Insights ---")
        try:
            from modules.facebook_insights import collect_all_pages, collect_post_metrics
            metrics = await collect_all_pages()
            results["insights"] = {
                "pages_collected": len(metrics),
                "total_followers": sum(m["followers"] for m in metrics),
            }

            # Also collect post metrics
            for niche in ACTIVE_NICHES:
                await collect_post_metrics(niche)

        except Exception as e:
            print(f"[Growth] Insights collection failed: {e}")
            results["insights"] = {"error": str(e)}

    # Phase 2: Community Management
    if "community" in phases:
        print("\n--- Phase 2: Community Management ---")
        try:
            from modules.community_manager import run_community_round
            summary = await run_community_round(ACTIVE_NICHES)
            results["community"] = summary
        except Exception as e:
            print(f"[Growth] Community management failed: {e}")
            results["community"] = {"error": str(e)}

    # Phase 3: Cross-Promotion
    if "cross_promo" in phases:
        print("\n--- Phase 3: Cross-Page Promotion ---")
        try:
            from modules.cross_promoter import run_cross_promo_round
            promos = await run_cross_promo_round()
            results["cross_promo"] = {
                "promos_attempted": len(promos),
                "promos_successful": sum(1 for p in promos if p.get("success")),
            }
        except Exception as e:
            print(f"[Growth] Cross-promotion failed: {e}")
            results["cross_promo"] = {"error": str(e)}

    # Phase 4: Content Optimization
    if "optimize" in phases:
        print("\n--- Phase 4: Content Optimization ---")
        try:
            from modules.content_optimizer import analyze_content_performance
            optimizations = {}
            for niche in ACTIVE_NICHES:
                analysis = await analyze_content_performance(niche)
                optimizations[niche] = {
                    "trend": analysis.get("engagement_trend", "unknown"),
                    "recommendations": analysis.get("recommendations", []),
                }
            results["optimization"] = optimizations
        except Exception as e:
            print(f"[Growth] Optimization failed: {e}")
            results["optimization"] = {"error": str(e)}

    # Phase 5: Daily Report
    if "report" in phases:
        print("\n--- Phase 5: Generating Daily Report ---")
        try:
            report = await generate_daily_report()
            results["report"] = report
            _save_daily_report(report)
        except Exception as e:
            print(f"[Growth] Report generation failed: {e}")
            results["report"] = {"error": str(e)}

    results["cycle_completed"] = datetime.now().isoformat()
    print(f"\n[Growth] Cycle completed at {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60 + "\n")

    return results


# ── Daily Report ─────────────────────────────────────────────

async def generate_daily_report() -> dict:
    """
    Compile a comprehensive daily growth report.

    Returns dict with per-niche summaries and overall stats.
    """
    report = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(),
        "pages": {},
        "totals": {
            "total_followers": 0,
            "total_new_followers": 0,
            "total_replies_sent": 0,
            "total_promos": 0,
        },
    }

    # Collect data from all modules
    for niche in ACTIVE_NICHES:
        page_data = {
            "page_name": NICHE_PAGE_NAMES.get(niche, niche),
            "tier": _get_tier(niche),
            "followers": 0,
            "new_followers": 0,
            "engagement_rate": 0.0,
            "replies_sent_today": 0,
            "weekly_growth": 0,
        }

        # Facebook Insights
        try:
            from modules.facebook_insights import get_growth_rate
            daily = get_growth_rate(niche, "daily")
            weekly = get_growth_rate(niche, "weekly")
            page_data["followers"] = daily.get("current", 0)
            page_data["new_followers"] = daily.get("delta", 0)
            page_data["weekly_growth"] = weekly.get("delta", 0)
            page_data["weekly_growth_pct"] = weekly.get("growth_percent", 0)
        except Exception:
            pass

        # Community stats
        try:
            from modules.community_manager import get_reply_stats
            stats = get_reply_stats(1)  # Today only
            niche_stats = stats.get(niche, {})
            page_data["replies_sent_today"] = niche_stats.get("total_replies", 0)
        except Exception:
            pass

        report["pages"][niche] = page_data
        report["totals"]["total_followers"] += page_data["followers"]
        report["totals"]["total_new_followers"] += page_data["new_followers"]
        report["totals"]["total_replies_sent"] += page_data["replies_sent_today"]

    # Cross-promo stats
    try:
        from modules.cross_promoter import get_promo_history
        today_promos = [
            p for p in get_promo_history(1)
            if p["date"] == datetime.now().strftime("%Y-%m-%d")
        ]
        report["totals"]["total_promos"] = len(today_promos)
    except Exception:
        pass

    # Print report
    _print_report(report)

    return report


def _print_report(report: dict):
    """Print formatted daily report."""
    print("\n" + "=" * 70)
    print(f"  DAILY GROWTH REPORT — {report['date']}")
    print("=" * 70)
    print(f"  {'Page':<22} {'Tier':<8} {'Followers':>10} {'New':>8} {'Weekly':>8} {'Replies':>8}")
    print("-" * 70)

    for niche in ACTIVE_NICHES:
        p = report["pages"].get(niche, {})
        name = p.get("page_name", niche)[:21]
        tier = p.get("tier", "?")
        followers = p.get("followers", 0)
        new = p.get("new_followers", 0)
        weekly = p.get("weekly_growth", 0)
        replies = p.get("replies_sent_today", 0)

        print(
            f"  {name:<22} {tier:<8} {followers:>10,} {new:>+8} {weekly:>+8} {replies:>8}"
        )

    t = report["totals"]
    print("-" * 70)
    print(
        f"  {'TOTAL':<22} {'':8} {t['total_followers']:>10,} "
        f"{t['total_new_followers']:>+8} {'':>8} {t['total_replies_sent']:>8}"
    )
    print(f"  Cross-promotions today: {t['total_promos']}")
    print("=" * 70 + "\n")


def _save_daily_report(report: dict):
    """Save daily report to JSON file."""
    report_file = LOGS_DIR / f"daily_growth_report_{report['date']}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"[Growth] Report saved to {report_file}")


# ── Goal Tracking ────────────────────────────────────────────

def check_goal_progress(niche: str) -> dict:
    """Compare actual vs target for the day."""
    goals = get_daily_goals(niche)
    actual = {
        "videos": 0,
        "engagement_posts": 0,
        "comment_replies": 0,
        "cross_promos": 0,
    }

    # Check community replies
    try:
        from modules.community_manager import get_reply_stats
        stats = get_reply_stats(1)
        niche_stats = stats.get(niche, {})
        actual["comment_replies"] = niche_stats.get("total_replies", 0)
    except Exception:
        pass

    # Check cross-promos
    try:
        from modules.cross_promoter import get_promo_history
        today_promos = [
            p for p in get_promo_history(1)
            if p["date"] == datetime.now().strftime("%Y-%m-%d") and p["promoter_niche"] == niche
        ]
        actual["cross_promos"] = len(today_promos)
    except Exception:
        pass

    progress = {}
    for key in goals:
        if key in ("niche", "tier", "page_name"):
            continue
        target = goals[key]
        done = actual.get(key, 0)
        progress[key] = {
            "target": target,
            "actual": done,
            "complete": done >= target,
            "remaining": max(0, target - done),
        }

    return {
        "niche": niche,
        "page_name": goals["page_name"],
        "tier": goals["tier"],
        "progress": progress,
        "overall_complete": all(p["complete"] for p in progress.values()),
    }


# ── Scheduler Integration ───────────────────────────────────

async def run_scheduled_phase(hour: int):
    """
    Run the appropriate growth phase based on current hour.
    Called by the scheduler at each check interval.
    """
    phases = []

    if hour == INSIGHTS_HOUR:
        phases = ["insights"]
    elif hour in COMMUNITY_HOURS:
        phases = ["community"]
    elif hour == CROSS_PROMO_HOUR:
        phases = ["cross_promo"]
    elif hour == REPORT_HOUR:
        phases = ["optimize", "report"]

    if phases:
        print(f"[Growth] Running scheduled phases at hour {hour}: {phases}")
        await run_growth_cycle(phases)


async def growth_daemon():
    """
    Standalone growth daemon — runs growth phases on schedule.

    Alternative to integrating into the main scheduler.
    Use: python -m modules.growth_engine --daemon
    """
    print("[Growth] Growth Engine daemon started")
    print(f"[Growth] Schedule:")
    print(f"  Insights: {INSIGHTS_HOUR}:00")
    print(f"  Community: {', '.join(str(h) + ':00' for h in COMMUNITY_HOURS)}")
    print(f"  Cross-promo: {CROSS_PROMO_HOUR}:00")
    print(f"  Report: {REPORT_HOUR}:00")

    last_run_hour = -1

    while True:
        now = datetime.now()
        current_hour = now.hour

        # Only run once per hour
        if current_hour != last_run_hour:
            all_hours = [INSIGHTS_HOUR] + COMMUNITY_HOURS + [CROSS_PROMO_HOUR, REPORT_HOUR]
            if current_hour in all_hours:
                try:
                    await run_scheduled_phase(current_hour)
                except Exception as e:
                    print(f"[Growth] Phase failed at hour {current_hour}: {e}")
                last_run_hour = current_hour

        # Check every 5 minutes
        await asyncio.sleep(300)


# ── CLI Entry Point ──────────────────────────────────────────

async def main():
    import sys

    if "--daemon" in sys.argv:
        await growth_daemon()
    elif "--report" in sys.argv:
        report = await generate_daily_report()
    elif "--goals" in sys.argv:
        print("\n" + "=" * 60)
        print("  DAILY GOAL PROGRESS")
        print("=" * 60)
        for niche in ACTIVE_NICHES:
            progress = check_goal_progress(niche)
            status = "DONE" if progress["overall_complete"] else "IN PROGRESS"
            print(f"\n  {progress['page_name']} [{progress['tier']}] — {status}")
            for key, p in progress["progress"].items():
                check = "x" if p["complete"] else " "
                print(f"    [{check}] {key}: {p['actual']}/{p['target']}")
        print("=" * 60)
    elif "--insights" in sys.argv:
        await run_growth_cycle(["insights"])
    elif "--community" in sys.argv:
        await run_growth_cycle(["community"])
    elif "--cross-promo" in sys.argv:
        await run_growth_cycle(["cross_promo"])
    else:
        # Run full cycle
        await run_growth_cycle()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

"""
Niche Prioritizer — Auto-pick the hottest niche based on real-time trend heat.

Instead of treating all niches equally, this module:
1. Scores each niche by trend heat across all sources
2. Ranks niches by heat (hottest first)
3. Allocates extra video slots to trending niches
4. Ensures minimum coverage for every niche

Feature-flagged via ENABLE_NICHE_PRIORITIZATION in config.
"""
import asyncio
from datetime import datetime

from config import NICHES, SCHEDULE, ENABLE_NICHE_PRIORITIZATION, MIN_VIDEOS_PER_NICHE_PER_DAY


async def score_niche_heat(niche: str) -> dict:
    """
    Score a single niche's current trend heat.

    Factors:
    - Number of trending results found across all sources
    - Average trend score
    - Number of "rising" / "viral" direction trends (most valuable)
    - Number of active sources that returned data

    Returns: {niche, heat_score (0-100), source_breakdown, top_trend}
    """
    try:
        from modules.trend_detector import get_trending_topics
        data = await get_trending_topics(niche)
    except Exception as e:
        print(f"[NichePrioritizer] Failed to get trends for {niche}: {e}")
        return {
            "niche": niche,
            "heat_score": 0.0,
            "source_breakdown": {},
            "top_trend": "",
            "active_sources": 0,
        }

    trends = data.get("trends", [])
    active_sources = data.get("active_sources", [])

    if not trends:
        return {
            "niche": niche,
            "heat_score": 0.0,
            "source_breakdown": {},
            "top_trend": "",
            "active_sources": 0,
        }

    # Count by source
    source_counts = {}
    for t in trends:
        src = t.get("source", "unknown").split("_")[0].split("/")[0]
        source_counts[src] = source_counts.get(src, 0) + 1

    # Calculate heat factors
    total_results = len(trends)
    avg_score = sum(t.get("score", 0) for t in trends) / total_results if total_results else 0

    # Rising/viral trends are worth more
    hot_directions = {"rising", "viral", "trending"}
    hot_count = sum(1 for t in trends if t.get("trend_direction") in hot_directions)

    # Multi-source bonus: more sources confirming = more reliable
    source_bonus = len(active_sources) * 5  # 0-25 points

    # Heat score (0-100)
    result_score = min(total_results * 3, 30)  # 0-30 from result count
    hot_score = min(hot_count * 5, 25)          # 0-25 from rising/viral
    avg_factor = min(avg_score / 100, 1.0) * 20  # 0-20 from avg score

    heat_score = result_score + hot_score + avg_factor + source_bonus
    heat_score = min(heat_score, 100)

    # Top trend (highest score)
    top = max(trends, key=lambda t: t.get("score", 0))

    return {
        "niche": niche,
        "heat_score": round(heat_score, 1),
        "source_breakdown": source_counts,
        "top_trend": top.get("keyword", "")[:80],
        "active_sources": len(active_sources),
        "total_trends": total_results,
        "hot_trends": hot_count,
    }


async def rank_niches_by_heat(niches: list[str] | None = None) -> list[dict]:
    """
    Score all niches by current trend heat and rank them.

    Runs all niche scores concurrently for speed.

    Returns: sorted list of niche heat dicts (hottest first)
    """
    if niches is None:
        niches = list(NICHES.keys())

    tasks = [score_niche_heat(niche) for niche in niches]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    rankings = []
    for result in results:
        if isinstance(result, Exception):
            continue
        rankings.append(result)

    rankings.sort(key=lambda x: x["heat_score"], reverse=True)
    return rankings


def allocate_niche_slots(
    niche_rankings: list[dict],
    total_slots: int,
    min_per_niche: int | None = None,
) -> dict[str, int]:
    """
    Allocate video slots proportionally by trend heat.

    Ensures each niche gets at least min_per_niche videos,
    then distributes remaining slots by heat score.

    Args:
        niche_rankings: Output from rank_niches_by_heat()
        total_slots: Total video slots available for this time period
        min_per_niche: Minimum videos per niche (default from config)

    Returns: {niche: slot_count}
    """
    if min_per_niche is None:
        min_per_niche = MIN_VIDEOS_PER_NICHE_PER_DAY

    if not niche_rankings:
        return {}

    # Start with minimum allocation
    allocations = {r["niche"]: min_per_niche for r in niche_rankings}
    used = sum(allocations.values())
    remaining = max(total_slots - used, 0)

    if remaining > 0:
        # Distribute remaining slots proportionally by heat score
        total_heat = sum(r["heat_score"] for r in niche_rankings)
        if total_heat > 0:
            for ranking in niche_rankings:
                extra = int(remaining * (ranking["heat_score"] / total_heat))
                allocations[ranking["niche"]] += extra

            # Distribute any leftover (from rounding) to hottest niches
            distributed = sum(allocations.values()) - sum(min_per_niche for _ in niche_rankings)
            leftover = remaining - distributed
            for i, ranking in enumerate(niche_rankings):
                if leftover <= 0:
                    break
                allocations[ranking["niche"]] += 1
                leftover -= 1

    return allocations


def get_niche_order_for_slot(niche_rankings: list[dict]) -> list[str]:
    """
    Get niches ordered by priority (hottest first).

    Use this to build the hottest niches first in each time slot,
    so if time/resources run out, the most important are done.
    """
    return [r["niche"] for r in niche_rankings]


# CLI display
async def show_niche_heat():
    """Display current niche heat rankings."""
    rankings = await rank_niches_by_heat()

    print(f"\n{'='*65}")
    print(f"  Niche Heat Rankings — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*65}")

    for i, r in enumerate(rankings, 1):
        bar = "#" * int(r["heat_score"] / 5)
        sources = r.get("active_sources", 0)
        total = r.get("total_trends", 0)
        hot = r.get("hot_trends", 0)
        print(f"  {i}. {NICHES.get(r['niche'], {}).get('name', r['niche'])[:30]:<32} "
              f"Heat: {r['heat_score']:5.1f} |{bar}")
        print(f"     Sources: {sources} | Trends: {total} ({hot} hot) | Top: {r['top_trend'][:50]}")

    # Show allocation preview
    total_daily_slots = sum(
        sum(v for v in schedule.values())
        for schedule in SCHEDULE.values()
    )
    allocations = allocate_niche_slots(rankings, total_daily_slots)

    print(f"\n  --- Slot Allocation Preview (total: {total_daily_slots} daily slots) ---")
    for niche, slots in sorted(allocations.items(), key=lambda x: x[1], reverse=True):
        name = NICHES.get(niche, {}).get("name", niche)[:30]
        default = sum(SCHEDULE.get(niche, {}).values())
        diff = slots - default
        diff_str = f" (+{diff})" if diff > 0 else f" ({diff})" if diff < 0 else ""
        print(f"    {name:<32} {slots} slots{diff_str}")

    print(f"{'='*65}\n")


if __name__ == "__main__":
    asyncio.run(show_niche_heat())

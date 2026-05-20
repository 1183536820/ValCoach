"""Shared match analysis pipeline — eliminates code duplication between data sources."""

from typing import List, Dict, Any, Optional

from src.metrics import aggregate_metrics, extract_match_extra, calculate_map_hero_breakdown
from src.baseline import load_baseline
from src.diagnosis import diagnose, diagnose_map_hero_weakness, diagnose_strengths
from src.report_generator import generate_report
from src.logger import get_logger

logger = get_logger()


def guess_tier(acs: float) -> str:
    """Estimate tier from average ACS."""
    if acs >= 300:
        return "Radiant"
    elif acs >= 260:
        return "Immortal"
    elif acs >= 230:
        return "Ascendant"
    elif acs >= 200:
        return "Diamond"
    elif acs >= 170:
        return "Platinum"
    elif acs >= 140:
        return "Gold"
    elif acs >= 110:
        return "Silver"
    elif acs >= 80:
        return "Bronze"
    else:
        return "Iron"


class AnalysisReport:
    """Container for all analysis outputs."""

    def __init__(
        self,
        html: str,
        avg_metrics: Dict[str, float],
        all_metrics: List[Dict[str, float]],
        strengths: List[Dict[str, Any]],
        tier: str,
    ):
        self.html = html
        self.avg_metrics = avg_metrics
        self.all_metrics = all_metrics
        self.strengths = strengths
        self.tier = tier


def run_analysis_pipeline(
    all_metrics: List[Dict[str, float]],
    all_match_extras: List[Dict[str, Any]],
    player_name: str,
    tag_line: str,
    is_full: bool = False,
) -> Optional[AnalysisReport]:
    """Shared post-fetch pipeline: aggregate → diagnose → report.

    Args:
        all_metrics: List of per-match metric dicts.
        all_match_extras: List of per-match extra info (map, agent, timestamp, etc).
        player_name: Riot ID game name.
        tag_line: Riot ID tag line.
        is_full: Whether full (paid/admin) features should be included.

    Returns:
        AnalysisReport object, or None if all_metrics is empty.
    """
    if not all_metrics:
        return None

    avg_metrics = aggregate_metrics(all_metrics)
    tier = guess_tier(avg_metrics.get("ACS", 0))
    baseline_data = load_baseline(tier=tier)

    diagnosis_results = diagnose(avg_metrics, baseline_data)
    strength_results = diagnose_strengths(avg_metrics, baseline_data) if is_full else []

    breakdown_data = calculate_map_hero_breakdown(all_match_extras)
    # Remove entries where map_name or agent is empty/Unknown (manual entry may skip these)
    if breakdown_data:
        for mk in list(breakdown_data.keys()):
            if mk in ("Unknown", "unknown", ""):
                del breakdown_data[mk]
            else:
                for ak in list(breakdown_data[mk].keys()):
                    if ak in ("Unknown", "unknown", ""):
                        del breakdown_data[mk][ak]
                if not breakdown_data[mk]:
                    del breakdown_data[mk]
    map_hero_results = diagnose_map_hero_weakness(
        breakdown_data, global_avg_acs=avg_metrics.get("ACS", 200)
    ) if is_full else None

    # Build trend data
    acs_history = []
    kast_history = []
    for m_extra in all_match_extras:
        met = m_extra.get("metrics", {})
        ts = m_extra.get("game_start_timestamp", 0)
        acs_history.append({"value": met.get("ACS", 0), "date": str(ts)})
        kast_history.append({"value": met.get("KAST", 0), "date": str(ts)})

    player_display_id = f"{player_name}#{tag_line}"
    html_report = generate_report(
        player_id=player_display_id,
        player_metrics=avg_metrics,
        diagnosis_results=diagnosis_results,
        baseline_metrics=baseline_data,
        acs_trend=acs_history if is_full else None,
        kast_trend=kast_history if is_full else None,
        map_hero_results=map_hero_results,
        strength_results=strength_results,
    )

    return AnalysisReport(
        html=html_report,
        avg_metrics=avg_metrics,
        all_metrics=all_metrics,
        strengths=strength_results,
        tier=tier,
    )

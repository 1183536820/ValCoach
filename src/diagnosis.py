from typing import List, Dict, Any


ADVICE_TEMPLATES = {
    "KDA": "你的存活能力和击杀效率低于高分玩家基准，建议关注团战站位和技能保命时机。",
    "ACS": "你的综合战斗贡献偏低，可能意味着在对局中制造伤害和影响战局的能力有待提升。",
    "KAST": "你的团队参与率不足，可能过多时间游离在团队之外，建议更积极地参与助攻或协防。",
    "headshot_percent": "瞄准精度有提升空间，建议每天在靶场进行15分钟的中级/高级机器人练习。",
    "first_blood_rate": "开局影响力较弱，可以尝试在安全位置预瞄，争取开局为团队创造人数优势。",
    "econ_rating": "资源利用效率不高，建议减少不必要的起枪，根据团队经济进行统一规划。",
}

METRIC_LABELS = {
    "KDA": "KDA",
    "ACS": "ACS",
    "KAST": "KAST (%)",
    "headshot_percent": "爆头率 (%)",
    "first_blood_rate": "首杀率 (%)",
    "econ_rating": "经济评分",
}


def diagnose(
    player_metrics: Dict[str, float],
    baseline_metrics: Dict[str, Any]
) -> List[Dict[str, Any]]:
    results = []
    gaps = []

    for metric, baseline_value in baseline_metrics.items():
        if metric not in player_metrics:
            continue

        player_value = player_metrics[metric]
        if baseline_value == 0:
            gap = 0.0
        else:
            gap = round((player_value - float(baseline_value)) / float(baseline_value) * 100, 2)

        gaps.append({"metric": metric, "gap": gap, "value": player_value, "baseline": float(baseline_value)})

    # Sort by gap ascending (worst first) and take bottom 3
    gaps.sort(key=lambda x: x["gap"])
    worst_gaps = [g for g in gaps if g["gap"] < 0][:3]

    for gap_info in worst_gaps:
        metric = gap_info["metric"]
        results.append({
            "metric": metric,
            "label": METRIC_LABELS.get(metric, metric),
            "player_value": gap_info["value"],
            "baseline_value": gap_info["baseline"],
            "gap": gap_info["gap"],
            "advice": ADVICE_TEMPLATES.get(metric, "该指标低于基准，建议针对性训练提升。"),
        })

    return results

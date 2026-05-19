import json
import os
from typing import Dict, Any, Optional


def load_baseline(tier: str = "Diamond", baseline_path: str = None) -> Dict[str, Any]:
    if baseline_path is None:
        baseline_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "baseline_stats.json"
        )

    with open(baseline_path, "r") as f:
        all_data = json.load(f)

    if tier in all_data and isinstance(all_data[tier], dict):
        return all_data[tier]
    if "Diamond" in all_data:
        return all_data["Diamond"]

    if isinstance(all_data, dict):
        first_key = list(all_data.keys())[0]
        return all_data[first_key]

    return all_data


def save_baseline(baseline_data: Dict[str, Any], baseline_path: str = None) -> None:
    if baseline_path is None:
        baseline_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "baseline_stats.json"
        )

    with open(baseline_path, "w") as f:
        json.dump(baseline_data, f, indent=2, ensure_ascii=False)

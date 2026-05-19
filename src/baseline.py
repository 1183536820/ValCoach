import json
import os
from typing import Dict, Any


def load_baseline(baseline_path: str = None) -> Dict[str, Any]:
    if baseline_path is None:
        baseline_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "baseline_stats.json"
        )

    with open(baseline_path, "r") as f:
        baseline_data = json.load(f)

    return baseline_data

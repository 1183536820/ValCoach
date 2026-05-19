import json
import os
import sys
import time
import random
import requests
from typing import Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from src import api_client


def fetch_challenger_puuids(region: str = "na") -> list:
    try:
        url = f"https://{region}.api.riotgames.com/val/ranked/v1/leaderboards/by-act/competitive"
        headers = {"X-Riot-Token": api_client.RIOT_API_KEY}
        params = {"size": 100}
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return [entry["puuid"] for entry in data.get("players", [])]
    except Exception as e:
        print(f"Could not fetch leaderboard: {e}")
    return []


def calculate_baseline(puuids: list, sample_size: int = 50) -> Dict[str, float]:
    sampled = random.sample(puuids, min(sample_size, len(puuids)))
    all_metrics = []

    for puuid in sampled:
        try:
            match_ids = api_client.get_match_history(puuid, count=5)
            for match_id in match_ids:
                from src.metrics import calculate_metrics
                match_data = api_client.get_match_details(match_id)
                metrics = calculate_metrics(match_data, puuid)
                all_metrics.append(metrics)
        except Exception:
            continue

    if not all_metrics:
        return {}

    baseline = {}
    for key in all_metrics[0]:
        values = [m[key] for m in all_metrics if key in m]
        if values:
            values.sort()
            mid = len(values) // 2
            median = values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2
            baseline[key] = round(median, 2)

    return baseline


def update_baseline(baseline_path: str = None):
    if baseline_path is None:
        baseline_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "baseline_stats.json"
        )

    print("Fetching Challenger leaderboard...")
    puuids = fetch_challenger_puuids()
    if not puuids:
        print("Using fallback default baseline.")
        return

    print(f"Sampling {min(50, len(puuids))} players...")
    baseline = calculate_baseline(puuids)

    if not baseline:
        print("No data collected, keeping existing baseline.")
        return

    with open(baseline_path, "w") as f:
        json.dump(baseline, f, indent=2)

    print(f"Baseline updated: {baseline}")


if __name__ == "__main__":
    update_baseline()

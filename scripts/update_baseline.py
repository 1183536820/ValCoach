import json
import os
import sys
import time
import random
import requests
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from src import api_client
from src.metrics import calculate_metrics

TIERS = ["Iron", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Ascendant", "Immortal", "Radiant"]


def fetch_tier_puuids(tier: str, region: str = "na") -> list:
    try:
        if tier == "Radiant":
            url = f"https://{region}.api.riotgames.com/val/ranked/v1/leaderboards/by-act/competitive"
            headers = {"X-Riot-Token": api_client.RIOT_API_KEY}
            params = {"size": 100}
            response = requests.get(url, headers=headers, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                return [entry["puuid"] for entry in data.get("players", [])]
    except Exception:
        pass
    return []


def calculate_tier_baseline(tier: str, sample_size: int = 30) -> Dict[str, float]:
    puuids = fetch_tier_puuids(tier)
    if not puuids:
        return {}

    sampled = random.sample(puuids, min(sample_size, len(puuids)))
    all_metrics = []

    for puuid in sampled:
        try:
            match_ids = api_client.get_match_history(puuid, count=5)
            for match_id in match_ids:
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

    api_key = os.getenv("RIOT_API_KEY", "")
    if api_key and api_key != "RGAPI-你的密钥":
        api_client.RIOT_API_KEY = api_key

    if not api_client.RIOT_API_KEY:
        print("No valid API key. Keeping existing baseline.")
        return

    all_baselines = {}
    for tier in TIERS:
        print(f"Processing {tier}...")
        baseline = calculate_tier_baseline(tier)
        if baseline:
            all_baselines[tier] = baseline
            print(f"  {tier}: {baseline}")
        else:
            print(f"  {tier}: no data collected")

    if all_baselines:
        with open(baseline_path, "w") as f:
            json.dump(all_baselines, f, indent=2, ensure_ascii=False)
        print(f"Baseline updated with {len(all_baselines)} tiers.")
    else:
        print("No data collected for any tier.")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    update_baseline()

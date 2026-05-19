from typing import Dict, Any, Optional


def _get_player_data(match_data: Dict[str, Any], puuid: str) -> Optional[Dict[str, Any]]:
    players = match_data.get("players", [])
    for player in players:
        if player.get("puuid") == puuid:
            return player
    return None


def extract_kda(player_data: Dict[str, Any]) -> float:
    # Calculates KDA ratio: kills / max(deaths + assists, 1)
    stats = player_data.get("stats", {})
    kills = stats.get("kills", 0)
    deaths = stats.get("deaths", 0)
    assists = stats.get("assists", 0)
    denominator = deaths + assists
    if denominator == 0:
        return round(float(kills), 2)
    return round(kills / denominator, 2)


def extract_acs(player_data: Dict[str, Any]) -> float:
    # ACS (Average Combat Score) is provided by Riot as "score" in stats
    stats = player_data.get("stats", {})
    return float(stats.get("score", 0))


def extract_kast(match_data: Dict[str, Any], player_data: Dict[str, Any], puuid: str) -> float:
    # KAST = rounds where player got Kill / Assist / Survived / Traded
    # We approximate this using round results
    match_info = match_data.get("matchInfo", {})
    total_rounds = match_info.get("provisioningFlow", "unrated")
    if "roundResults" in match_data:
        rounds = match_data["roundResults"]
    else:
        return 0.0

    rounds_participated = 0
    total_rounds_count = len(rounds)
    if total_rounds_count == 0:
        return 0.0

    for round_data in rounds:
        player_stats_in_round = None
        for player_stat in round_data.get("playerStats", []):
            if player_stat.get("puuid") == puuid:
                player_stats_in_round = player_stat
                break

        if player_stats_in_round is None:
            continue

        # Check if player got any kills or assists in this round
        kills = player_stats_in_round.get("kills", [])
        damage = player_stats_in_round.get("damage", [])

        if len(kills) > 0 or len(damage) > 0:
            rounds_participated += 1

    return round(rounds_participated / total_rounds_count * 100, 2)


def extract_headshot_percent(player_data: Dict[str, Any]) -> float:
    # Headshot percentage = headshots / (headshots + bodyshots + legshots)
    stats = player_data.get("stats", {})
    headshots = stats.get("headshots", 0)
    bodyshots = stats.get("bodyshots", 0)
    legshots = stats.get("legshots", 0)
    total_shots = headshots + bodyshots + legshots
    if total_shots == 0:
        return 0.0
    return round(headshots / total_shots * 100, 2)


def extract_first_blood_rate(player_data: Dict[str, Any], total_rounds: int = 24) -> float:
    # First blood rate: number of first kills / total rounds
    stats = player_data.get("stats", {})
    # Riot API may provide first bloods directly
    first_bloods = player_data.get("firstBloods", 0) or stats.get("firstBloods", 0)
    if total_rounds == 0:
        return 0.0
    return round(first_bloods / total_rounds * 100, 2)


def extract_econ_rating(player_data: Dict[str, Any]) -> float:
    # Economic rating: damage dealt / credits spent
    stats = player_data.get("stats", {})
    damage = stats.get("damage", {}).get("dealt", 0) if isinstance(stats.get("damage"), dict) else stats.get("damage", {}).get("total", 0)

    # Try to get economy data from rounds
    total_spent = 0
    economy = player_data.get("economy", {})
    if economy:
        total_spent = economy.get("spent", 0)

    if total_spent == 0:
        return 0.0

    return round(damage / total_spent, 2)


def calculate_metrics(match_data: Dict[str, Any], puuid: str) -> Dict[str, float]:
    player_data = _get_player_data(match_data, puuid)
    if player_data is None:
        raise ValueError(f"Player with PUUID {puuid} not found in match data.")

    match_info = match_data.get("matchInfo", {})
    total_rounds = len(match_data.get("roundResults", []))
    if total_rounds == 0:
        total_rounds = 24

    metrics = {
        "KDA": extract_kda(player_data),
        "ACS": extract_acs(player_data),
        "KAST": extract_kast(match_data, player_data, puuid),
        "headshot_percent": extract_headshot_percent(player_data),
        "first_blood_rate": extract_first_blood_rate(player_data, total_rounds),
        "econ_rating": extract_econ_rating(player_data),
    }

    return metrics


def aggregate_metrics(all_metrics: list) -> Dict[str, float]:
    if not all_metrics:
        return {}

    aggregated = {}
    keys = all_metrics[0].keys()
    for key in keys:
        values = [m[key] for m in all_metrics if key in m]
        if values:
            aggregated[key] = round(sum(values) / len(values), 2)
        else:
            aggregated[key] = 0.0
    return aggregated

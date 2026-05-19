from typing import Dict, Any, Optional, List


def _get_player_data(match_data: Dict[str, Any], puuid: str) -> Optional[Dict[str, Any]]:
    players = match_data.get("players", [])
    for player in players:
        if player.get("puuid") == puuid:
            return player
    return None


def _get_match_info(match_data: Dict[str, Any]) -> Dict[str, Any]:
    return match_data.get("matchInfo", {})


def extract_kda(player_data: Dict[str, Any]) -> float:
    stats = player_data.get("stats", {})
    kills = stats.get("kills", 0)
    deaths = stats.get("deaths", 0)
    assists = stats.get("assists", 0)
    denominator = deaths + assists
    if denominator == 0:
        return round(float(kills), 2)
    return round(kills / denominator, 2)


def extract_acs(player_data: Dict[str, Any]) -> float:
    stats = player_data.get("stats", {})
    return float(stats.get("score", 0))


def extract_kast(match_data: Dict[str, Any], player_data: Dict[str, Any], puuid: str) -> float:
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

        kills = player_stats_in_round.get("kills", [])
        damage = player_stats_in_round.get("damage", [])

        if len(kills) > 0 or len(damage) > 0:
            rounds_participated += 1

    return round(rounds_participated / total_rounds_count * 100, 2)


def extract_headshot_percent(player_data: Dict[str, Any]) -> float:
    stats = player_data.get("stats", {})
    headshots = stats.get("headshots", 0)
    bodyshots = stats.get("bodyshots", 0)
    legshots = stats.get("legshots", 0)
    total_shots = headshots + bodyshots + legshots
    if total_shots == 0:
        return 0.0
    return round(headshots / total_shots * 100, 2)


def extract_first_blood_rate(player_data: Dict[str, Any], total_rounds: int = 24) -> float:
    stats = player_data.get("stats", {})
    first_bloods = player_data.get("firstBloods", 0) or stats.get("firstBloods", 0)
    if total_rounds == 0:
        return 0.0
    return round(first_bloods / total_rounds * 100, 2)


def extract_econ_rating(player_data: Dict[str, Any]) -> float:
    stats = player_data.get("stats", {})
    damage = stats.get("damage", {}).get("dealt", 0) if isinstance(stats.get("damage"), dict) else 0
    if damage == 0:
        damage = stats.get("damage", {}).get("total", 0) if isinstance(stats.get("damage"), dict) else 0

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


def extract_match_extra(match_data: Dict[str, Any], puuid: str) -> Dict[str, Any]:
    player_data = _get_player_data(match_data, puuid)
    match_info = _get_match_info(match_data)
    if player_data is None:
        return {}

    result = {}
    result["agent_played"] = player_data.get("characterId", "Unknown")
    result["map_name"] = match_info.get("mapId", "Unknown").replace("/", "").split(":")[-1] if match_info.get("mapId") else "Unknown"

    team_id = player_data.get("team", "")
    teams_data = match_data.get("teams", [])
    won = False
    for team in teams_data:
        if team.get("teamId") == team_id:
            won = team.get("won", False)
            break
    result["won"] = won

    match_info = match_data.get("matchInfo", {})
    result["game_start_timestamp"] = match_info.get("gameStartMillis", 0)

    return result


def calculate_map_hero_breakdown(matches: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    breakdown = {}
    for match_data in matches:
        map_name = match_data.get("map_name", "Unknown")
        agent = match_data.get("agent_played", "Unknown")
        if map_name not in breakdown:
            breakdown[map_name] = {}
        if agent not in breakdown[map_name]:
            breakdown[map_name][agent] = {"matches": [], "total_acs": 0, "total_kda": 0, "count": 0}

        metrics = match_data.get("metrics", {})
        breakdown[map_name][agent]["matches"].append(match_data)
        breakdown[map_name][agent]["total_acs"] += metrics.get("ACS", 0)
        breakdown[map_name][agent]["total_kda"] += metrics.get("KDA", 0)
        breakdown[map_name][agent]["count"] += 1

    result = {}
    for map_name, agents in breakdown.items():
        result[map_name] = {}
        for agent, data in agents.items():
            c = data["count"]
            result[map_name][agent] = {
                "avg_acs": round(data["total_acs"] / c, 2) if c else 0,
                "avg_kda": round(data["total_kda"] / c, 2) if c else 0,
                "match_count": c,
            }

    return result


def aggregate_metrics(all_metrics: List[Dict[str, float]]) -> Dict[str, float]:
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

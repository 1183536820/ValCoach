import time
import requests
from typing import List, Dict, Any, Optional
from urllib.parse import quote


RIOT_API_KEY: Optional[str] = None

ACCOUNT_API_BASE = "https://americas.api.riotgames.com/riot/account/v1"


def _make_request(url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None) -> Any:
    time.sleep(0.5)
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise PermissionError("Invalid Riot API key. Please check your .env file.")
        elif response.status_code == 404:
            raise ValueError("Player not found. Please check the game name and tagline.")
        elif response.status_code == 429:
            raise RuntimeError("Rate limit exceeded. Please wait and try again.")
        else:
            response.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError("Request timed out. Riot servers may be slow.")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Failed to connect to Riot servers. Check your internet connection.")
    except (ValueError, PermissionError, RuntimeError):
        raise
    except Exception as e:
        raise RuntimeError(f"Unexpected API error: {str(e)}")


def get_puuid(game_name: str, tag_line: str) -> str:
    encoded_name = quote(game_name, safe="")
    encoded_tag = quote(tag_line, safe="")
    url = f"{ACCOUNT_API_BASE}/accounts/by-riot-id/{encoded_name}/{encoded_tag}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    data = _make_request(url, headers)
    return data["puuid"]


def get_match_history(puuid: str, count: int = 20) -> List[str]:
    headers = {"X-Riot-Token": RIOT_API_KEY}
    params = {"queue": "competitive", "size": count}

    for region_prefix in ["na", "eu", "ap", "kr"]:
        try:
            url = f"https://{region_prefix}.api.riotgames.com/val/match/v1/matchlists/by-puuid/{puuid}"
            data = _make_request(url, headers, params)
            if data and "history" in data:
                matches = [match["matchId"] for match in data["history"] if "matchId" in match]
                if matches:
                    return matches[:count]
        except Exception:
            continue

    raise RuntimeError("Could not fetch match history from any region.")


def get_match_details(match_id: str) -> Dict[str, Any]:
    headers = {"X-Riot-Token": RIOT_API_KEY}
    for region_prefix in ["na", "eu", "ap", "kr"]:
        try:
            url = f"https://{region_prefix}.api.riotgames.com/val/match/v1/matches/{match_id}"
            return _make_request(url, headers)
        except Exception:
            continue
    raise RuntimeError(f"Could not fetch match details for {match_id}.")

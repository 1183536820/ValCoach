import os
import time
import base64
import logging
import subprocess
from typing import Optional, List, Dict, Any, Tuple

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("valcoach")

CLIENT_PLATFORM = "ew0KCSAJInBsYXRmb3JtVHlwZSI6ICJQQyINCn0="  # base64 {"platformType": "PC"}


class LocalClientError(Exception):
    pass


def is_valorant_running() -> bool:
    """Check if VALORANT.exe process is currently running."""
    try:
        import psutil
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] and "VALORANT" in proc.info["name"].upper():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    except ImportError:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq VALORANT.exe", "/NH"],
                capture_output=True, text=True, timeout=5
            )
            return "VALORANT.exe" in result.stdout
        except Exception:
            return False


def find_lockfile() -> Optional[str]:
    """Search for Riot Client lockfile in known locations.

    Covers standard Riot Games install (international) and Tencent
    (Chinese) install paths for 无畏契约.
    """
    localappdata = os.environ.get("LOCALAPPDATA", "")
    programdata = os.environ.get("PROGRAMDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")

    # All known lockfile locations across different installers
    candidates = [
        # Standard Riot Client path (intl + CN via Riot launcher)
        os.path.join(localappdata, "Riot Games", "Riot Client", "Config", "lockfile"),
        # Tencent launcher — 腾讯游戏
        os.path.join(localappdata, "腾讯游戏", "Riot Client", "Config", "lockfile"),
        # Valorant-specific path under LOCALAPPDATA
        os.path.join(localappdata, "VALORANT", "Riot Client", "Config", "lockfile"),
        # Under programdata
        os.path.join(programdata, "Riot Games", "Riot Client", "Config", "lockfile"),
        # Under userprofile as alternative
        os.path.join(userprofile, "AppData", "Local", "Riot Games", "Riot Client", "Config", "lockfile"),
    ]

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for p in candidates:
        if p and p not in seen:
            seen.add(p)
            unique.append(p)

    for path in unique:
        if os.path.isfile(path):
            try:
                with open(path, "r") as f:
                    f.read().strip()
                logger.info(f"Found lockfile at {path}")
                return path
            except Exception:
                continue

    # Fallback: recursive glob under LOCALAPPDATA
    import glob
    pattern = os.path.join(localappdata, "**", "lockfile")
    for match in sorted(glob.glob(pattern, recursive=True)):
        try:
            with open(match, "r") as f:
                content = f.read().strip()
            if ":" in content and content.count(":") >= 4:
                logger.info(f"Found lockfile via glob at {match}")
                return match
        except Exception:
            continue

    logger.warning(f"Lockfile not found in any candidate path under {localappdata}")
    return None


def read_lockfile(path: str) -> Dict[str, str]:
    """Parse lockfile: name:PID:port:password:protocol"""
    try:
        with open(path, "r") as f:
            parts = f.read().strip().split(":")
        if len(parts) < 5:
            raise LocalClientError(f"Invalid lockfile format at {path}")
        return {
            "name": parts[0],
            "pid": parts[1],
            "port": parts[2],
            "password": parts[3],
            "protocol": parts[4],
        }
    except FileNotFoundError:
        raise LocalClientError("Lockfile not found. Is the game running?")
    except PermissionError:
        raise LocalClientError("Permission denied reading lockfile.")
    except Exception as e:
        raise LocalClientError(f"Failed to read lockfile: {str(e)}")


def get_local_session(lockfile: Dict[str, str]) -> Tuple[str, Dict[str, str]]:
    """Build base URL and basic auth headers for the local API."""
    port = lockfile["port"]
    password = lockfile["password"]
    base_url = f"{lockfile['protocol']}://127.0.0.1:{port}"
    auth_raw = f"riot:{password}"
    auth_b64 = base64.b64encode(auth_raw.encode()).decode()
    headers = {"Authorization": f"Basic {auth_b64}"}
    return base_url, headers


def _local_request(method: str, base_url: str, headers: Dict[str, str],
                   endpoint: str, **kwargs) -> Any:
    """Make a request to the local API with error handling."""
    url = f"{base_url}{endpoint}"
    kwargs.setdefault("timeout", 10)
    kwargs.setdefault("verify", False)
    try:
        resp = requests.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 401:
            raise LocalClientError("Local API authentication failed (invalid lockfile).")
        elif resp.status_code == 404:
            raise LocalClientError(f"Local API endpoint not found: {endpoint}")
        else:
            resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise LocalClientError(
            "Cannot connect to local API. Make sure Valorant and Riot Client are running."
        )
    except requests.exceptions.Timeout:
        raise LocalClientError("Local API request timed out.")
    except (LocalClientError, ValueError):
        raise
    except Exception as e:
        raise LocalClientError(f"Local API error: {str(e)}")


def get_local_status() -> Dict[str, Any]:
    """Check if the game client is accessible. Returns status dict."""
    lockfile_path = find_lockfile()
    if not lockfile_path:
        # Check if Chinese Tencent/WeGame version is running
        if is_valorant_running():
            logger.info("VALORANT.exe is running but no Riot Client lockfile found — Chinese WeGame version detected.")
            return {
                "available": False,
                "reason": "cn_wegame_version",
                "message": (
                    "检测到无畏契约（WeGame 国服版）正在运行，但国服版本不提供本地 API 接口。\n\n"
                    "💡 建议方案：\n"
                    "1. 切换到「🌐 Riot API（国际服）」数据源并使用国际服账号\n"
                    "2. 使用「🎮 演示数据」模式体验功能\n"
                    "3. 使用视频分析功能分析你的对局录像"
                ),
            }
        return {"available": False, "reason": "lockfile_not_found",
                "message": "未找到 Riot Client，请先启动无畏契约"}

    try:
        lockfile = read_lockfile(lockfile_path)
        base_url, headers = get_local_session(lockfile)
        session = _local_request("GET", base_url, headers, "/chat/v1/session")
        puuid = session.get("puuid", "")
        game_name = session.get("gameName", "")
        tag_line = session.get("tagLine", "")
        return {
            "available": True,
            "puuid": puuid,
            "game_name": game_name,
            "tag_line": tag_line,
            "lockfile": lockfile,
            "base_url": base_url,
            "auth_headers": headers,
        }
    except LocalClientError as e:
        return {"available": False, "reason": "auth_failed",
                "message": f"连接失败: {str(e)}"}


def get_remote_tokens(base_url: str, headers: Dict[str, str]) -> Dict[str, str]:
    """Exchange local auth for remote API access tokens."""
    data = _local_request("PUT", base_url, headers,
                          "/rso-auth/v1/authorization/access-token")
    token = data.get("token", "")
    entitlement = data.get("entitlements_token", "")
    if not token or not entitlement:
        raise LocalClientError("Failed to obtain remote API tokens.")
    return {"access_token": token, "entitlements_token": entitlement}


def get_client_version(base_url: str, headers: Dict[str, str]) -> str:
    """Extract the current client version from product sessions."""
    sessions = _local_request("GET", base_url, headers,
                              "/product-session/v1/product-sessions")
    if isinstance(sessions, list):
        for session in sessions:
            if session.get("productId") == "valorant":
                return session.get("version", "")
        if sessions:
            return sessions[0].get("version", "")
    if isinstance(sessions, dict):
        return sessions.get("version", "")
    raise LocalClientError("Could not determine client version.")


def _remote_request(method: str, url: str, tokens: Dict[str, str],
                    client_version: str, **kwargs) -> Any:
    """Make a request to the remote (pd.a.pvp.net) API."""
    headers = {
        "Authorization": f'Bearer {tokens["access_token"]}',
        "X-Riot-Entitlements-JWT": tokens["entitlements_token"],
        "X-Riot-ClientPlatform": CLIENT_PLATFORM,
        "X-Riot-ClientVersion": client_version,
    }
    kwargs.setdefault("timeout", 15)
    try:
        resp = requests.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            raise LocalClientError("No match data found for this account/region.")
        elif resp.status_code == 429:
            raise LocalClientError("Rate limited. Please wait and try again.")
        else:
            resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise LocalClientError("Remote API request timed out.")
    except (LocalClientError, ValueError):
        raise
    except Exception as e:
        raise LocalClientError(f"Remote API error: {str(e)}")


_VALORANT_REGIONS = ["ap", "na", "eu", "kr", "latam", "br"]


def fetch_match_history(puuid: str, tokens: Dict[str, str],
                        client_version: str, count: int = 20) -> List[str]:
    """Fetch recent match IDs by trying all Valorant regions."""
    for region in _VALORANT_REGIONS:
        try:
            url = (f"https://pd.{region}.a.pvp.net/match-history/v1/history/"
                   f"{puuid}?startIndex=0&endIndex={count}")
            data = _remote_request("GET", url, tokens, client_version)
            history = data.get("History", [])
            if history:
                match_ids = [m["MatchID"] for m in history if "MatchID" in m]
                logger.info(f"Found {len(match_ids)} matches in region {region}")
                return match_ids[:count]
        except LocalClientError:
            continue
    raise LocalClientError("Could not find match history in any region.")


def fetch_match_details(match_id: str, tokens: Dict[str, str],
                        client_version: str) -> Dict[str, Any]:
    """Fetch full match details from the remote API."""
    for region in _VALORANT_REGIONS:
        try:
            url = (f"https://pd.{region}.a.pvp.net/match-details/v1/"
                   f"matches/{match_id}")
            return _remote_request("GET", url, tokens, client_version)
        except LocalClientError:
            continue
    raise LocalClientError(f"Could not fetch match details for {match_id} "
                           f"from any region.")

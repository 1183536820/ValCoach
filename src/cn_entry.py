"""Manual match data entry for Chinese (WeGame) Valorant players.

Users copy stats from the in-game career page and enter them into
a structured form. The data feeds into the same analysis pipeline
as API-fetched data.
"""

from typing import List, Dict, Any, Tuple, Optional
import time
import streamlit as st

from src.metrics import aggregate_metrics
from src.diagnosis import METRIC_LABELS

_VALORANT_MAPS = [
    "", "Ascent", "Bind", "Haven", "Split", "Icebox",
    "Breeze", "Fracture", "Pearl", "Lotus", "Sunset",
    "Abyss", "Glitch",
]

_VALORANT_AGENTS = [
    "", "Jett", "Raze", "Reyna", "Phoenix", "Yoru", "Neon", "Iso",
    "Sage", "Cypher", "Killjoy", "Chamber", "Deadlock", "Vyse", "Tejo", "Waylay",
    "Brimstone", "Omen", "Astra", "Viper", "Harbor", "Clove",
    "Sova", "Breach", "Skye", "KAY/O", "Fade", "Gekko",
]


def _get_default_entry() -> Dict[str, Any]:
    return {
        "acs": 200,
        "kills": 10,
        "deaths": 10,
        "assists": 5,
        "kast": 70.0,
        "hs_percent": 20.0,
        "fb_rate": 10.0,
        "econ_rating": 1.0,
        "map_name": "",
        "agent": "",
        "won": None,
    }


def _entry_to_metrics(entry: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Convert a single entry dict to a metrics dict compatible with aggregate_metrics."""
    denom = entry["deaths"] + entry["assists"]
    kda = entry["kills"] / denom if denom > 0 else float(entry["kills"])
    return {
        "KDA": round(kda, 2),
        "ACS": round(entry["acs"], 2),
        "KAST": round(entry["kast"], 2),
        "headshot_percent": round(entry["hs_percent"], 2),
        "first_blood_rate": round(entry["fb_rate"], 2),
        "econ_rating": round(entry["econ_rating"], 2),
    }


def _entry_to_extra(entry: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Convert a single entry dict to a match-extra dict."""
    return {
        "agent_played": entry["agent"] or "Unknown",
        "map_name": entry["map_name"] or "Unknown",
        "won": entry["won"] if entry["won"] is not None else True,
        "game_start_timestamp": int(time.time() * 1000) - (index * 1800000),
    }


def _validate_entry(entry: Dict[str, Any], idx: int) -> Optional[str]:
    """Validate a single entry. Returns error string or None."""
    if entry["acs"] < 0 or entry["acs"] > 500:
        return f"第 {idx+1} 场: ACS 应在 0-500 之间"
    if entry["kills"] < 0 or entry["kills"] > 99:
        return f"第 {idx+1} 场: 击杀数应在 0-99 之间"
    if entry["deaths"] < 0 or entry["deaths"] > 99:
        return f"第 {idx+1} 场: 死亡数应在 0-99 之间"
    if entry["assists"] < 0 or entry["assists"] > 99:
        return f"第 {idx+1} 场: 助攻数应在 0-99 之间"
    if entry["kast"] < 0 or entry["kast"] > 100:
        return f"第 {idx+1} 场: KAST 应在 0-100 之间"
    if entry["hs_percent"] < 0 or entry["hs_percent"] > 100:
        return f"第 {idx+1} 场: 爆头率应在 0-100 之间"
    if entry["fb_rate"] < 0 or entry["fb_rate"] > 100:
        return f"第 {idx+1} 场: 首杀率应在 0-100 之间"
    if entry["econ_rating"] < 0 or entry["econ_rating"] > 5:
        return f"第 {idx+1} 场: 经济评分应在 0-5 之间"
    return None


def render_manual_entry_form() -> None:
    """Render the manual match entry form. Stores entries in st.session_state.cn_entries."""
    if "cn_entries" not in st.session_state:
        st.session_state.cn_entries = [_get_default_entry()]

    entries = st.session_state.cn_entries

    st.markdown("""
    <div class="glass-card">
        <h3><i class="fas fa-keyboard" style="margin-right:8px;"></i>📝 手动输入比赛数据</h3>
        <p>在游戏中打开<strong>「生涯」→「比赛记录」</strong>，查看每场数据并填入下方表单。
        至少需要 <strong>1 场</strong>，推荐 <strong>5+ 场</strong> 以获得更准确的分析。</p>
    </div>
    """, unsafe_allow_html=True)

    # Fill demo data button
    demo_col, _ = st.columns([1, 3])
    if demo_col.button("🎲 填入演示数据（快速测试）", use_container_width=True):
        import random
        random.seed(42)
        demo_entries = []
        for i in range(10):
            demo_entries.append({
                "acs": random.randint(150, 280),
                "kills": random.randint(8, 28),
                "deaths": random.randint(8, 22),
                "assists": random.randint(3, 14),
                "kast": round(random.uniform(55, 82), 1),
                "hs_percent": round(random.uniform(12, 32), 1),
                "fb_rate": round(random.uniform(3, 18), 1),
                "econ_rating": round(random.uniform(0.6, 1.6), 2),
                "map_name": random.choice([m for m in _VALORANT_MAPS if m]),
                "agent": random.choice([a for a in _VALORANT_AGENTS if a]),
                "won": random.choice([True, False]),
            })
        st.session_state.cn_entries = demo_entries
        st.rerun()

    st.markdown("---")

    # Render each match entry
    to_remove = None
    for idx, entry in enumerate(entries):
        with st.container():
            st.markdown(f"""
            <div style="background:rgba(255,70,85,0.05);border-radius:10px;
                        padding:12px 16px 4px;margin-bottom:8px;
                        border-left:3px solid #ff4655;">
                <b>🎮 第 {idx+1} 场</b>
            </div>
            """, unsafe_allow_html=True)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                entry["acs"] = col1.number_input(
                    "ACS", min_value=0, max_value=500, value=entry["acs"],
                    step=1, key=f"cn_acs_{idx}", format="%d",
                    help="每局平均战斗评分 (0-500)")
            with col2:
                entry["kills"] = col2.number_input(
                    "击杀", min_value=0, max_value=99, value=entry["kills"],
                    step=1, key=f"cn_kills_{idx}", format="%d")
            with col3:
                entry["deaths"] = col3.number_input(
                    "死亡", min_value=0, max_value=99, value=entry["deaths"],
                    step=1, key=f"cn_deaths_{idx}", format="%d")
            with col4:
                entry["assists"] = col4.number_input(
                    "助攻", min_value=0, max_value=99, value=entry["assists"],
                    step=1, key=f"cn_assists_{idx}", format="%d")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                entry["kast"] = col1.number_input(
                    "KAST (%)", min_value=0.0, max_value=100.0,
                    value=entry["kast"], step=0.5,
                    key=f"cn_kast_{idx}",
                    help="击杀/助攻/存活/被交易的回合占比")
            with col2:
                entry["hs_percent"] = col2.number_input(
                    "爆头率 (%)", min_value=0.0, max_value=100.0,
                    value=entry["hs_percent"], step=0.5,
                    key=f"cn_hs_{idx}")
            with col3:
                entry["fb_rate"] = col3.number_input(
                    "首杀率 (%)", min_value=0.0, max_value=100.0,
                    value=entry["fb_rate"], step=0.5,
                    key=f"cn_fb_{idx}", help="每回合首个击杀的比率")
            with col4:
                entry["econ_rating"] = col4.number_input(
                    "经济评分", min_value=0.0, max_value=5.0,
                    value=entry["econ_rating"], step=0.1,
                    key=f"cn_econ_{idx}", format="%.1f")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                entry["map_name"] = col1.selectbox(
                    "地图（选填）", _VALORANT_MAPS, index=0,
                    key=f"cn_map_{idx}")
            with col2:
                entry["agent"] = col2.selectbox(
                    "英雄（选填）", _VALORANT_AGENTS, index=0,
                    key=f"cn_agent_{idx}")
            with col3:
                won_options = ["未选", "胜利 ✅", "失败 ❌"]
                current_won = 0 if entry["won"] is None else (1 if entry["won"] else 2)
                won_idx = col3.selectbox(
                    "胜负（选填）", won_options,
                    index=current_won, key=f"cn_won_{idx}")
                if won_idx == 0:
                    entry["won"] = None
                elif won_idx == 1:
                    entry["won"] = True
                else:
                    entry["won"] = False
            with col4:
                if len(entries) > 1:
                    if col4.button("🗑️ 移除", key=f"cn_rm_{idx}"):
                        to_remove = idx

        st.markdown("<div style='margin-bottom:12px;'></div>", unsafe_allow_html=True)

    # Add match button
    add_col, _ = st.columns([1, 3])
    if add_col.button("➕ 添加一场比赛", use_container_width=True):
        entries.append(_get_default_entry())
        st.rerun()

    # Remove pending entry
    if to_remove is not None and to_remove < len(entries):
        entries.pop(to_remove)
        st.rerun()

    st.markdown("---")
    st.markdown(f"<p style='color:#888;font-size:0.85rem;'>已录入 <b>{len(entries)}</b> 场比赛（点击下方「生成诊断报告」开始分析）</p>",
                unsafe_allow_html=True)


def process_entries(entries: List[Dict[str, Any]]) -> Tuple[bool, List[Dict[str, float]], List[Dict[str, Any]]]:
    """Validate and convert form entries to pipeline-compatible format.

    Returns:
        (valid, all_metrics, all_match_extras)
    """
    if not entries:
        st.error("请至少添加一场比赛的数据。")
        return False, [], []

    for idx, entry in enumerate(entries):
        err = _validate_entry(entry, idx)
        if err:
            st.error(f"❌ {err}")
            return False, [], []

    all_metrics = []
    all_match_extras = []
    for idx, entry in enumerate(entries):
        m = _entry_to_metrics(entry)
        all_metrics.append(m)
        e = _entry_to_extra(entry, idx)
        e["metrics"] = m
        all_match_extras.append(e)

    return True, all_metrics, all_match_extras

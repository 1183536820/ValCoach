"""OCR-based match data extraction from Valorant screenshots.

Users upload screenshots of the Valorant career page (生涯 → 比赛记录)
or post-game scoreboard. EasyOCR extracts numerical stats, which are
then fed into the same analysis pipeline as manual entry data.
"""

from typing import List, Dict, Any, Optional, Tuple
import time
import re
from dataclasses import dataclass

import streamlit as st
import numpy as np
from PIL import Image

from src.logger import get_logger

logger = get_logger()

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Lazy-loaded EasyOCR reader
# ---------------------------------------------------------------------------

_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        try:
            import easyocr
        except ImportError:
            st.error("⚠️ EasyOCR 未安装。截图识别功能需要在本地手动安装依赖：

```
pip install easyocr
```

在线版（Streamlit Cloud）不支持此功能，请切换其他数据源。")
            st.stop()
        # Show a one-time status message on first load
        st.info("🔄 EasyOCR 正在加载模型（首次使用会下载约 100MB 模型文件）...")
        progress_placeholder = st.empty()
        _reader = easyocr.Reader(["en", "ch_sim"], gpu=False)
        progress_placeholder.success("✅ EasyOCR 模型加载完成！")
    return _reader


# ---------------------------------------------------------------------------
# Image preprocessing
# ---------------------------------------------------------------------------

def _load_image(uploaded_file) -> Image.Image:
    """Load an uploaded file into a PIL Image."""
    return Image.open(uploaded_file).convert("RGB")


def _preprocess_for_ocr(image: Image.Image) -> np.ndarray:
    """Convert PIL image to numpy array (RGB) for EasyOCR."""
    return np.array(image)


# ---------------------------------------------------------------------------
# OCR result parsing
# ---------------------------------------------------------------------------

@dataclass
class OCRText:
    text: str
    conf: float
    y_center: float
    x_center: float
    y_min: float
    y_max: float
    x_min: float
    x_max: float


def _run_ocr(image: np.ndarray) -> List[OCRText]:
    """Run EasyOCR and return structured results."""
    reader = _get_reader()
    raw = reader.readtext(image)
    items = []
    for bbox, text, conf in raw:
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        items.append(OCRText(
            text=str(text).strip(),
            conf=conf,
            y_center=sum(ys) / 4,
            x_center=sum(xs) / 4,
            y_min=min(ys),
            y_max=max(ys),
            x_min=min(xs),
            x_max=max(xs),
        ))
    return items


def _parse_number(s: str) -> Optional[float]:
    """Safe number parsing, strips trailing % etc."""
    s = s.strip().rstrip("%").replace(",", ".").replace("O", "0").replace("o", "0")
    # Handle common OCR confusions: l→1, S→5, etc.
    s = s.replace("l", "1").replace("I", "1").replace("S", "5").replace("s", "5")
    try:
        return float(s)
    except ValueError:
        # Try regex fallback
        m = re.search(r"(\d+[.,]?\d*)", s)
        if m:
            return float(m.group(1).replace(",", "."))
        return None


def _extract_all_numbers(text: str) -> List[float]:
    """Extract ALL numbers from a text string (handles merged OCR text).

    Useful when OCR merges adjacent numbers like '12 8' or '12  8'.
    """
    cleaned = text.strip().rstrip("%").replace(",", ".")
    # Replace common OCR confusions
    cleaned = cleaned.replace("O", "0").replace("o", "0")
    cleaned = cleaned.replace("l", "1").replace("I", "1").replace("S", "5").replace("s", "5")
    # Find all number patterns
    matches = re.findall(r"(\d+[.]?\d*)", cleaned)
    return [float(m) for m in matches]


def _group_by_row(items: List[OCRText], row_threshold: float = 0.05) -> List[List[OCRText]]:
    """Group OCR items into rows based on Y-coordinate proximity.

    row_threshold is a fraction of image height for grouping tolerance.
    """
    if not items:
        return []
    sorted_items = sorted(items, key=lambda x: x.y_center)
    rows = [[sorted_items[0]]]
    y_range = max(i.y_max - i.y_min for i in sorted_items) or 1

    for item in sorted_items[1:]:
        prev_y = rows[-1][-1].y_center
        if abs(item.y_center - prev_y) / y_range < row_threshold:
            rows[-1].append(item)
        else:
            rows.append([item])

    # Sort items within each row by X
    for row in rows:
        row.sort(key=lambda x: x.x_center)

    return rows


def _find_header_row(rows: List[List[OCRText]]) -> Optional[Dict[str, float]]:
    """Find the header row and determine column X positions for each stat.

    Returns a dict mapping stat_key -> x_center, or None if not found.
    """
    # Known header keywords and their stat mappings
    header_patterns = {
        "acs": ["acs", "战斗评分", "评分"],
        "kills": ["击杀", "kill", "kills"],
        "deaths": ["死亡", "deaths", "death"],
        "assists": ["助攻", "assists", "assist"],
        "kast": ["kast", "kast%", "参与率"],
        "hs": ["爆头率", "爆头", "hs%", "hs", "headshot"],
        "fk": ["首杀", "首杀率", "fk", "first"],
        "fd": ["首死", "fd", "firstdeath"],
        "adr": ["adr", "平均伤害", "伤害"],
    }
    # Flatten for lookup
    all_keywords = {}
    for stat, words in header_patterns.items():
        for w in words:
            all_keywords[w] = stat

    best_row = None
    best_matches = 0
    best_cols = {}

    for row in rows:
        col_map = {}
        match_count = 0
        for item in row:
            text_lower = item.text.strip().lower()
            if text_lower in all_keywords:
                stat = all_keywords[text_lower]
                if stat not in col_map:
                    col_map[stat] = item.x_center
                    match_count += 1
        if match_count > best_matches:
            best_matches = match_count
            best_cols = col_map
            best_row = row

    if best_matches >= 2:  # Need at least 2 header matches to be confident
        return best_cols
    return None


def _find_user_data_row(rows: List[List[OCRText]], header_y: Optional[float] = None) -> Optional[List[OCRText]]:
    """Find the user's data row (highlighted or with most numbers).

    In the Valorant scoreboard, the user's row has a teal/blue highlight.
    Falls back to the row with the most numbers below the header.
    """
    # Strategy 1: Find highlighted row (higher blue+green values)
    # We need the original image for this, which isn't available here.
    # Use a proxy: look for the row with the most numeric values below header

    if not rows:
        return None

    # Sort rows by Y to find rows below header
    sorted_rows = sorted(rows, key=lambda r: r[0].y_center if r else 0)

    # Find all rows that contain numbers (potential data rows)
    data_rows = []
    for row in sorted_rows:
        num_count = sum(len(_extract_all_numbers(item.text)) for item in row)
        if num_count >= 3:  # At least 3 numbers = likely a data row
            data_rows.append(row)

    if not data_rows:
        return None

    # The user's row is typically the first data row (topmost) in the scoreboard,
    # or it can be identified by having the highest number count
    data_rows.sort(key=lambda r: -sum(len(_extract_all_numbers(it.text)) for it in r))
    return data_rows[0]


def _extract_stats_from_ocr(items: List[OCRText], image: np.ndarray) -> Dict[str, Any]:
    """Parse OCR results into a match stats dictionary.

    Uses column-based matching by detecting header positions, then
    finding corresponding values in the user's data row.
    """
    stats = {
        "acs": None, "kills": None, "deaths": None, "assists": None,
        "kast": None, "hs_percent": None, "fb_rate": None,
        "econ_rating": 1.0,  # Default, not on scoreboard
        "map_name": "", "agent": "", "won": None,
    }

    h, w = image.shape[:2]
    rows = _group_by_row(items)

    # ── Step 1: Detect column headers → X positions ──
    header_cols = _find_header_row(rows)

    # ── Step 2: Find user's data row ──
    user_row = _find_user_data_row(rows)

    if user_row is None:
        return stats

    # Extract numbers from user row with their positions
    # Use _extract_all_numbers to handle merged text like "12  8"
    raw_user_numbers = []
    for item in user_row:
        nums = _extract_all_numbers(item.text)
        for n in nums:
            raw_user_numbers.append((n, item.x_center))
        # Check for win/loss text
        text_lower = item.text.strip().lower()
        if text_lower in ("win", "w", "victory", "胜"):
            stats["won"] = True
        elif text_lower in ("loss", "l", "defeat", "负", "败"):
            stats["won"] = False

    if not raw_user_numbers:
        return stats

    # Deduplicate: when OCR detects same number at close X positions
    # (e.g. original+enhanced both detect "12" at slightly different x),
    # keep the first occurrence per approximate position
    user_numbers = []
    x_bucket_size = w * 0.02
    seen_buckets = set()
    for val, x in sorted(raw_user_numbers, key=lambda p: p[1]):
        bucket = (val, round(x / x_bucket_size))
        if bucket not in seen_buckets:
            seen_buckets.add(bucket)
            user_numbers.append((val, x))

    # ── Step 3: Match stats by column position ──
    if header_cols:
        # Sort headers left-to-right and track used number indices to prevent
        # two different stats from claiming the same value (e.g. ACS value 605
        # being picked by both "acs" and "assists" columns).
        sorted_headers = sorted(header_cols.items(), key=lambda kv: kv[1])
        used_idxs: set = set()

        for stat_key, col_x in sorted_headers:
            best_val = None
            best_dist = float("inf")
            best_idx = -1
            for idx, (val, val_x) in enumerate(user_numbers):
                if idx in used_idxs:
                    continue
                dist = abs(val_x - col_x)
                if dist < best_dist:
                    best_dist = dist
                    best_val = val
                    best_idx = idx

            if best_idx >= 0 and best_dist < w * 0.08:
                used_idxs.add(best_idx)
                if stat_key == "acs":
                    stats["acs"] = best_val
                elif stat_key == "kills":
                    stats["kills"] = best_val
                elif stat_key == "deaths":
                    stats["deaths"] = best_val
                elif stat_key == "assists":
                    stats["assists"] = best_val
                elif stat_key == "kast" and best_val <= 100:
                    stats["kast"] = best_val
                elif stat_key == "hs" and best_val <= 100:
                    stats["hs_percent"] = best_val
                elif stat_key == "fk" and best_val <= 20:
                    stats["fb_rate"] = best_val

        # Build remaining unassigned numbers (not yet used by header matching)
        unassigned = [v for i, (v, x) in enumerate(user_numbers) if i not in used_idxs]
    else:
        # No header detected — use all numbers in left-to-right order
        sorted_numbers = sorted(user_numbers, key=lambda p: p[1])
        unassigned = [v for v, _ in sorted_numbers]

    # ── Step 4: Position-based fallback ──
    if stats["acs"] is None and unassigned:
        stats["acs"] = unassigned.pop(0)
    if stats["kills"] is None and unassigned:
        stats["kills"] = unassigned.pop(0)
    if stats["deaths"] is None and unassigned:
        stats["deaths"] = unassigned.pop(0)
    if stats["assists"] is None and unassigned:
        stats["assists"] = unassigned.pop(0)

    return stats


# ---------------------------------------------------------------------------
# Main extraction pipeline
# ---------------------------------------------------------------------------

def extract_stats_from_screenshot(image: Image.Image) -> Optional[Dict[str, Any]]:
    """Full OCR pipeline: preprocess → detect → parse.

    Args:
        image: PIL Image of a Valorant scoreboard screenshot.

    Returns:
        Stats dict compatible with cn_entry._get_default_entry(), or None if
        parsing fails.
    """
    try:
        img_array = _preprocess_for_ocr(image)
        # Run OCR on original image only (running on both original + enhanced
        # creates duplicate number detections that confuse positional parsing)
        merged = _run_ocr(img_array)

        stats = _extract_stats_from_ocr(merged, img_array)

        # Validate: at minimum we need ACS and kills
        if stats["acs"] is not None and stats["kills"] is not None:
            return stats

        return None

    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

def _clamp(value, lo, hi, default):
    """Clamp value to [lo, hi]; return default if value is not a number."""
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return default


def render_ocr_entry_form(game_name: str = "国服玩家", tag_line: str = "CN") -> None:
    """Render the screenshot OCR upload & review UI.

    Args:
        game_name: Player name from the main input field.
        tag_line: Tag line from the main input field.
    """
    # Store for _run_ocr_analysis
    st.session_state._ocr_player_name = game_name or "国服玩家"
    st.session_state._ocr_tag_line = tag_line or "CN"

    st.markdown("""
    <div class="glass-card">
        <h3><i class="fas fa-camera" style="margin-right:8px;"></i>📸 截图自动识别</h3>
        <p>截取无畏契约<strong>「生涯 → 比赛记录」</strong>中每场比赛的统计卡片，
        或<strong>结算页面</strong>的完整数据表。上传截图后自动识别数值，建议使用清晰的全屏截图。</p>
    </div>
    """, unsafe_allow_html=True)

    try:
        import easyocr
    except ImportError:
        st.warning("⚠️ 截图识别需要 EasyOCR，当前环境未安装。如需使用此功能，请在本地运行项目：pip install easyocr。在线版（Streamlit Cloud）请切换其他数据源。")

    # Initialize session state
    if "ocr_entries" not in st.session_state:
        st.session_state.ocr_entries = []
    if "ocr_processing" not in st.session_state:
        st.session_state.ocr_processing = False

    # ── File upload ──
    uploaded_files = st.file_uploader(
        "上传无畏契约截图（支持 PNG / JPG）",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
        help="截取结算页面或生涯比赛记录的清晰截图上传。每张截图应包含一场比赛的数据。",
    )

    # Process uploaded files
    if uploaded_files and st.button("🔍 开始自动识别", type="primary", use_container_width=True):
        st.session_state.ocr_processing = True
        st.session_state.ocr_entries = []
        progress_bar = st.progress(0, text="正在识别...")
        status_text = st.empty()

        total_files = len(uploaded_files)
        new_entries = []

        for idx, f in enumerate(uploaded_files):
            progress = int((idx / total_files) * 90)
            progress_bar.progress(progress, text=f"正在识别第 {idx+1}/{total_files} 张截图...")
            status_text.info(f"⏳ 处理中: {f.name}")

            try:
                image = _load_image(f)
                # Display a small preview
                with st.expander(f"📷 {f.name}", expanded=(idx == 0)):
                    st.image(image, caption=f"截图 {idx+1}", use_column_width=True)
                    st.caption(f"原始尺寸: {image.width} × {image.height}")

                stats = extract_stats_from_screenshot(image)

                if stats:
                    # Write stats to session so user can edit
                    entry_key = f"ocr_entry_{idx}"
                    st.session_state[entry_key] = stats
                    new_entries.append(stats)
                    st.success(f"✅ 识别成功！ACS: {stats.get('acs', '?')}, "
                               f"K/D/A: {stats.get('kills', '?')}/{stats.get('deaths', '?')}/{stats.get('assists', '?')}")
                else:
                    st.warning(f"⚠️ 未能从「{f.name}」中识别出有效数据，请检查截图是否包含完整的统计面板。")

            except Exception as e:
                logger.error(f"Failed to process {f.name}: {e}")
                st.error(f"❌ 处理 {f.name} 时出错: {e}")

            progress_bar.progress(int(((idx + 1) / total_files) * 90),
                                  text=f"已完成 {idx+1}/{total_files}")

        st.session_state.ocr_entries = new_entries
        progress_bar.progress(100, text="识别完成！")
        status_text.success(f"🎉 处理完成！成功识别 {len(new_entries)}/{total_files} 张截图")

        if not new_entries:
            st.error("没有成功识别任何截图。请检查截图质量后再试。")
            st.info("💡 提示：确保截图中包含完整的统计面板（ACS, K/D/A, KAST, 爆头率等数值）。"
                    "建议在游戏内按 PrintScreen 后粘贴到画图工具，保存为 PNG 格式。")

    # ── Review & Edit extracted entries ──
    if st.session_state.ocr_entries:
        st.markdown("---")
        st.markdown("### 📋 识别结果（请检查并修正）")
        st.markdown("""
        <div style="background:rgba(255,255,255,0.05);padding:10px 16px;border-radius:8px;margin-bottom:16px;
                    border-left:3px solid #ff4655;font-size:0.85rem;">
        ⚠️ <b>OCR 识别可能有误差</b>，请核对下方每个数值，特别是：
        <ul style="margin:4px 0 0 16px;">
            <li>K/D/A 是否正确分割</li>
            <li>百分比数值（KAST, 爆头率）是否在合理范围</li>
            <li>经济评分不在截图中，已设为默认值 1.0，可手动修正</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)

        # Let user edit the extracted entries
        entries_updated = False
        for idx, entry in enumerate(st.session_state.ocr_entries):
            with st.container():
                col1, col2 = st.columns([1, 5])
                with col1:
                    st.markdown(f"**🎮 第 {idx+1} 场**")
                    if st.button("🗑️ 移除", key=f"ocr_rm_{idx}"):
                        st.session_state.ocr_entries.pop(idx)
                        entries_updated = True
                        st.experimental_rerun()
                with col2:
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        entry["acs"] = c1.number_input(
                            "ACS", 0, 500, int(_clamp(entry.get("acs"), 0, 500, 200)),
                            step=1, key=f"ocr_acs_{idx}", format="%d")
                    with c2:
                        entry["kills"] = c2.number_input(
                            "击杀", 0, 99, int(_clamp(entry.get("kills"), 0, 99, 10)),
                            step=1, key=f"ocr_kills_{idx}", format="%d")
                    with c3:
                        entry["deaths"] = c3.number_input(
                            "死亡", 0, 99, int(_clamp(entry.get("deaths"), 0, 99, 10)),
                            step=1, key=f"ocr_deaths_{idx}", format="%d")
                    with c4:
                        entry["assists"] = c4.number_input(
                            "助攻", 0, 99, int(_clamp(entry.get("assists"), 0, 99, 5)),
                            step=1, key=f"ocr_assists_{idx}", format="%d")

                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        entry["kast"] = c1.number_input(
                            "KAST (%)", 0.0, 100.0, float(_clamp(entry.get("kast"), 0, 100, 70)),
                            step=0.5, key=f"ocr_kast_{idx}",
                            help="击杀/助攻/存活/被交易的回合占比")
                    with c2:
                        entry["hs_percent"] = c2.number_input(
                            "爆头率 (%)", 0.0, 100.0, float(_clamp(entry.get("hs_percent"), 0, 100, 20)),
                            step=0.5, key=f"ocr_hs_{idx}")
                    with c3:
                        entry["fb_rate"] = c3.number_input(
                            "首杀率 (%)", 0.0, 100.0, float(_clamp(entry.get("fb_rate"), 0, 100, 10)),
                            step=0.5, key=f"ocr_fb_{idx}",
                            help="首杀/首死率，根据截图中的 FK 值估算")
                    with c4:
                        entry["econ_rating"] = c4.number_input(
                            "经济评分", 0.0, 5.0, float(_clamp(entry.get("econ_rating"), 0, 5, 1.0)),
                            step=0.1, key=f"ocr_econ_{idx}", format="%.1f",
                            help="不在截图中，设为默认值 1.0，可手动修正")

                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        entry["map_name"] = c1.selectbox(
                            "地图（选填）", _VALORANT_MAPS,
                            index=_VALORANT_MAPS.index(entry.get("map_name", ""))
                                if entry.get("map_name", "") in _VALORANT_MAPS else 0,
                            key=f"ocr_map_{idx}")
                    with c2:
                        entry["agent"] = c2.selectbox(
                            "英雄（选填）", _VALORANT_AGENTS,
                            index=_VALORANT_AGENTS.index(entry.get("agent", ""))
                                if entry.get("agent", "") in _VALORANT_AGENTS else 0,
                            key=f"ocr_agent_{idx}")
                    with c3:
                        won_options = ["未选", "胜利 ✅", "失败 ❌"]
                        current = entry.get("won")
                        current_idx = 0 if current is None else (1 if current else 2)
                        won_idx = c3.selectbox(
                            "胜负（选填）", won_options,
                            index=current_idx, key=f"ocr_won_{idx}")
                        entry["won"] = None if won_idx == 0 else (True if won_idx == 1 else False)
                    with c4:
                        st.caption("")

        if entries_updated:
            st.experimental_rerun()

        st.markdown("---")
        num_entries = len(st.session_state.ocr_entries)
        st.markdown(
            f"<p style='color:#888;font-size:0.85rem;'>已识别 <b>{num_entries}</b> 场比赛"
            f"（请确认数值正确后，点击下方按钮开始分析）</p>",
            unsafe_allow_html=True,
        )

        # ── Run analysis button ──
        col_a, col_b = st.columns([3, 1])
        with col_a:
            if st.button("📊 生成诊断报告", type="primary", use_container_width=True):
                _run_ocr_analysis()
        with col_b:
            if st.button("🔄 清空所有", use_container_width=True):
                st.session_state.ocr_entries = []
                st.experimental_rerun()


def _validate_ocr_entries(entries: List[Dict[str, Any]]) -> Optional[str]:
    """Validate OCR entries. Returns error message or None."""
    for idx, entry in enumerate(entries):
        if entry["acs"] < 0 or entry["acs"] > 500:
            return f"第 {idx+1} 场: ACS 应在 0-500 之间（当前: {entry['acs']}）"
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


def _entry_to_metrics(entry: Dict[str, Any]) -> Dict[str, float]:
    """Convert OCR entry dict to metrics dict compatible with aggregate_metrics."""
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
    """Convert OCR entry dict to match-extra dict."""
    return {
        "agent_played": entry.get("agent", "") or "Unknown",
        "map_name": entry.get("map_name", "") or "Unknown",
        "won": entry.get("won") if entry.get("won") is not None else True,
        "game_start_timestamp": int(time.time() * 1000) - (index * 1800000),
    }


def _run_ocr_analysis() -> None:
    """Validate OCR entries, convert to pipeline format, and run analysis."""
    from src.pipeline import run_analysis_pipeline

    entries = st.session_state.ocr_entries

    # Validate
    err = _validate_ocr_entries(entries)
    if err:
        st.error(f"❌ {err}")
        return

    if not entries:
        st.error("请至少保留一场比赛的数据。")
        return

    all_metrics = []
    all_match_extras = []

    for idx, entry in enumerate(entries):
        m = _entry_to_metrics(entry)
        all_metrics.append(m)
        e = _entry_to_extra(entry, idx)
        e["metrics"] = m
        all_match_extras.append(e)

    game_name = st.session_state.get("_ocr_player_name", "").strip() or "国服玩家"
    tag_line = st.session_state.get("_ocr_tag_line", "").strip() or "CN"

    # Determine if user has full (paid/admin) access
    is_full = False
    user = st.session_state.get("user")
    if user:
        if user.get("tier") == "admin":
            is_full = True
        else:
            try:
                import src.database as db
                is_full = db.has_user_paid(user["id"])
            except Exception:
                pass

    progress_bar = st.progress(0, text="正在分析数据...")
    status_text = st.empty()

    try:
        status_text.info("📊 正在计算指标...")
        progress_bar.progress(30)

        report = run_analysis_pipeline(
            all_metrics, all_match_extras,
            game_name, tag_line, is_full=is_full,
        )

        if report is None:
            st.error("分析失败，请检查输入数据。")
            return

        progress_bar.progress(85)
        status_text.info("正在生成报告...")
        player_display_id = f"{game_name}#{tag_line}"

        st.session_state.report_html = report.html
        st.session_state.report_player = player_display_id
        st.session_state.report_metrics = report.avg_metrics
        st.session_state.report_strengths = report.strengths

        # Save to DB if user is logged in
        if st.session_state.get("user"):
            try:
                import src.database as db
                db.save_report(st.session_state.user["id"], player_display_id, report.html)
            except Exception:
                pass

        progress_bar.progress(100)
        status_text.success(f"🎉 分析完成！（截图识别 · 共 {len(entries)} 场）")
        st.components.v1.html(report.html, height=1800, scrolling=True)

    except Exception as e:
        logger.error(f"OCR analysis error: {e}")
        st.error(f"❌ 分析出错: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
    finally:
        progress_bar.empty()
        status_text.empty()

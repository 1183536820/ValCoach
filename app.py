import os
import sys
import traceback
import random
import time

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.logger import get_logger

logger = get_logger()

try:
    RIO_TXT_CONTENT = open(os.path.join(os.path.dirname(__file__), "riot.txt"), "r").read().strip()
except Exception:
    RIO_TXT_CONTENT = None


def _rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def _is_valid_api_key(key: str) -> bool:
    return bool(key and key.strip() and key != "RGAPI-你的密钥")

import src.api_client as api_client
from src.api_client import get_puuid, get_match_history, get_match_details
import src.local_client as local_client
from src.sidebar import render_sidebar
from src.metrics import calculate_metrics, aggregate_metrics, extract_match_extra, calculate_map_hero_breakdown
from src.baseline import load_baseline
from src.diagnosis import diagnose, diagnose_map_hero_weakness, diagnose_strengths
from src.report_generator import generate_report, build_share_card, generate_pdf_report
from src.cn_entry import render_manual_entry_form
import src.database as db
from pages.video_analysis import video_analysis_page
try:
    from src.payment import create_checkout_session, verify_payment
    PAYMENT_AVAILABLE = True
except Exception:
    create_checkout_session = None
    verify_payment = None
    PAYMENT_AVAILABLE = False

try:
    from src.mailer import send_report_email
    MAILER_AVAILABLE = True
except Exception:
    send_report_email = None
    MAILER_AVAILABLE = False

ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "").split(",")
ADMIN_EMAILS = [e.strip() for e in ADMIN_EMAILS if e.strip()]


def _has_full_access(user) -> bool:
    if user is None:
        return False
    if user.get("tier") == "admin" or user.get("email") in ADMIN_EMAILS:
        return True
    return db.has_user_paid(user["id"])


def _get_demo_metrics():
    results = []
    for _ in range(20):
        results.append({
            "KDA": round(random.uniform(0.5, 2.0), 2),
            "ACS": round(random.uniform(100, 300), 2),
            "KAST": round(random.uniform(50, 85), 2),
            "headshot_percent": round(random.uniform(10, 35), 2),
            "first_blood_rate": round(random.uniform(2, 18), 2),
            "econ_rating": round(random.uniform(0.5, 1.8), 2),
        })
    return results


def _guess_tier(avg_acs: float) -> str:
    tiers_acs = [
        ("Iron", 120), ("Bronze", 140), ("Silver", 160), ("Gold", 185),
        ("Platinum", 205), ("Diamond", 230), ("Ascendant", 250),
        ("Immortal", 270), ("Radiant", 300),
    ]
    best = "Gold"
    for tier, acs in tiers_acs:
        if avg_acs >= acs:
            best = tier
    return best


def _generate_demo_report(game_name, tag_line, baseline_data, is_full=False):
    all_metrics = _get_demo_metrics()
    avg_metrics = aggregate_metrics(all_metrics)
    diagnosis_results = diagnose(avg_metrics, baseline_data)
    strength_results = diagnose_strengths(avg_metrics, baseline_data) if is_full else []

    demo_history = [{"value": m["ACS"], "date": f"场次{i+1}"} for i, m in enumerate(all_metrics)]
    demo_kast = [{"value": m["KAST"], "date": f"场次{i+1}"} for i, m in enumerate(all_metrics)]

    demo_breakdown = {
        "Ascent": {"Jett": {"avg_acs": 180, "avg_kda": 0.9, "match_count": 5}},
        "Bind": {"Raze": {"avg_acs": 210, "avg_kda": 1.2, "match_count": 4}},
        "Haven": {"Sage": {"avg_acs": 160, "avg_kda": 0.7, "match_count": 3}},
    }
    map_hero_results = diagnose_map_hero_weakness(demo_breakdown, global_avg_acs=avg_metrics.get("ACS", 200))

    player_display_id = f"{game_name}#{tag_line}"
    html_report = generate_report(
        player_id=player_display_id,
        player_metrics=avg_metrics,
        diagnosis_results=diagnosis_results,
        baseline_metrics=baseline_data,
        acs_trend=demo_history if is_full else None,
        kast_trend=demo_kast if is_full else None,
        map_hero_results=map_hero_results if is_full else None,
        strength_results=strength_results if is_full else None,
    )
    return html_report, avg_metrics, all_metrics, strength_results


db.init_db()
admin_id = db.seed_admin_account()
logger.info(f"Admin account ready (id={admin_id})")

st.set_page_config(
    page_title="ValCoach - 《无畏契约》AI 教练",
    page_icon="🎯",
    layout="wide",
)

# Serve riot.txt publicly at ?raw=riot (fallback access method)
if RIO_TXT_CONTENT:
    try:
        if st.query_params.get("raw") == "riot":
            st.header("riot.txt")
            st.code(RIO_TXT_CONTENT, language="text")
            st.caption("Public file — used by client-side Riot API calls.")
            st.stop()
    except AttributeError:
        try:
            if st.experimental_get_query_params().get("raw", [""])[0] == "riot":
                st.header("riot.txt")
                st.code(RIO_TXT_CONTENT, language="text")
                st.caption("Public file — used by client-side Riot API calls.")
                st.stop()
        except Exception:
            logger.warning("Failed to parse query params for riot.txt fallback")

st.markdown("""
<meta name="description" content="ValCoach - 《无畏契约》AI 赛后诊断工具。分析你的排位赛数据，找出短板，提升段位。">
<meta property="og:title" content="ValCoach - 《无畏契约》AI 教练">
<meta property="og:description" content="AI驱动的无畏契约赛后分析工具，6项核心指标诊断，雷达图可视化报告。">
""", unsafe_allow_html=True)

# JS redirect: /riot.txt → ?raw=riot (runs in browser, uses iframe so scripts execute)
if RIO_TXT_CONTENT:
    components.html("""
<script>
(function() {
    var p = window.parent.location.pathname.replace(/\\/+/g, '/');
    if (p.endsWith('/riot.txt') && window.parent.location.search.indexOf('raw=riot') === -1) {
        window.parent.location.replace(window.parent.location.origin + '/?raw=riot');
    }
})();
</script>
""", height=0)

from src.styles import APP_CSS

st.markdown(f"<style>{APP_CSS}</style>", unsafe_allow_html=True)

if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "analysis"
if "report_html" not in st.session_state:
    st.session_state.report_html = None
if "report_player" not in st.session_state:
    st.session_state.report_player = None
if "report_metrics" not in st.session_state:
    st.session_state.report_metrics = None
if "report_strengths" not in st.session_state:
    st.session_state.report_strengths = None

render_sidebar(ADMIN_EMAILS, _is_valid_api_key)
data_source = st.session_state.get("data_source", "🌐 Riot API（国际服）")
demo_mode = (data_source == "🎮 演示数据")
local_mode = (data_source == "💻 本地客户端")

if st.session_state.page == "history" and st.session_state.user:
    st.markdown("# <i class='fas fa-history' style='margin-right:8px;'></i> 我的历史报告", unsafe_allow_html=True)
    reports = db.get_user_reports(st.session_state.user["id"])
    if reports:
        for r in reports:
            with st.container():
                st.markdown(f"**{r['player_name']}** - {r['created_at']}")
                col_a, col_b = st.columns(2)
                if col_a.button("查看", key=f"view_{r['id']}"):
                    report_data = db.get_report_by_id(r["id"])
                    if report_data:
                        st.session_state.report_html = report_data["report_html"]
                        st.components.v1.html(report_data["report_html"], height=1800, scrolling=True)
                if col_b.button("删除", key=f"del_{r['id']}"):
                    st.info("删除功能待实现")
    else:
        st.info("暂无历史报告，快去生成一份吧！")
        if st.button("返回分析页"):
            st.session_state.page = "analysis"
            _rerun()
    st.markdown("---")
    if st.button("⬅️ 返回分析"):
        st.session_state.page = "analysis"
        _rerun()

elif st.session_state.page == "video_analysis":
    with st.container():
        video_analysis_page()

elif st.session_state.page == "analysis":
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.markdown("# ValCoach - 《无畏契约》AI 教练")
    st.markdown("<p>输入你的游戏ID和Tagline，获取专属赛后诊断报告</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.user:
        tier_label = st.session_state.user.get("tier", "免费")
        if tier_label == "admin":
            st.info(f"👑 管理员已登录，所有功能已解锁")
        else:
            st.info(f"👋 欢迎回来，{st.session_state.user['email']}")

    src_label = data_source
    st.markdown(f"""
    <div class="status-msg">
        <i class="fas fa-info-circle" style="margin-right:6px;"></i>
        当前数据源：<b style="color:#ff4655;">{src_label}</b>
        <span style="color:#777;font-size:0.8rem;"> — 可在左侧边栏切换</span>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="glass-card"><h3><i class="fas fa-crosshairs" style="margin-right:8px;"></i>AI 驱动的赛后诊断</h3><p>自动拉取你最近20场排位赛数据，与同段位玩家基准进行6维对比，精准定位你的短板，提供可执行的训练建议。</p></div>', unsafe_allow_html=True)

        st.markdown("""<i class="fas fa-compass" style="color:#ff4655;margin-right:4px;"></i> **三步使用指南**""", unsafe_allow_html=True)
        guide_cols = st.columns(3)
        steps = [
            ("1", "输入ID", "输入你的游戏ID和Tagline"),
            ("2", "自动分析", "系统拉取最近20场排位赛数据"),
            ("3", "获取报告", "一键生成诊断报告和改进建议"),
        ]
        for col, (num, title, desc) in zip(guide_cols, steps):
            with col:
                st.markdown(f"""
                <div class="step-card">
                    <div class="step-num">{num}</div>
                    <span class="step-label">{title}</span>
                    <p>{desc}</p>
                </div>
                """, unsafe_allow_html=True)

        cols = st.columns(3)
        features = [
            ('<i class="fas fa-chart-bar"></i>', "全面指标", "KDA/ACS/KAST/爆头率/首杀率/经济评分"),
            ('<i class="fas fa-brain"></i>', "智能诊断", "AI分析短板，给出针对性训练建议"),
            ('<i class="fas fa-chart-line"></i>', "趋势追踪", "查看ACS和KAST的历史变化趋势"),
        ]
        for col, (icon, title, desc) in zip(cols, features):
            with col:
                st.markdown(f"""
                <div class="glass-card" style="text-align:center;">
                    <div class="card-icon">{icon}</div>
                    <p style="color:#e0e0e0;font-weight:600;margin-bottom:6px;">{title}</p>
                    <p>{desc}</p>
                </div>
                """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        game_name = st.text_input("游戏ID", placeholder="例如: Player1", help="你的 Riot 游戏 ID（不含 Tagline）")
    with col2:
        tag_line = st.text_input("Tagline", placeholder="例如: 1234", help="你的 Riot ID 后的 # 号后的数字/字母")

    analyze_button = st.button("生成诊断报告", type="primary", use_container_width=True)

    # Manual entry form — always visible when this data source is selected
    if data_source == "📝 手动输入":
        render_manual_entry_form()

    if analyze_button:
        # Manual entry mode: game_name/tag_line are optional
        if data_source == "📝 手动输入":
            if not game_name:
                game_name = "国服玩家"
            if not tag_line:
                tag_line = "CN"
        elif not game_name or not tag_line:
            st.error("请同时输入游戏ID和Tagline。")
        else:
            is_full = _has_full_access(st.session_state.user)
            if data_source == "🎮 演示数据":
                progress_bar = st.progress(0, text="正在准备演示数据...")
                status_text = st.empty()
                try:
                    status_text.info("正在生成模拟数据...")
                    progress_bar.progress(30)
                    time.sleep(0.5)
                    baseline_data = load_baseline()
                    html_report, avg_metrics, all_metrics, strengths = _generate_demo_report(game_name, tag_line, baseline_data, is_full=is_full)
                    progress_bar.progress(85)
                    status_text.info("正在生成报告...")
                    player_display_id = f"{game_name}#{tag_line}"
                    st.session_state.report_html = html_report
                    st.session_state.report_player = player_display_id
                    st.session_state.report_metrics = avg_metrics
                    st.session_state.report_strengths = strengths
                    progress_bar.progress(100)
                    status_text.success("分析完成！（演示模式）")
                    st.components.v1.html(html_report, height=1800, scrolling=True)

                    if st.session_state.user:
                        try:
                            db.save_report(st.session_state.user["id"], player_display_id, html_report)
                        except Exception:
                            pass
                except Exception as e:
                    logger.error(f"Demo mode error: {str(e)}")
                    st.error(f"❌ 演示模式出错: {str(e)}")
                    st.error(traceback.format_exc())
                finally:
                    progress_bar.empty()
                    status_text.empty()

            elif data_source == "💻 本地客户端":
                progress_bar = st.progress(0, text="正在连接本地客户端...")
                status_text = st.empty()
                try:
                    status_text.info("正在检测无畏契约客户端...")
                    progress_bar.progress(10)
                    status = local_client.get_local_status()
                    if not status["available"]:
                        if status.get("reason") == "cn_wegame_version":
                            st.warning("⚠️ " + status["message"])
                            st.info("💡 建议切换到「🎮 演示数据」模式或使用视频分析功能。")
                            st.markdown("""
                            <div style="background:#1e1e2e;padding:16px;border-radius:10px;margin:12px 0;border-left:3px solid #ff4655;">
                            <b>📌 为什么国服版不支持本地客户端？</b><br>
                            腾讯 WeGame 版无畏契约不使用 Riot Client 启动器，因此没有本地 API 接口。
                            这是国服版与国际版的架构差异，无法通过软件更新解决。
                            </div>
                            """, unsafe_allow_html=True)
                            progress_bar.empty()
                            status_text.empty()
                            st.stop()
                        raise local_client.LocalClientError(
                            status.get("message", "未检测到运行中的无畏契约客户端。请先启动游戏，然后重试。")
                        )

                    puuid = status["puuid"]
                    lockfile = status["lockfile"]
                    base_url = status["base_url"]
                    auth_headers = status["auth_headers"]

                    status_text.info("✅ 已连接客户端，正在获取授权令牌...")
                    progress_bar.progress(20)
                    tokens = local_client.get_remote_tokens(base_url, auth_headers)
                    client_version = local_client.get_client_version(base_url, auth_headers)

                    status_text.info("🔄 正在拉取比赛记录...")
                    progress_bar.progress(30)
                    match_ids = local_client.fetch_match_history(puuid, tokens, client_version, count=20)

                    if not match_ids:
                        st.warning("未找到排位赛记录。")
                    else:
                        all_metrics = []
                        all_match_extras = []
                        total_matches = len(match_ids)

                        for i, match_id in enumerate(match_ids):
                            progress_val = 30 + int((i / total_matches) * 50)
                            progress_bar.progress(progress_val, text=f"正在分析第 {i+1}/{total_matches} 场比赛...")
                            try:
                                match_data = local_client.fetch_match_details(match_id, tokens, client_version)
                                match_metrics = calculate_metrics(match_data, puuid)
                                extra = extract_match_extra(match_data, puuid)
                                all_metrics.append(match_metrics)
                                combined = {**extra, "metrics": match_metrics, "match_id": match_id}
                                all_match_extras.append(combined)
                            except Exception:
                                continue

                        if not all_metrics:
                            st.error("未能成功分析任何比赛数据。")
                        else:
                            progress_bar.progress(85, text="正在生成诊断建议...")
                            status_text.info("正在生成诊断建议...")
                            avg_metrics = aggregate_metrics(all_metrics)

                            tier = _guess_tier(avg_metrics.get("ACS", 0))
                            baseline_data = load_baseline(tier=tier)

                            diagnosis_results = diagnose(avg_metrics, baseline_data)
                            strength_results = diagnose_strengths(avg_metrics, baseline_data) if is_full else []

                            breakdown_data = calculate_map_hero_breakdown(all_match_extras)
                            map_hero_results = diagnose_map_hero_weakness(breakdown_data, global_avg_acs=avg_metrics.get("ACS", 200))

                            acs_history = []
                            kast_history = []
                            for m_extra in all_match_extras:
                                met = m_extra.get("metrics", {})
                                ts = m_extra.get("game_start_timestamp", 0)
                                acs_history.append({"value": met.get("ACS", 0), "date": str(ts)})
                                kast_history.append({"value": met.get("KAST", 0), "date": str(ts)})

                            progress_bar.progress(95, text="正在生成报告...")
                            status_text.info("正在生成报告...")
                            player_display_id = f"{game_name}#{tag_line}"
                            html_report = generate_report(
                                player_id=player_display_id,
                                player_metrics=avg_metrics,
                                diagnosis_results=diagnosis_results,
                                baseline_metrics=baseline_data,
                                acs_trend=acs_history if is_full else None,
                                kast_trend=kast_history if is_full else None,
                                map_hero_results=map_hero_results if is_full else None,
                                strength_results=strength_results,
                            )
                            st.session_state.report_html = html_report
                            st.session_state.report_player = player_display_id
                            st.session_state.report_metrics = avg_metrics
                            st.session_state.report_strengths = strength_results

                            if st.session_state.user:
                                try:
                                    db.save_report(st.session_state.user["id"], player_display_id, html_report)
                                    if st.session_state.user.get("tier") != tier:
                                        db.update_user_tier(st.session_state.user["id"], tier)
                                except Exception:
                                    pass

                            progress_bar.progress(100)
                            status_text.success("分析完成！（本地客户端）")
                            st.components.v1.html(html_report, height=1800, scrolling=True)

                except local_client.LocalClientError as e:
                    logger.error(f"Local client error: {str(e)}")
                    st.error(f"💻 本地客户端错误: {str(e)}")
                except Exception as e:
                    logger.error(f"Local client unexpected error: {str(e)}")
                    st.error(f"❌ 未知错误: {str(e)}")
                    st.error(traceback.format_exc())
                finally:
                    progress_bar.empty()
                    status_text.empty()

            elif data_source == "📝 手动输入":
                from src.cn_entry import process_entries
                ok, manual_metrics, manual_extras = process_entries(st.session_state.get("cn_entries", []))
                if not ok:
                    st.stop()
                is_full = _has_full_access(st.session_state.user)
                progress_bar = st.progress(0, text="正在分析数据...")
                status_text = st.empty()
                try:
                    status_text.info("📊 正在计算指标...")
                    progress_bar.progress(30)
                    from src.pipeline import run_analysis_pipeline
                    report = run_analysis_pipeline(
                        manual_metrics, manual_extras,
                        game_name, tag_line, is_full=is_full,
                    )
                    if report is None:
                        st.error("分析失败，请检查输入数据。")
                    else:
                        progress_bar.progress(85)
                        status_text.info("正在生成报告...")
                        player_display_id = f"{game_name}#{tag_line}"
                        st.session_state.report_html = report.html
                        st.session_state.report_player = player_display_id
                        st.session_state.report_metrics = report.avg_metrics
                        st.session_state.report_strengths = report.strengths
                        if st.session_state.user:
                            try:
                                db.save_report(st.session_state.user["id"], player_display_id, report.html)
                                if st.session_state.user.get("tier") != report.tier:
                                    db.update_user_tier(st.session_state.user["id"], report.tier)
                            except Exception:
                                pass
                        progress_bar.progress(100)
                        status_text.success(f"分析完成！（手动输入 · 共 {len(manual_metrics)} 场）")
                        st.components.v1.html(report.html, height=1800, scrolling=True)
                except Exception as e:
                    logger.error(f"Manual entry error: {str(e)}")
                    st.error(f"❌ 分析出错: {str(e)}")
                    st.error(traceback.format_exc())
                finally:
                    progress_bar.empty()
                    status_text.empty()

            else:  # Riot API (国际服)
                api_key = os.getenv("RIOT_API_KEY")
                if not _is_valid_api_key(api_key):
                    st.error("⚠️ 请先在 `.env` 文件中配置有效的 RIOT_API_KEY。")
                    st.markdown("前往 [Riot Developer Portal](https://developer.riotgames.com/) 获取 API Key")
                else:
                    api_client.RIOT_API_KEY = api_key
                    progress_bar = st.progress(0, text="正在准备...")
                    status_text = st.empty()
                    try:
                        status_text.info("正在获取玩家信息...")
                        progress_bar.progress(5)
                        puuid = get_puuid(game_name, tag_line)

                        cached = False
                        if db.is_cache_valid(puuid):
                            cached_metrics = db.get_cached_metrics(puuid)
                            if cached_metrics and len(cached_metrics) >= 5:
                                cached = True
                                status_text.info(f"✅ 使用缓存数据（共 {len(cached_metrics)} 场比赛）")
                                progress_bar.progress(30)

                        if cached:
                            all_metrics = []
                            all_match_extras = []
                            for cm in cached_metrics:
                                all_metrics.append({
                                    "KDA": cm.get("kda", 0),
                                    "ACS": cm.get("acs", 0),
                                    "KAST": cm.get("kast", 0),
                                    "headshot_percent": cm.get("headshot_percent", 0),
                                    "first_blood_rate": cm.get("first_blood_rate", 0),
                                    "econ_rating": cm.get("econ_rating", 0),
                                })
                                all_match_extras.append({
                                    "map_name": cm.get("map_name", ""),
                                    "agent_played": cm.get("agent_played", ""),
                                    "match_id": cm.get("match_id", ""),
                                    "won": cm.get("won", 0),
                                    "game_start_timestamp": cm.get("game_start_timestamp", 0),
                                    "metrics": all_metrics[-1],
                                })
                            progress_bar.progress(60)
                        else:
                            status_text.info("🔄 正在从Riot服务器拉取最新数据...")
                            match_ids = get_match_history(puuid, count=20)

                            if not match_ids:
                                st.warning("未找到排位赛记录。")
                            else:
                                all_metrics = []
                                all_match_extras = []
                                total_matches = len(match_ids)

                                for i, match_id in enumerate(match_ids):
                                    progress_val = 30 + int((i / total_matches) * 50)
                                    progress_bar.progress(progress_val, text=f"正在分析第 {i+1}/{total_matches} 场比赛...")
                                    try:
                                        match_data = get_match_details(match_id)
                                        match_metrics = calculate_metrics(match_data, puuid)
                                        extra = extract_match_extra(match_data, puuid)
                                        all_metrics.append(match_metrics)
                                        combined = {**extra, "metrics": match_metrics, "match_id": match_id}
                                        all_match_extras.append(combined)
                                    except Exception:
                                        continue

                        if not all_metrics:
                            st.error("未能成功分析任何比赛数据。")
                        else:
                            progress_bar.progress(85, text="正在生成诊断建议...")
                            status_text.info("正在生成诊断建议...")
                            avg_metrics = aggregate_metrics(all_metrics)

                            tier = _guess_tier(avg_metrics.get("ACS", 0))
                            baseline_data = load_baseline(tier=tier)

                            diagnosis_results = diagnose(avg_metrics, baseline_data)
                            strength_results = diagnose_strengths(avg_metrics, baseline_data) if is_full else []

                            breakdown_data = calculate_map_hero_breakdown(all_match_extras)
                            map_hero_results = diagnose_map_hero_weakness(breakdown_data, global_avg_acs=avg_metrics.get("ACS", 200))

                            acs_history = []
                            kast_history = []
                            for m_extra in all_match_extras:
                                met = m_extra.get("metrics", {})
                                ts = m_extra.get("game_start_timestamp", 0)
                                acs_history.append({"value": met.get("ACS", 0), "date": str(ts)})
                                kast_history.append({"value": met.get("KAST", 0), "date": str(ts)})

                            progress_bar.progress(95, text="正在生成报告...")
                            status_text.info("正在生成报告...")
                            player_display_id = f"{game_name}#{tag_line}"
                            html_report = generate_report(
                                player_id=player_display_id,
                                player_metrics=avg_metrics,
                                diagnosis_results=diagnosis_results,
                                baseline_metrics=baseline_data,
                                acs_trend=acs_history if is_full else None,
                                kast_trend=kast_history if is_full else None,
                                map_hero_results=map_hero_results if is_full else None,
                                strength_results=strength_results,
                            )
                            st.session_state.report_html = html_report
                            st.session_state.report_player = player_display_id
                            st.session_state.report_metrics = avg_metrics
                            st.session_state.report_strengths = strength_results

                            if not cached:
                                try:
                                    db.save_match_records(puuid, game_name, tag_line, all_match_extras)
                                except Exception:
                                    pass

                            if st.session_state.user:
                                try:
                                    db.save_report(st.session_state.user["id"], player_display_id, html_report)
                                    if st.session_state.user.get("tier") != tier:
                                        db.update_user_tier(st.session_state.user["id"], tier)
                                except Exception:
                                    pass

                            progress_bar.progress(100)
                            status_text.success(f"分析完成！检测段位: {tier}")
                            st.components.v1.html(html_report, height=1800, scrolling=True)

                    except PermissionError as e:
                        logger.error(f"API key error: {str(e)}")
                        st.error(f"🔑 API密钥错误: {str(e)}")
                    except ValueError as e:
                        logger.error(f"Player not found: {str(e)}")
                        st.error(f"👤 玩家未找到: {str(e)}")
                    except RuntimeError as e:
                        logger.error(f"API error: {str(e)}")
                        st.error(f"🌐 API错误: {str(e)}")
                    except Exception as e:
                        logger.error(f"Unexpected error: {str(e)}")
                        st.error(f"❌ 未知错误: {str(e)}")
                        st.error(traceback.format_exc())
                    finally:
                        progress_bar.empty()
                        status_text.empty()

    from src.upsell import render_upsell_banner, render_delivery_tools
    render_upsell_banner()
    render_delivery_tools()

st.markdown("---")
st.markdown(
    '<div class="footer">⚠️ 本产品未经Riot Games认可。ValCoach是一个独立的第三方分析工具。</div>',
    unsafe_allow_html=True
)

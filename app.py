import os
import sys
import traceback
import random
import time

import streamlit as st
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

import src.api_client as api_client
from src.api_client import get_puuid, get_match_history, get_match_details
from src.metrics import calculate_metrics, aggregate_metrics, extract_match_extra, calculate_map_hero_breakdown
from src.baseline import load_baseline
from src.diagnosis import diagnose, diagnose_map_hero_weakness, diagnose_strengths
from src.report_generator import generate_report, build_share_card, generate_pdf_report
import src.database as db
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
    layout="centered",
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
            pass

st.markdown("""
<meta name="description" content="ValCoach - 《无畏契约》AI 赛后诊断工具。分析你的排位赛数据，找出短板，提升段位。">
<meta property="og:title" content="ValCoach - 《无畏契约》AI 教练">
<meta property="og:description" content="AI驱动的无畏契约赛后分析工具，6项核心指标诊断，雷达图可视化报告。">
""", unsafe_allow_html=True)

st.markdown("""
<style>
    .main-header { text-align: center; padding: 2rem 0; }
    .main-header h1 { font-size: 3rem; background: linear-gradient(90deg, #ff4655, #ff6b81); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem; }
    .main-header p { font-size: 1.1rem; color: #888; }
    .stButton > button { background: linear-gradient(90deg, #ff4655, #e63946); color: white; border: none; font-size: 1.1rem; padding: 0.5rem 2rem; width: 100%; }
    .stButton > button:hover { background: linear-gradient(90deg, #e63946, #c5303c); }
    .product-card { background: rgba(255,255,255,0.05); border-radius: 12px; padding: 24px; margin: 12px 0; border: 1px solid rgba(255,255,255,0.1); }
    .product-card h3 { color: #ff4655; margin-bottom: 8px; }
    .product-card p { color: #aaa; font-size: 14px; }
    .footer { text-align: center; color: #666; font-size: 0.85rem; padding: 2rem 0; }
    .step-card { background: rgba(255,255,255,0.03); border-radius: 8px; padding: 16px; text-align: center; }
    .step-card h4 { color: #ff4655; font-size: 1.5rem; }
    .step-card p { color: #ccc; font-size: 0.9rem; }
    .premium-lock { background: rgba(255,70,85,0.08); border-radius: 12px; padding: 30px; text-align: center; margin: 20px 0; border: 1px dashed #ff4655; }
    .feature-list { list-style: none; padding: 0; }
    .feature-list li { padding: 8px 0; color: #ccc; font-size: 14px; }
</style>
""", unsafe_allow_html=True)

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

st.sidebar.markdown("## 🔐 账户")

if st.session_state.user:
    tier_label = st.session_state.user.get("tier", "免费")
    display = f"欢迎, {st.session_state.user['email']}"
    if tier_label == "admin":
        display += " 👑"
    st.sidebar.success(display)
    col_a, col_b = st.sidebar.columns(2)
    if col_a.button("📊 分析"):
        st.session_state.page = "analysis"
    if col_b.button("📋 历史"):
        st.session_state.page = "history"
    if st.sidebar.button("🚪 退出登录"):
        st.session_state.user = None
        st.session_state.page = "analysis"
        _rerun()
else:
    with st.sidebar.expander("登录 / 注册", expanded=True):
        tab1, tab2 = st.tabs(["登录", "注册"])
        with tab1:
            login_email = st.text_input("邮箱", key="login_email")
            login_pwd = st.text_input("密码", type="password", key="login_pwd")
            if st.button("登录", key="login_btn"):
                user = db.login_user(login_email, login_pwd)
                if user:
                    st.session_state.user = user
                    logger.info(f"User logged in: {login_email}")
                    st.success("登录成功")
                    _rerun()
                else:
                    st.error("邮箱或密码错误")
        with tab2:
            reg_email = st.text_input("邮箱", key="reg_email")
            reg_pwd = st.text_input("密码", type="password", key="reg_pwd")
            if st.button("注册", key="reg_btn"):
                user_id = db.register_user(reg_email, reg_pwd)
                if user_id:
                    logger.info(f"User registered: {reg_email}")
                    st.success("注册成功，请登录")
                else:
                    st.error("该邮箱已被注册")

demo_mode = st.sidebar.checkbox("🎮 使用演示数据（跳过API）", value=False, key="demo_mode_global",
                                help="启用后使用模拟数据展示报告效果，无需配置API密钥")

if st.session_state.user and st.session_state.user.get("email") in ADMIN_EMAILS:
    with st.sidebar.expander("🛠 管理员工具", expanded=False):
        st.caption("仅管理员可见")
        if st.button("🔄 更新基准数据"):
            try:
                from scripts.update_baseline import update_baseline
                api_key = os.getenv("RIOT_API_KEY")
                if api_key and api_key != "RGAPI-你的密钥":
                    api_client.RIOT_API_KEY = api_key
                    with st.spinner("正在从Riot API拉取高分玩家数据..."):
                        update_baseline()
                    st.success("基准数据已更新！")
                else:
                    st.error("请先配置有效的 RIOT_API_KEY")
            except Exception as e:
                st.error(f"更新失败: {str(e)}")

st.sidebar.markdown("---")
st.sidebar.markdown("### ℹ️ 关于 ValCoach")
st.sidebar.markdown("""
ValCoach 是一款基于 AI 的《无畏契约》赛后诊断工具。

- 📊 6项核心指标分析
- 🎯 智能短板诊断
- 📈 历史趋势追踪
- 🗺️ 地图/英雄专项分析
""")

if not st.session_state.user:
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 👑 管理员体验账号")
    st.sidebar.info("邮箱: `admin@valcoach.gg`\n密码: `admin123`")

if st.session_state.page == "history" and st.session_state.user:
    st.markdown("# 📋 我的历史报告")
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

    st.markdown("""
    <div style="text-align:center; margin: 12px 0; padding: 12px; background: rgba(255,70,85,0.05); border-radius: 8px;">
        <p style="color:#aaa; font-size:14px;">
            💡 首次使用？试试勾选侧边栏的 <b style="color:#ff4655;">🎮 演示模式</b>，或输入你的ID开始分析
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown("""
        <div class="product-card">
            <h3>🎯 AI 驱动的赛后诊断</h3>
            <p>自动拉取你最近20场排位赛数据，与同段位玩家基准进行6维对比，精准定位你的短板，提供可执行的训练建议。</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 📖 三步使用指南")
        guide_cols = st.columns(3)
        steps = [
            ("1️⃣", "输入ID", "输入你的游戏ID和Tagline"),
            ("2️⃣", "自动分析", "系统拉取最近20场排位赛数据"),
            ("3️⃣", "获取报告", "一键生成诊断报告和改进建议"),
        ]
        for col, (num, title, desc) in zip(guide_cols, steps):
            with col:
                st.markdown(f"""
                <div class="step-card">
                    <h4>{num}</h4>
                    <p style="font-weight:600; color:#e0e0e0;">{title}</p>
                    <p>{desc}</p>
                </div>
                """, unsafe_allow_html=True)

        cols = st.columns(3)
        features = [
            ("📊", "全面指标", "KDA/ACS/KAST/爆头率/首杀率/经济评分"),
            ("🧠", "智能诊断", "AI分析短板，给出针对性训练建议"),
            ("📈", "趋势追踪", "查看ACS和KAST的历史变化趋势"),
        ]
        for col, (icon, title, desc) in zip(cols, features):
            with col:
                st.markdown(f"""
                <div class="product-card" style="text-align:center;">
                    <h3>{icon}</h3>
                    <p style="color:#e0e0e0;font-weight:600;">{title}</p>
                    <p>{desc}</p>
                </div>
                """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        game_name = st.text_input("游戏ID", placeholder="例如: Player1", help="你的 Riot 游戏 ID（不含 Tagline）")
    with col2:
        tag_line = st.text_input("Tagline", placeholder="例如: 1234", help="你的 Riot ID 后的 # 号后的数字/字母")

    analyze_button = st.button("生成诊断报告", type="primary", use_container_width=True)

    if analyze_button:
        if not game_name or not tag_line:
            st.error("请同时输入游戏ID和Tagline。")
        else:
            is_full = _has_full_access(st.session_state.user)
            if demo_mode:
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
            else:
                api_key = os.getenv("RIOT_API_KEY")
                if not api_key or api_key == "RGAPI-你的密钥":
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

    if not _has_full_access(st.session_state.user) and st.session_state.report_html:
        st.markdown("""
        <div class="premium-lock">
            <h3 style="color:#ff4655;">🔓 解锁完整报告</h3>
            <p style="color:#ccc; margin: 16px 0;">付费后可解锁以下所有功能：</p>
            <ul class="feature-list">
                <li>🧠 完整短板诊断（含差距百分比和改进建议）</li>
                <li>💚 正向优势反馈（表扬文案）</li>
                <li>📈 ACS/KAST 历史趋势图</li>
                <li>🗺️ 地图/英雄专项分析</li>
                <li>📄 PDF 报告下载</li>
                <li>📤 分享卡片生成</li>
                <li>📧 邮件自动发送</li>
            </ul>
            <div style="margin-top: 20px; font-size: 24px; font-weight: bold; color: #ff4655;">¥9.9 / 份</div>
        </div>
        """, unsafe_allow_html=True)
        if st.session_state.user and PAYMENT_AVAILABLE:
            if st.button("💳 立即支付 ¥9.9 解锁", key="pay_btn"):
                try:
                    success_url = f"{os.getenv('BASE_URL', 'http://localhost:8501')}/"
                    cancel_url = f"{os.getenv('BASE_URL', 'http://localhost:8501')}/"
                    checkout_url = create_checkout_session(st.session_state.user["id"], success_url, cancel_url)
                    if checkout_url:
                        st.markdown(f"[点击前往支付]({checkout_url})")
                except Exception as e:
                    logger.error(f"Payment error: {str(e)}")
                    st.error(f"支付创建失败: {str(e)}")
        elif not st.session_state.user:
            st.info("请先登录后再支付")

    if _has_full_access(st.session_state.user) and st.session_state.report_html:
        st.markdown("---")
        st.markdown("### 📤 交付工具")
        action_cols = st.columns(3)

        with action_cols[0]:
            pdf_path = generate_pdf_report(st.session_state.report_html, st.session_state.report_player or "report")
            if pdf_path:
                with open(pdf_path, "rb") as f:
                    st.download_button("📥 下载 PDF", data=f, file_name=os.path.basename(pdf_path), mime="application/pdf")

        with action_cols[1]:
            if st.session_state.report_metrics and st.session_state.report_strengths:
                share_path = build_share_card(
                    st.session_state.report_player or "Player",
                    st.session_state.report_metrics,
                    st.session_state.report_strengths,
                )
                if share_path:
                    with open(share_path, "rb") as f:
                        st.download_button("📤 分享卡片", data=f, file_name=os.path.basename(share_path), mime="image/png")

        with action_cols[2]:
            if st.session_state.user and MAILER_AVAILABLE:
                user_email = st.session_state.user.get("email", "")
                if st.button("📧 发送到邮箱"):
                    try:
                        send_report_email(user_email, st.session_state.report_html)
                        st.success(f"报告已发送到 {user_email}")
                    except Exception as e:
                        st.error(f"发送失败: {str(e)}")

st.markdown("---")
st.markdown(
    '<div class="footer">⚠️ 本产品未经Riot Games认可。ValCoach是一个独立的第三方分析工具。</div>',
    unsafe_allow_html=True
)

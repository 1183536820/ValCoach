import os
import sys
import traceback
import random
import time

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

import src.api_client as api_client
from src.api_client import get_puuid, get_match_history, get_match_details
from src.metrics import calculate_metrics, aggregate_metrics, extract_match_extra, calculate_map_hero_breakdown
from src.baseline import load_baseline
from src.diagnosis import diagnose, diagnose_map_hero_weakness
from src.report_generator import generate_report
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


def _generate_demo_report(game_name, tag_line, baseline_data):
    all_metrics = _get_demo_metrics()
    avg_metrics = aggregate_metrics(all_metrics)
    diagnosis_results = diagnose(avg_metrics, baseline_data)

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
        acs_trend=demo_history,
        kast_trend=demo_kast,
        map_hero_results=map_hero_results,
    )
    return html_report, avg_metrics, all_metrics


db.init_db()

st.set_page_config(
    page_title="ValCoach - 《无畏契约》AI 教练",
    page_icon="🎯",
    layout="wide",
)

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
    .auth-form { background: rgba(255,255,255,0.03); border-radius: 8px; padding: 16px; margin: 8px 0; }
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

st.sidebar.markdown("## 🔐 账户")

if st.session_state.user:
    st.sidebar.success(f"欢迎, {st.session_state.user['email']}")
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
                    st.success("注册成功，请登录")
                else:
                    st.error("该邮箱已被注册")

if st.sidebar.checkbox("🎮 使用演示数据（跳过API）", value=False, key="demo_mode_global",
                        help="启用后使用模拟数据展示报告效果，无需配置API密钥"):
    pass

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

    with st.container():
        st.markdown("""
        <div class="product-card">
            <h3>🎯 AI 驱动的赛后诊断</h3>
            <p>自动拉取你最近20场排位赛数据，与高分玩家基准进行6维对比，精准定位你的短板，提供可执行的训练建议。</p>
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
    paid_user = st.session_state.user and db.has_user_paid(st.session_state.user["id"])

    if analyze_button:
        if not game_name or not tag_line:
            st.error("请同时输入游戏ID和Tagline。")
        else:
            demo_mode = st.session_state.get("demo_mode_global", False)
            if demo_mode:
                progress_bar = st.progress(0, text="正在准备演示数据...")
                status_text = st.empty()
                try:
                    status_text.info("正在生成模拟数据...")
                    progress_bar.progress(30)
                    time.sleep(0.5)
                    baseline_data = load_baseline()
                    html_report, avg_metrics, all_metrics = _generate_demo_report(game_name, tag_line, baseline_data)
                    progress_bar.progress(85)
                    status_text.info("正在生成报告...")
                    player_display_id = f"{game_name}#{tag_line}"
                    st.session_state.report_html = html_report
                    st.session_state.report_player = player_display_id
                    progress_bar.progress(100)
                    status_text.success("分析完成！（演示模式）")
                    st.components.v1.html(html_report, height=1800, scrolling=True)
                except Exception as e:
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
                        progress_bar.progress(10)
                        puuid = get_puuid(game_name, tag_line)

                        status_text.info("正在拉取比赛历史...")
                        progress_bar.progress(25)
                        match_ids = get_match_history(puuid, count=20)

                        if not match_ids:
                            st.warning("未找到排位赛记录。")
                        else:
                            status_text.info(f"获取到 {len(match_ids)} 场比赛，正在分析...")
                            progress_bar.progress(40)
                            all_metrics = []
                            all_match_extras = []
                            total_matches = len(match_ids)

                            for i, match_id in enumerate(match_ids):
                                progress_val = 40 + int((i / total_matches) * 40)
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
                                baseline_data = load_baseline()
                                diagnosis_results = diagnose(avg_metrics, baseline_data)

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
                                    acs_trend=acs_history,
                                    kast_trend=kast_history,
                                    map_hero_results=map_hero_results,
                                )
                                st.session_state.report_html = html_report
                                st.session_state.report_player = player_display_id

                                try:
                                    db.save_match_records(puuid, game_name, tag_line, all_match_extras)
                                except Exception:
                                    pass

                                if st.session_state.user:
                                    try:
                                        db.save_report(st.session_state.user["id"], player_display_id, html_report)
                                    except Exception:
                                        pass

                                progress_bar.progress(100)
                                status_text.success("分析完成！")
                                st.components.v1.html(html_report, height=1800, scrolling=True)

                    except PermissionError as e:
                        st.error(f"🔑 API密钥错误: {str(e)}")
                    except ValueError as e:
                        st.error(f"👤 玩家未找到: {str(e)}")
                    except RuntimeError as e:
                        st.error(f"🌐 API错误: {str(e)}")
                    except Exception as e:
                        st.error(f"❌ 未知错误: {str(e)}")
                        st.error(traceback.format_exc())
                    finally:
                        progress_bar.empty()
                        status_text.empty()

    if st.session_state.report_html and not paid_user and st.session_state.user and PAYMENT_AVAILABLE:
        st.markdown("---")
        st.markdown("### 🔓 解锁完整报告")
        st.info("注册用户可查看完整报告、历史记录和邮箱发送功能。")
        if st.button("💳 支付 ¥9.9 获取完整报告"):
            try:
                success_url = f"{os.getenv('BASE_URL', 'http://localhost:8501')}/"
                cancel_url = f"{os.getenv('BASE_URL', 'http://localhost:8501')}/"
                checkout_url = create_checkout_session(st.session_state.user["id"], success_url, cancel_url)
                if checkout_url:
                    st.markdown(f"[点击前往支付]({checkout_url})")
            except Exception as e:
                st.error(f"支付创建失败: {str(e)}")

st.markdown("---")
st.markdown(
    '<div class="footer">⚠️ 本产品未经Riot Games认可。ValCoach是一个独立的第三方分析工具。</div>',
    unsafe_allow_html=True
)

# =============================================================================
# 功能测试 Checklist (注释)
# =============================================================================
# [ ] 演示模式: 勾选侧边栏"使用演示数据"，输入任意ID/Tagline，生成含雷达图+趋势图+诊断+地图英雄的报告
# [ ] 用户注册: 侧边栏输入邮箱和密码注册，验证注册后能登录
# [ ] 用户登录: 用已注册账号登录，侧边栏显示欢迎信息
# [ ] 历史报告: 登录状态下生成报告，切换到"历史"页面查看
# [ ] 数据库持久化: 检查 data/player_history.db 文件已生成并包含数据
# [ ] 真实API: 配置 RIOT_API_KEY 后输入真实玩家ID，生成真实数据报告
# [ ] 管理员工具: 将邮箱加入 ADMIN_EMAILS 环境变量，出现管理员面板
# [ ] 基准更新脚本: python scripts/update_baseline.py 执行无误
# [ ] 支付: 配置 Stripe 密钥后点击支付按钮跳转
# [ ] 邮件: 配置 SMTP 环境变量后，历史报告中可触发邮件发送
# [ ] .env配置: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, STRIPE_SECRET_KEY, STRIPE_PRICE_ID, ADMIN_EMAILS, BASE_URL
# =============================================================================

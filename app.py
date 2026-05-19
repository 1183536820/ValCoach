import os
import sys
import traceback

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Ensure src is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api_client import get_puuid, get_match_history, get_match_details
import src.api_client as api_client
from src.metrics import calculate_metrics, aggregate_metrics
from src.baseline import load_baseline
from src.diagnosis import diagnose
from src.report_generator import generate_report


# === DEMO MODE START ===
def _get_demo_metrics():
    import random
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
# === DEMO MODE END ===


st.set_page_config(
    page_title="ValCoach - AI教练",
    page_icon="🎯",
    layout="wide",
)

# === DEMO MODE START ===
demo_mode = st.sidebar.checkbox("🎮 使用演示数据（跳过API）", value=False,
                                help="启用后使用模拟数据展示报告效果，无需配置API密钥")
# === DEMO MODE END ===

st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
    }
    .main-header h1 {
        font-size: 3rem;
        background: linear-gradient(90deg, #ff4655, #ff6b81);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .main-header p {
        font-size: 1.1rem;
        color: #888;
    }
    .stButton > button {
        background: linear-gradient(90deg, #ff4655, #e63946);
        color: white;
        border: none;
        font-size: 1.1rem;
        padding: 0.5rem 2rem;
        width: 100%;
    }
    .stButton > button:hover {
        background: linear-gradient(90deg, #e63946, #c5303c);
    }
    .footer {
        text-align: center;
        color: #666;
        font-size: 0.85rem;
        padding: 2rem 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">', unsafe_allow_html=True)
st.markdown("# ValCoach - 《无畏契约》AI 教练")
st.markdown("<p>输入你的游戏ID和Tagline，获取专属赛后诊断报告</p>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    game_name = st.text_input(
        "游戏ID",
        placeholder="例如: Player1",
        help="你的 Riot 游戏 ID（不含 Tagline）"
    )

with col2:
    tag_line = st.text_input(
        "Tagline",
        placeholder="例如: 1234",
        help="你的 Riot ID 后的 # 号后的数字/字母"
    )

analyze_button = st.button("生成诊断报告", type="primary", use_container_width=True)

if analyze_button:
    if not game_name or not tag_line:
        st.error("请同时输入游戏ID和Tagline。")
    elif demo_mode:
        # === DEMO MODE START ===
        progress_bar = st.progress(0, text="正在准备演示数据...")
        status_text = st.empty()

        try:
            status_text.info("正在生成模拟数据...")
            progress_bar.progress(30, text="正在生成模拟数据...")
            import time
            time.sleep(0.5)

            all_metrics = _get_demo_metrics()

            progress_bar.progress(60, text="正在计算指标...")
            status_text.info("正在计算指标...")
            time.sleep(0.3)

            avg_metrics = aggregate_metrics(all_metrics)
            baseline_data = load_baseline()
            diagnosis_results = diagnose(avg_metrics, baseline_data)

            progress_bar.progress(85, text="正在生成报告...")
            status_text.info("正在生成报告...")

            player_display_id = f"{game_name}#{tag_line}（演示数据）"
            html_report = generate_report(
                player_id=player_display_id,
                player_metrics=avg_metrics,
                diagnosis_results=diagnosis_results,
                baseline_metrics=baseline_data,
            )

            progress_bar.progress(100, text="完成！")
            status_text.success("分析完成！（演示模式）")

            st.components.v1.html(html_report, height=1800, scrolling=True)
        except Exception as e:
            st.error(f"❌ 演示模式出错: {str(e)}")
            st.error(traceback.format_exc())
        finally:
            progress_bar.empty()
            status_text.empty()
        # === DEMO MODE END ===
    else:
        api_key = os.getenv("RIOT_API_KEY")
        if not api_key or api_key == "RGAPI-你的密钥":
            st.error("⚠️ 请先在 `.env` 文件中配置有效的 RIOT_API_KEY。")
            st.markdown("""
            1. 前往 [Riot Developer Portal](https://developer.riotgames.com/) 注册并获取 API Key
            2. 将 `.env` 文件中的 `RIOT_API_KEY` 替换为你的密钥
            """)
        else:
            api_client.RIOT_API_KEY = api_key

            progress_bar = st.progress(0, text="正在准备...")
            status_text = st.empty()

            try:
                status_text.info("正在获取玩家信息...")
                progress_bar.progress(10, text="正在获取玩家信息...")

                puuid = get_puuid(game_name, tag_line)

                status_text.info("正在拉取比赛历史...")
                progress_bar.progress(25, text="正在拉取比赛历史...")

                match_ids = get_match_history(puuid, count=20)

                if not match_ids:
                    st.warning("未找到排位赛记录，请检查该账号是否进行过排位赛。")
                else:
                    status_text.info(f"获取到 {len(match_ids)} 场比赛，正在分析...")
                    progress_bar.progress(40, text="正在获取比赛详情...")

                    all_metrics = []
                    total_matches = len(match_ids)

                    for i, match_id in enumerate(match_ids):
                        progress_val = 40 + int((i / total_matches) * 40)
                        progress_bar.progress(
                            progress_val,
                            text=f"正在分析第 {i+1}/{total_matches} 场比赛..."
                        )

                        try:
                            match_data = get_match_details(match_id)
                            match_metrics = calculate_metrics(match_data, puuid)
                            all_metrics.append(match_metrics)
                        except Exception as e:
                            st.warning(f"第 {i+1} 场比赛分析失败: {str(e)[:50]}...")
                            continue

                    if not all_metrics:
                        st.error("未能成功分析任何比赛数据。")
                    else:
                        progress_bar.progress(85, text="正在生成诊断建议...")
                        status_text.info("正在生成诊断建议...")

                        avg_metrics = aggregate_metrics(all_metrics)
                        baseline_data = load_baseline()
                        diagnosis_results = diagnose(avg_metrics, baseline_data)

                        progress_bar.progress(95, text="正在生成报告...")
                        status_text.info("正在生成报告...")

                        player_display_id = f"{game_name}#{tag_line}"
                        html_report = generate_report(
                            player_id=player_display_id,
                            player_metrics=avg_metrics,
                            diagnosis_results=diagnosis_results,
                            baseline_metrics=baseline_data,
                        )

                        progress_bar.progress(100, text="完成！")
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

st.markdown("---")
st.markdown(
    '<div class="footer">⚠️ 本产品未经Riot Games认可。ValCoach是一个独立的第三方分析工具。</div>',
    unsafe_allow_html=True
)

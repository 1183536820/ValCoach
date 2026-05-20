"""Sidebar UI: auth, navigation, admin tools, about section."""

import streamlit as st

from src.database import login_user, register_user, get_user_reports
from src.validation import validate_email, validate_password
from src.logger import get_logger

logger = get_logger()


def render_sidebar(admin_emails: list, is_valid_api_key_fn=None):
    """Render the full sidebar: account, nav, data source, admin, about."""
    st.sidebar.markdown("""<i class="fas fa-user-lock" style="margin-right:4px;"></i> **账户**""", unsafe_allow_html=True)

    if st.session_state.user:
        _render_user_panel()
    else:
        _render_auth_panel()

    st.sidebar.markdown("---")
    if st.sidebar.button("🎥 视频分析", use_container_width=True):
        st.session_state.page = "video_analysis"

    _render_data_source()
    _render_admin_tools(admin_emails, is_valid_api_key_fn)
    _render_about_section()


def _render_user_panel():
    """Logged-in user info + nav buttons."""
    user = st.session_state.user
    tier_label = user.get("tier", "免费")
    display = f"<i class='fas fa-user' style='margin-right:4px;'></i> {user['email']}"
    if tier_label == "admin":
        display += " <i class='fas fa-crown' style='color:#ffd700;'></i>"
    st.sidebar.markdown(
        f"<div style='padding:10px 14px;background:rgba(76,175,80,0.08);"
        f"border-radius:10px;border-left:3px solid #4caf50;color:#a5d6a7;"
        f"font-size:0.85rem;'>{display}<br>"
        f"<span style='color:#888;font-size:0.75rem;'>{tier_label.upper()}</span></div>",
        unsafe_allow_html=True,
    )
    col_a, col_b = st.sidebar.columns(2)
    if col_a.button("📊 分析"):
        st.session_state.page = "analysis"
    if col_b.button("📋 历史"):
        st.session_state.page = "history"
    if st.sidebar.button("🚪 退出登录"):
        st.session_state.user = None
        st.session_state.page = "analysis"
        st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()


def _render_auth_panel():
    """Login / register expander."""
    with st.sidebar.expander("登录 / 注册", expanded=True):
        tab1, tab2 = st.tabs(["登录", "注册"])
        with tab1:
            login_email = st.text_input("邮箱", key="login_email")
            login_pwd = st.text_input("密码", type="password", key="login_pwd")
            if st.button("登录", key="login_btn"):
                err = validate_email(login_email) or validate_password(login_pwd)
                if err:
                    st.error(err)
                else:
                    user = login_user(login_email, login_pwd)
                    if user:
                        st.session_state.user = user
                        st.success("登录成功")
                        st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
                    else:
                        st.error("邮箱或密码错误")
        with tab2:
            reg_email = st.text_input("邮箱", key="reg_email")
            reg_pwd = st.text_input("密码", type="password", key="reg_pwd")
            if st.button("注册", key="reg_btn"):
                err = validate_email(reg_email) or validate_password(reg_pwd)
                if err:
                    st.error(err)
                else:
                    user_id = register_user(reg_email, reg_pwd)
                    if user_id:
                        st.success("注册成功，请登录")
                    else:
                        st.error("该邮箱已被注册")


def _render_data_source():
    """Data source selector."""
    data_source = st.sidebar.radio(
        "📡 数据来源",
        options=["🌐 Riot API（国际服）", "💻 本地客户端", "📝 手动输入", "📸 截图识别", "🎮 演示数据"],
        index=0,
        key="data_source",
        help="国际服 Riot API 需要 API Key；本地客户端仅支持国际服 Riot Client 版；手动输入适合从生涯页面填数据；截图识别用 OCR 自动提取结算页面数据",
    )
    st.session_state.demo_mode = (data_source == "🎮 演示数据")
    st.session_state.local_mode = (data_source == "💻 本地客户端")


def _render_admin_tools(admin_emails: list, is_valid_api_key_fn=None):
    """Admin-only tools expander."""
    user = st.session_state.user
    if not user or user.get("email") not in admin_emails:
        return
    with st.sidebar.expander("🛠 管理员工具", expanded=False):
        st.caption("仅管理员可见")
        if st.button("🔄 更新基准数据"):
            try:
                from scripts.update_baseline import update_baseline
                import os
                from src import api_client
                api_key = os.getenv("RIOT_API_KEY")
                if is_valid_api_key_fn and is_valid_api_key_fn(api_key):
                    api_client.RIOT_API_KEY = api_key
                    with st.spinner("正在从Riot API拉取高分玩家数据..."):
                        update_baseline()
                    st.success("基准数据已更新！")
                else:
                    st.error("请先配置有效的 RIOT_API_KEY")
            except Exception as e:
                st.error(f"更新失败: {str(e)}")


def _render_about_section():
    """About ValCoach section."""
    st.sidebar.markdown("---")
    st.sidebar.markdown("### <i class='fas fa-info-circle' style='margin-right:4px;'></i> 关于 ValCoach", unsafe_allow_html=True)
    st.sidebar.markdown("""
    ValCoach 是一款基于 AI 的《无畏契约》赛后诊断工具。

    - 📊 6项核心指标分析
    - 🎯 智能短板诊断
    - 📈 历史趋势追踪
    - 🗺️ 地图/英雄专项分析
    """)

    if not st.session_state.user:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### <i class='fas fa-crown' style='margin-right:4px;color:#ffd700;'></i> 管理员体验账号", unsafe_allow_html=True)
        st.sidebar.info("邮箱: `admin@valcoach.gg`\n密码: `admin123`")

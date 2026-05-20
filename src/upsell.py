"""Premium upsell banner and delivery tools (PDF / email / share card)."""

import streamlit as st
import streamlit.components.v1 as components

from src.logger import get_logger

logger = get_logger()


def render_upsell_banner():
    """Render the premium unlock banner for free-tier users."""
    if not st.session_state.get("report_html"):
        return
    if _has_full_access(st.session_state.user):
        return

    st.markdown("""
    <div class="premium-lock">
        <h3><i class="fas fa-crown" style="margin-right:8px;"></i>解锁完整报告</h3>
        <p style="color:#ccc; margin: 16px 0;">付费后可解锁以下所有功能：</p>
        <ul class="feature-list">
            <li><i class="fas fa-brain" style="width:20px;"></i> 完整短板诊断（含差距百分比和改进建议）</li>
            <li><i class="fas fa-thumbs-up" style="width:20px;"></i> 正向优势反馈（表扬文案）</li>
            <li><i class="fas fa-chart-line" style="width:20px;"></i> ACS/KAST 历史趋势图</li>
            <li><i class="fas fa-map" style="width:20px;"></i> 地图/英雄专项分析</li>
            <li><i class="fas fa-file-pdf" style="width:20px;"></i> PDF 报告下载</li>
            <li><i class="fas fa-share-alt" style="width:20px;"></i> 分享卡片生成</li>
            <li><i class="fas fa-envelope" style="width:20px;"></i> 邮件自动发送</li>
        </ul>
        <div class="price">¥9.9 <span style="font-size:1rem;font-weight:400;color:#999;">/ 份</span></div>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.user and _is_payment_available():
        render_payment_button()


def render_delivery_tools():
    """Render PDF download, share card, and email buttons for full-access users."""
    if not _has_full_access(st.session_state.user):
        return
    if not st.session_state.get("report_html"):
        return

    st.markdown("---")
    st.markdown("### <i class='fas fa-download' style='margin-right:4px;'></i> 报告交付", unsafe_allow_html=True)

    col_pdf, col_share, col_mail = st.columns(3)

    with col_pdf:
        if st.button("📄 下载 PDF", use_container_width=True):
            with st.spinner("正在生成 PDF..."):
                try:
                    from src.report_generator import generate_pdf_report
                    player_id = st.session_state.get("report_player", "player")
                    pdf_path = generate_pdf_report(st.session_state.report_html, player_id)
                    if pdf_path:
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                label="📥 点击下载",
                                data=f,
                                file_name=f"{player_id}_report.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                            )
                    else:
                        st.error("PDF 生成失败")
                except Exception as e:
                    logger.error(f"PDF generation error: {e}")
                    st.error("PDF 生成失败（需要安装 weasyprint）")

    with col_share:
        if st.button("🖼️ 分享卡片", use_container_width=True):
            with st.spinner("正在生成分享卡片..."):
                try:
                    from src.report_generator import build_share_card
                    player_id = st.session_state.get("report_player", "player")
                    metrics = st.session_state.get("report_metrics", {})
                    strengths = st.session_state.get("report_strengths", [])
                    card_path = build_share_card(player_id, metrics, strengths)
                    if card_path:
                        with open(card_path, "rb") as f:
                            st.download_button(
                                label="📥 下载分享卡片",
                                data=f,
                                file_name=f"{player_id}_share.png",
                                mime="image/png",
                                use_container_width=True,
                            )
                    else:
                        st.info("⚠️ 暂无优势数据，无法生成分享卡片")
                except Exception as e:
                    logger.error(f"Share card error: {e}")
                    st.error("分享卡片生成失败")

    with col_mail:
        if st.button("📧 邮件发送", use_container_width=True):
            _render_mail_dialog()


def render_payment_button():
    """Render the Stripe payment button."""
    try:
        from src.payment import create_checkout_session
    except Exception:
        return
    try:
        session = create_checkout_session(st.session_state.user["id"])
        if session and session.get("url"):
            st.markdown(f"""
            <a href="{session['url']}" target="_blank">
                <button style="background: linear-gradient(135deg, #ff4655, #e63946);
                    color: white; border: none; font-size: 1.1rem; font-weight: 600;
                    padding: 12px 32px; border-radius: 8px; cursor: pointer;
                    box-shadow: 0 4px 15px rgba(255,70,85,0.3);
                    transition: all 0.3s;">
                    💳 立即支付 ¥9.9
                </button>
            </a>
            """, unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"Payment error: {e}")
        st.error("支付系统暂不可用")


def _render_mail_dialog():
    """Simple email input for sending report."""
    with st.container():
        recipient = st.text_input("收件邮箱", key="mail_recipient",
                                  placeholder="your@email.com")
        if st.button("发送", key="send_mail_btn"):
            if not recipient or "@" not in recipient:
                st.error("请输入有效的邮箱地址")
            else:
                try:
                    from src.mailer import send_report_email
                    player_id = st.session_state.get("report_player", "player")
                    success = send_report_email(
                        recipient,
                        player_id,
                        st.session_state.report_html,
                    )
                    if success:
                        st.success(f"报告已发送至 {recipient}")
                    else:
                        st.error("邮件发送失败，请检查 SMTP 配置")
                except Exception as e:
                    logger.error(f"Mail error: {e}")
                    st.error("邮件发送失败")


def _has_full_access(user) -> bool:
    if not user:
        return False
    if user.get("tier") == "admin":
        return True
    try:
        from src.database import has_user_paid
        return has_user_paid(user["id"])
    except Exception:
        return user.get("tier") in ("Gold", "Platinum", "Diamond", "Ascendant", "Immortal", "Radiant")


def _is_payment_available() -> bool:
    try:
        from src.payment import create_checkout_session
        return create_checkout_session is not None
    except Exception:
        return False

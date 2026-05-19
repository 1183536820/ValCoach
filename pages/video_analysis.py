"""Streamlit page for video analysis — upload MP4 or live capture, show results."""

import os
import sys
import time
import tempfile
import traceback

import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.video_analyzer import VideoAnalyzer
from src.video_report import generate_video_report
from src.video_diagnosis import diagnose_video
from src.logger import get_logger

logger = get_logger()


def _run_analysis(video_path: str) -> str:
    """Run full video analysis pipeline and return HTML report."""
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    bar = progress_placeholder.progress(0)

    def on_progress(stage: str, pct: float):
        status_texts = {
            "performance": "正在分析帧率与性能...",
            "scene": "正在检测回合边界...",
            "crosshair": "正在检测开枪与反应时间...",
            "done": "分析完成！",
            "error": "分析出错",
        }
        status_placeholder.info(status_texts.get(stage, f"处理中... ({stage})"))
        bar.progress(min(int(pct * 100), 100))

    analyzer = VideoAnalyzer(video_path)
    result = analyzer.analyze(progress_callback=on_progress)

    status_placeholder.empty()
    bar.empty()

    if result.error:
        st.error(f"分析出错: {result.error}")
        return ""

    html = generate_video_report(result)
    return html


def _render_report(html: str):
    """Display video analysis report."""
    if not html:
        return
    components.html(html, height=2000, scrolling=True)


def video_analysis_page():
    """Main page function — called from app.py."""
    st.markdown("# <i class='fas fa-video' style='margin-right:8px;'></i> 视频分析", unsafe_allow_html=True)
    st.markdown("<p>上传你的《无畏契约》录屏或实时采集画面，获取帧率、反应时间、回合分析等深度数据。</p>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📂 上传录像分析", "🔴 实时采集"])

    # --- Tab 1: Upload & Analyze ---
    with tab1:
        uploaded_file = st.file_uploader(
            "选择 MP4 录屏文件",
            type=["mp4", "avi", "mov", "mkv"],
            help="支持常见视频格式，建议录制 720p 以上分辨率",
        )

        if uploaded_file:
            with st.expander("📋 文件信息", expanded=False):
                file_size_mb = len(uploaded_file.getvalue()) / 1024 / 1024
                st.write(f"文件名: {uploaded_file.name}")
                st.write(f"文件大小: {file_size_mb:.1f} MB")

            if st.button("🚀 开始分析", type="primary", use_container_width=True):
                with st.spinner("正在保存上传文件..."):
                    suffix = os.path.splitext(uploaded_file.name)[1] or ".mp4"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(uploaded_file.getvalue())
                        tmp_path = tmp.name

                try:
                    html_report = _run_analysis(tmp_path)
                    if html_report:
                        st.success("✅ 分析完成！")
                        st.session_state.video_report_html = html_report
                        _render_report(html_report)
                except Exception as e:
                    logger.error(f"Video analysis error: {traceback.format_exc()}")
                    st.error(f"❌ 分析失败: {str(e)}")
                finally:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

        # Show last report if exists
        if st.session_state.get("video_report_html") and not uploaded_file:
            st.info("📄 显示上次分析结果")
            if st.button("查看上次报告", use_container_width=True):
                _render_report(st.session_state.video_report_html)

        # Guide section
        st.markdown("---")
        st.markdown("### <i class='fas fa-lightbulb' style='margin-right:4px;'></i> 录制建议", unsafe_allow_html=True)
        guide_cols = st.columns(3)
        guides = [
            ("🎯", "分辨率", "建议 1920×1080，保证最小地图和击杀信息清晰可见"),
            ("⚡", "帧率", "60fps 以上录制，过低帧率会影响反应时间分析的准确性"),
            ("📏", "时长", "单次录制建议包含完整的 1-2 场对局（约 30-60 分钟）"),
        ]
        for col, (icon, title, desc) in zip(guide_cols, guides):
            with col:
                st.markdown(f"""
                <div style="background:rgba(255,255,255,0.03);border-radius:12px;padding:16px;text-align:center;border:1px solid rgba(255,255,255,0.06);">
                    <div style="font-size:28px;margin-bottom:8px;">{icon}</div>
                    <div style="font-weight:600;color:#e0e0e0;margin-bottom:4px;">{title}</div>
                    <div style="font-size:13px;color:#888;">{desc}</div>
                </div>
                """, unsafe_allow_html=True)

    # --- Tab 2: Live Capture ---
    with tab2:
        st.info("🔴 实时采集功能：捕获当前屏幕画面进行分析")

        duration = st.slider("采集时长 (秒)", min_value=30, max_value=600, value=180, step=30)

        col1, col2 = st.columns([1, 3])
        with col1:
            start_capture = st.button("⏺ 开始采集", type="primary", use_container_width=True)
        with col2:
            st.caption("采集期间请确保《无畏契约》处于前台运行状态")

        if start_capture:
            try:
                import mss
                import cv2
                import numpy as np
            except ImportError:
                st.error("实时采集需要安装 mss 库: `pip install mss`")
                st.stop()

            progress_bar = st.progress(0, text="准备采集...")
            status_text = st.empty()

            try:
                # Use temp file for live capture
                with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                    tmp_path = tmp.name

                # Screen capture loop
                monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                out = cv2.VideoWriter(tmp_path, fourcc, 30.0, (1920, 1080))

                with mss.mss() as sct:
                    start_time = time.time()
                    frame_count = 0
                    total_frames = duration * 30

                    while time.time() - start_time < duration:
                        img = sct.grab(monitor)
                        frame = np.array(img)
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                        out.write(frame)
                        frame_count += 1

                        elapsed = time.time() - start_time
                        pct = min(elapsed / duration, 1.0)
                        progress_bar.progress(int(pct * 100))
                        status_text.info(f"采集进度: {elapsed:.0f}/{duration} 秒 ({frame_count} 帧)")

                out.release()

                progress_bar.empty()
                status_text.success(f"采集完成！共 {frame_count} 帧")

                # Analyze captured video
                st.info("正在分析采集的视频...")
                html_report = _run_analysis(tmp_path)
                if html_report:
                    st.success("✅ 分析完成！")
                    st.session_state.video_report_html = html_report
                    _render_report(html_report)

                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"Live capture error: {traceback.format_exc()}")
                st.error(f"❌ 采集失败: {str(e)}")
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass


if __name__ == "__main__":
    st.set_page_config(page_title="视频分析 - ValCoach", page_icon="🎥", layout="wide")
    video_analysis_page()

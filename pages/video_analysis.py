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
        st.info("🔴 实时采集：录制屏幕画面，点击「开始录制」和「停止录制」控制采集过程")

        # ── Session state for capture ──
        if "capture_running" not in st.session_state:
            st.session_state.capture_running = False
            st.session_state.capture_path = None
            st.session_state.flag_path = None
            st.session_state.capture_start = 0
            st.session_state.capture_thread = None

        # ── Helper: background capture worker ──
        def _capture_worker(path: str, flag_path: str, fps: int = 20):
            import mss
            import cv2
            import numpy as np
            monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(path, fourcc, fps, (1920, 1080))
            try:
                with mss.mss() as sct:
                    while os.path.exists(flag_path):
                        frame = np.array(sct.grab(monitor))
                        out.write(cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR))
                        time.sleep(1 / fps)
            finally:
                out.release()

        if not st.session_state.capture_running:
            # ── Show previous report if available ──
            if st.session_state.get("video_report_html"):
                if st.button("📄 查看上次分析报告", use_container_width=True):
                    _render_report(st.session_state.video_report_html)
                st.markdown("---")

            if st.button("⏺ 开始录制", type="primary", use_container_width=True):
                try:
                    import mss
                    import cv2
                    import numpy as np
                except ImportError:
                    st.error("需要安装 mss 和 opencv-python: `pip install mss opencv-python-headless`")
                    st.stop()

                import threading

                path = tempfile.mktemp(suffix=".mp4")
                flag_path = path + ".flag"
                open(flag_path, "w").close()  # flag file exists = keep recording

                t = threading.Thread(
                    target=_capture_worker, args=(path, flag_path), daemon=True
                )
                t.start()

                st.session_state.capture_running = True
                st.session_state.capture_path = path
                st.session_state.flag_path = flag_path
                st.session_state.capture_thread = t
                st.session_state.capture_start = time.time()
                st.experimental_rerun()

        else:
            elapsed = time.time() - st.session_state.capture_start
            mins, secs = divmod(int(elapsed), 60)

            st.markdown(f"""
            <div style="text-align:center; padding:20px; border:2px solid #ff4444;
                        border-radius:12px; background:rgba(255,0,0,0.05);">
                <div style="font-size:48px; margin-bottom:10px;">🔴</div>
                <div style="font-size:20px; font-weight:bold;">正在录制...</div>
                <div style="font-size:28px; color:#ff6666; font-weight:bold; margin:8px 0;">
                    {mins:02d}:{secs:02d}</div>
                <div style="font-size:13px; color:#888;">停止后自动进行分析</div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("⏹ 停止录制", type="primary", use_container_width=True):
                # Signal the background thread to stop
                fp = st.session_state.flag_path
                if fp and os.path.exists(fp):
                    os.remove(fp)

                # Wait for thread to finish writing
                thread = st.session_state.capture_thread
                if thread:
                    thread.join(timeout=10)

                st.session_state.capture_running = False

                # ── Run video analysis pipeline with progress ──
                video_path = st.session_state.capture_path
                from src.video_analyzer import VideoAnalyzer

                progress_bar = st.progress(0, text="正在分析视频...")
                status_text = st.empty()

                def on_progress(stage: str, pct: float):
                    status_texts = {
                        "performance": "正在分析帧率与性能...",
                        "scene": "正在检测回合边界...",
                        "crosshair": "正在检测开枪与反应时间...",
                        "done": "分析完成！",
                        "error": "分析出错",
                    }
                    status_text.info(status_texts.get(stage, f"处理中... ({stage})"))
                    progress_bar.progress(min(int(pct * 100), 100))

                try:
                    analyzer = VideoAnalyzer(video_path)
                    result = analyzer.analyze(progress_callback=on_progress)

                    progress_bar.empty()
                    status_text.empty()

                    if result.error:
                        st.error(f"❌ 分析出错: {result.error}")
                    else:
                        html_report = generate_video_report(result)
                        if html_report:
                            st.success("✅ 分析完成！")
                            st.session_state.video_report_html = html_report
                            _render_report(html_report)
                        else:
                            st.error("❌ 报告生成失败")
                except Exception as e:
                    progress_bar.empty()
                    status_text.empty()
                    logger.error(f"Live capture analysis error: {traceback.format_exc()}")
                    st.error(f"❌ 分析失败: {str(e)}")

                # Cleanup temp file
                try:
                    if video_path and os.path.exists(video_path):
                        os.unlink(video_path)
                except Exception:
                    pass

                # No rerun here — report stays visible

            # Poll for UI updates (elapsed time refreshes ~every 2s)
            time.sleep(2)
            st.experimental_rerun()


if __name__ == "__main__":
    st.set_page_config(page_title="视频分析 - ValCoach", page_icon="🎥", layout="wide")
    video_analysis_page()

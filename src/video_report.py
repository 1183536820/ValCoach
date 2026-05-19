"""HTML report generator for video analysis results."""

import io
import base64
from datetime import datetime
from typing import List, Dict, Any, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .video_analyzer import VideoAnalysisResult
from .video_diagnosis import diagnose_video


def _build_fps_chart(result: VideoAnalysisResult) -> str:
    """Generate FPS over time chart."""
    if not result.performance or not result.performance.fps_samples:
        return ""

    samples = result.performance.fps_samples
    # Downsample to ~200 points for chart readability
    step = max(1, len(samples) // 200)
    sampled = samples[::step]

    times = [s.time_sec for s in sampled]
    fps_vals = [s.fps for s in sampled]
    stutter_mask = [s.is_stutter for s in sampled]

    fig, ax = plt.subplots(figsize=(12, 4))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    # Main FPS line
    ax.plot(times, fps_vals, color="#4a90d9", linewidth=1.5, alpha=0.8, label="FPS")

    # Highlight stutter regions
    if any(stutter_mask):
        stutter_times = [times[i] for i in range(len(times)) if stutter_mask[i]]
        stutter_fps = [fps_vals[i] for i in range(len(times)) if stutter_mask[i]]
        ax.scatter(stutter_times, stutter_fps, color="#ff4655", s=8, alpha=0.6, label="卡顿")

    ax.axhline(y=result.performance.avg_fps, color="#ffd700", linestyle="--",
               linewidth=1, alpha=0.7, label=f"平均 {result.performance.avg_fps:.0f} FPS")

    ax.set_xlabel("时间 (秒)", color="#888888", fontsize=10)
    ax.set_ylabel("FPS", color="#888888", fontsize=10)
    ax.set_title("帧率变化", color="#e0e0e0", fontsize=13)

    ax.tick_params(colors="#888888")
    ax.spines["bottom"].set_color("#333333")
    ax.spines["top"].set_color("#333333")
    ax.spines["left"].set_color("#333333")
    ax.spines["right"].set_color("#333333")
    ax.grid(color="#333333", linewidth=0.5, alpha=0.5)
    ax.legend(fontsize=9, labelcolor="#e0e0e0")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#1a1a2e")
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return img_base64


def _build_reaction_chart(result: VideoAnalysisResult) -> str:
    """Generate reaction time bar chart per round."""
    if not result.crosshair or not result.crosshair.reaction_times_ms:
        return ""

    rts = result.crosshair.reaction_times_ms
    rounds = list(range(1, len(rts) + 1))

    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    colors = ["#4a90d9" if rt <= 200 else "#e67e22" if rt <= 350 else "#ff4655" for rt in rts]
    ax.bar(rounds, rts, color=colors, alpha=0.8, width=0.6)

    ax.axhline(y=result.crosshair.avg_reaction_time_ms, color="#ffd700",
               linestyle="--", linewidth=1, alpha=0.7,
               label=f"平均 {result.crosshair.avg_reaction_time_ms:.0f} ms")

    ax.set_xlabel("回合", color="#888888", fontsize=10)
    ax.set_ylabel("反应时间 (ms)", color="#888888", fontsize=10)
    ax.set_title("每回合反应时间", color="#e0e0e0", fontsize=13)

    ax.tick_params(colors="#888888")
    ax.spines["bottom"].set_color("#333333")
    ax.spines["top"].set_color("#333333")
    ax.spines["left"].set_color("#333333")
    ax.spines["right"].set_color("#333333")
    ax.grid(color="#333333", linewidth=0.5, alpha=0.5, axis="y")
    ax.legend(fontsize=9, labelcolor="#e0e0e0")
    ax.set_xticks(rounds)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#1a1a2e")
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return img_base64


def _build_round_timeline(result: VideoAnalysisResult) -> str:
    """Generate round timeline visualization."""
    if not result.scene or not result.scene.rounds:
        return ""

    html = '<div style="margin: 20px 0;">'
    for r in result.scene.rounds:
        pct = min(r.duration_sec / 120 * 100, 100)
        color = "#4a90d9"
        html += f"""
        <div style="margin: 6px 0; display: flex; align-items: center; gap: 10px;">
            <span style="min-width: 60px; font-size: 13px; color: #aaa;">R{r.round_number}</span>
            <div style="flex: 1; height: 20px; background: rgba(255,255,255,0.05); border-radius: 10px; overflow: hidden;">
                <div style="width: {pct:.0f}%; height: 100%; background: {color}; border-radius: 10px;
                            opacity: 0.7; transition: width 0.3s;"></div>
            </div>
            <span style="min-width: 50px; font-size: 12px; color: #888; text-align: right;">{r.duration_sec:.1f}s</span>
        </div>"""
    html += "</div>"
    return html


def generate_video_report(result: VideoAnalysisResult) -> str:
    """Generate complete HTML report for video analysis."""
    diagnoses = diagnose_video(result)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    duration_str = f"{result.duration_sec:.0f} 秒" if result.duration_sec < 60 else f"{result.duration_sec / 60:.1f} 分钟"

    # --- FPS chart ---
    fps_chart = _build_fps_chart(result)
    fps_chart_html = ""
    if fps_chart:
        fps_chart_html = f"""
        <div class="chart-container">
            <img src="data:image/png;base64,{fps_chart}" alt="FPS Chart" style="max-width: 100%; height: auto;">
        </div>"""

    # --- Reaction time chart ---
    rt_chart = _build_reaction_chart(result)
    rt_chart_html = ""
    if rt_chart:
        rt_chart_html = f"""
        <div class="chart-container">
            <img src="data:image/png;base64,{rt_chart}" alt="Reaction Time Chart" style="max-width: 100%; height: auto;">
        </div>"""

    # --- Round timeline ---
    timeline_html = _build_round_timeline(result)

    # --- Performance stats ---
    perf_html = '<p style="color: #888;">未进行性能分析</p>'
    if result.performance:
        perf_html = f"""
        <table>
            <thead><tr><th>指标</th><th>数值</th></tr></thead>
            <tbody>
                <tr><td>平均帧率</td><td>{result.performance.avg_fps:.1f} FPS</td></tr>
                <tr><td>最低帧率 (1% Low)</td><td>{result.performance.p1_low_fps:.1f} FPS</td></tr>
                <tr><td>卡顿率</td><td>{result.performance.stutter_pct:.1f}%</td></tr>
                <tr><td>卡顿次数</td><td>{len(result.performance.stutters)} 次</td></tr>
                <tr><td>总帧数</td><td>{result.performance.total_frames}</td></tr>
            </tbody>
        </table>"""

    # --- Crosshair stats ---
    crosshair_html = '<p style="color: #888;">未进行准星分析</p>'
    if result.crosshair:
        crosshair_html = f"""
        <table>
            <thead><tr><th>指标</th><th>数值</th></tr></thead>
            <tbody>
                <tr><td>检测开枪次数</td><td>{result.crosshair.total_shots}</td></tr>
                <tr><td>平均反应时间</td><td>{result.crosshair.avg_reaction_time_ms:.0f} ms</td></tr>
                <tr><td>每回合开枪数</td><td>{result.crosshair.shots_per_round:.1f}</td></tr>
            </tbody>
        </table>"""

    # --- Round stats ---
    scene_html = ""
    if result.scene:
        scene_html = f"""
        <table>
            <thead><tr><th>指标</th><th>数值</th></tr></thead>
            <tbody>
                <tr><td>检测回合数</td><td>{result.scene.total_rounds}</td></tr>
                <tr><td>平均回合时长</td><td>{result.scene.avg_round_duration_sec:.1f} 秒</td></tr>
            </tbody>
        </table>"""

    # --- Diagnosis cards ---
    diagnosis_cards = ""
    for d in diagnoses:
        if d["metric"] == "error":
            diagnosis_cards += f"""
            <div class="diagnosis-card" style="border-left: 4px solid #e74c3c;">
                <div class="diagnosis-header">
                    <span class="metric-name">{d['label']}</span>
                    <span class="severity-badge" style="background:#e74c3c20;color:#e74c3c;">严重</span>
                </div>
                <div class="diagnosis-advice">{d['advice']}</div>
            </div>"""
            continue

        sev_color = {"low": "#27ae60", "medium": "#e67e22", "high": "#e74c3c"}
        sev_label = {"low": "良好", "medium": "待改善", "high": "需重视"}
        color = sev_color.get(d["severity"], "#e67e22")

        value_str = f"{d['value']:.0f}{d['unit']}" if d.get("unit") else f"{d['value']:.1f}"
        drills_html = ""
        if d.get("drills"):
            drills_html = "<div style='margin-top: 10px;'>"
            drills_html += f"<div style='font-size: 13px; color: #aaa; margin-bottom: 6px;'>💡 改进建议：</div>"
            for drill in d["drills"]:
                drills_html += f"<div style='font-size: 13px; color: #ccc; padding: 2px 0;'>• {drill}</div>"
            drills_html += "</div>"

        diagnosis_cards += f"""
        <div class="diagnosis-card" style="border-left: 4px solid {color};">
            <div class="diagnosis-header">
                <span class="metric-name">{d['label']}</span>
                <span class="severity-badge" style="background:{color}20;color:{color};">{sev_label.get(d['severity'], '未知')}</span>
            </div>
            <div class="diagnosis-detail">数值: {value_str}</div>
            <div class="diagnosis-advice">{d['advice']}</div>
            {drills_html}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ValCoach 视频分析报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .card {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 24px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .header {{ text-align: center; padding: 40px 30px; }}
        .header h1 {{ font-size: 28px; background: linear-gradient(90deg, #ff4655, #ff6b81); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }}
        .header .subtitle {{ color: #888; font-size: 14px; }}
        .section-title {{ font-size: 20px; margin-bottom: 20px; color: #e0e0e0; padding-left: 12px; border-left: 3px solid #ff4655; }}
        .chart-container {{ display: flex; justify-content: center; margin: 16px 0; background: rgba(0, 0, 0, 0.2); border-radius: 12px; padding: 16px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 16px 0; background: rgba(0, 0, 0, 0.2); border-radius: 12px; overflow: hidden; }}
        th {{ background: rgba(255, 70, 85, 0.15); padding: 10px 14px; text-align: left; font-weight: 600; font-size: 14px; color: #ccc; }}
        td {{ padding: 10px 14px; border-top: 1px solid rgba(255, 255, 255, 0.05); font-size: 14px; }}
        tr:hover {{ background: rgba(255, 255, 255, 0.03); }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 20px 0; }}
        .metric-card {{ background: rgba(0, 0, 0, 0.2); border-radius: 12px; padding: 20px; text-align: center; }}
        .metric-value {{ font-size: 32px; font-weight: 700; color: #ff4655; }}
        .metric-label {{ font-size: 13px; color: #888; margin-top: 4px; }}
        .diagnosis-card {{ background: rgba(0, 0, 0, 0.2); border-radius: 10px; padding: 20px; margin: 16px 0; }}
        .diagnosis-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }}
        .metric-name {{ font-size: 16px; font-weight: 600; color: #e0e0e0; }}
        .severity-badge {{ display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }}
        .diagnosis-detail {{ font-size: 13px; color: #888; margin-bottom: 8px; }}
        .diagnosis-advice {{ font-size: 14px; line-height: 1.6; color: #ccc; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid rgba(255, 255, 255, 0.1); text-align: center; font-size: 12px; color: #666; }}
        @media (max-width: 600px) {{ body {{ padding: 10px; }} .card {{ padding: 16px; }} .header h1 {{ font-size: 22px; }} .metric-value {{ font-size: 26px; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card header">
            <h1>ValCoach 视频分析报告</h1>
            <div class="subtitle">生成时间: {now_str} | 视频时长: {duration_str}</div>
        </div>

        <!-- Key Metrics -->
        <div class="card">
            <h2 class="section-title">关键指标概览</h2>
            <div class="metrics-grid">
                {f'<div class="metric-card"><div class="metric-value">{result.performance.avg_fps:.0f}</div><div class="metric-label">平均 FPS</div></div>' if result.performance else ''}
                {f'<div class="metric-card"><div class="metric-value">{result.performance.stutter_pct:.1f}%</div><div class="metric-label">卡顿率</div></div>' if result.performance else ''}
                {f'<div class="metric-card"><div class="metric-value">{result.crosshair.avg_reaction_time_ms:.0f}</div><div class="metric-label">平均反应 (ms)</div></div>' if result.crosshair and result.crosshair.avg_reaction_time_ms > 0 else ''}
                {f'<div class="metric-card"><div class="metric-value">{result.scene.total_rounds}</div><div class="metric-label">检测回合</div></div>' if result.scene else ''}
                {f'<div class="metric-card"><div class="metric-value">{result.crosshair.total_shots}</div><div class="metric-label">开枪次数</div></div>' if result.crosshair else ''}
                {f'<div class="metric-card"><div class="metric-value">{result.total_frames}</div><div class="metric-label">总帧数</div></div>' if result.total_frames > 0 else ''}
            </div>
        </div>

        <!-- FPS Chart -->
        {f'<div class="card"><h2 class="section-title">帧率分析</h2>{fps_chart_html}{perf_html}</div>' if result.performance else ''}

        <!-- Round Analysis -->
        {f'<div class="card"><h2 class="section-title">回合分析</h2>{scene_html}{timeline_html}</div>' if result.scene else ''}

        <!-- Aim / Shot Analysis -->
        {f'<div class="card"><h2 class="section-title">瞄准与开枪分析</h2>{rt_chart_html}{crosshair_html}</div>' if result.crosshair else ''}

        <!-- Diagnosis -->
        {f'<div class="card"><h2 class="section-title">智能诊断与改进建议</h2>{diagnosis_cards}</div>' if diagnosis_cards else ''}

        <div class="footer">
            <p>本报告由 AI 通过视频分析生成，仅供参考。</p>
            <p>ValCoach — 你的《无畏契约》AI 教练</p>
        </div>
    </div>
</body>
</html>"""
    return html

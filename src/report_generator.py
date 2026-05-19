import io
import base64
import math
from datetime import datetime
from typing import List, Dict, Any, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.diagnosis import METRIC_LABELS


def _normalize_metrics(
    player_metrics: Dict[str, float],
    baseline_metrics: Dict[str, Any]
) -> Dict[str, float]:
    normalized = {}
    for key in baseline_metrics:
        if key not in player_metrics:
            continue
        player_val = player_metrics[key]
        baseline_val = float(baseline_metrics[key])
        if baseline_val == 0:
            normalized[key] = 0.5
        else:
            # Cap at 200% to avoid extreme values distorting the chart
            normalized[key] = min(player_val / baseline_val, 2.0)
    return normalized


def _build_radar_chart_base64(
    player_metrics: Dict[str, float],
    baseline_metrics: Dict[str, Any]
) -> str:
    labels = []
    player_values = []
    baseline_values = []

    normalized = _normalize_metrics(player_metrics, baseline_metrics)

    for key in baseline_metrics:
        if key in player_metrics and key in normalized:
            labels.append(METRIC_LABELS.get(key, key))
            player_values.append(normalized[key])
            baseline_values.append(1.0)

    num_vars = len(labels)
    if num_vars == 0:
        return ""

    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    angles += angles[:1]

    player_values_plot = player_values + player_values[:1]
    baseline_values_plot = baseline_values + baseline_values[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    ax.plot(angles, baseline_values_plot, "o-", linewidth=2, label="高分玩家基准", color="#4a90d9")
    ax.fill(angles, baseline_values_plot, alpha=0.1, color="#4a90d9")

    ax.plot(angles, player_values_plot, "o-", linewidth=2, label="你的数据", color="#e74c3c")
    ax.fill(angles, player_values_plot, alpha=0.15, color="#e74c3c")

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=11, color="#e0e0e0")
    ax.set_ylim(0, 2.0)
    ax.set_yticks([0.5, 1.0, 1.5, 2.0])
    ax.set_yticklabels(["50%", "100%", "150%", "200%"], color="#888888", fontsize=9)

    ax.tick_params(colors="#888888")
    for spine in ax.spines.values():
        spine.set_color("#333333")

    ax.set_title("能力雷达图 - 玩家 vs 高分基准", color="#e0e0e0", fontsize=14, pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=10, labelcolor="#e0e0e0")

    # Add gridlines
    ax.grid(color="#333333", linewidth=0.5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)

    return img_base64


def generate_report(
    player_id: str,
    player_metrics: Dict[str, float],
    diagnosis_results: List[Dict[str, Any]],
    baseline_metrics: Dict[str, Any],
    acs_trend: Optional[List[float]] = None,
) -> str:
    radar_img = _build_radar_chart_base64(player_metrics, baseline_metrics)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    metrics_rows = ""
    for key, baseline_val in baseline_metrics.items():
        if key in player_metrics:
            player_val = player_metrics[key]
            label = METRIC_LABELS.get(key, key)
            metrics_rows += f"""
            <tr>
                <td>{label}</td>
                <td>{player_val}</td>
                <td>{baseline_val}</td>
                <td>{'+' if player_val >= float(baseline_val) else ''}{round((player_val - float(baseline_val)) / float(baseline_val) * 100, 1)}%</td>
            </tr>"""

    diagnosis_html = ""
    for diag in diagnosis_results:
        color = "#e74c3c"
        diagnosis_html += f"""
        <div class="diagnosis-card" style="border-left: 4px solid {color};">
            <div class="diagnosis-header">
                <span class="metric-name">{diag['label']}</span>
                <span class="gap-badge" style="background: {color}20; color: {color};">
                    {diag['gap']:+.1f}%
                </span>
            </div>
            <div class="diagnosis-detail">
                你的数值: {diag['player_value']} | 基准值: {diag['baseline_value']}
            </div>
            <div class="diagnosis-advice">{diag['advice']}</div>
        </div>"""

    radar_html = ""
    if radar_img:
        radar_html = f"""
        <div class="chart-container">
            <img src="data:image/png;base64,{radar_img}" alt="雷达图" style="max-width: 100%; height: auto;">
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ValCoach - {player_id} 诊断报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 40px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .header h1 {{
            font-size: 28px;
            background: linear-gradient(90deg, #ff4655, #ff6b81);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        .header .subtitle {{
            color: #888;
            font-size: 14px;
        }}
        .header .player-id {{
            font-size: 20px;
            color: #e0e0e0;
            margin-top: 12px;
        }}
        .section-title {{
            font-size: 20px;
            margin: 30px 0 20px;
            color: #e0e0e0;
            padding-left: 12px;
            border-left: 3px solid #ff4655;
        }}
        .chart-container {{
            display: flex;
            justify-content: center;
            margin: 20px 0;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 12px;
            padding: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 12px;
            overflow: hidden;
        }}
        th {{
            background: rgba(255, 70, 85, 0.15);
            padding: 12px 16px;
            text-align: left;
            font-weight: 600;
            font-size: 14px;
            color: #ccc;
        }}
        td {{
            padding: 12px 16px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            font-size: 14px;
        }}
        tr:hover {{
            background: rgba(255, 255, 255, 0.03);
        }}
        .diagnosis-card {{
            background: rgba(0, 0, 0, 0.2);
            border-radius: 10px;
            padding: 20px;
            margin: 16px 0;
        }}
        .diagnosis-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }}
        .metric-name {{
            font-size: 18px;
            font-weight: 600;
            color: #e0e0e0;
        }}
        .gap-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
        }}
        .diagnosis-detail {{
            font-size: 13px;
            color: #888;
            margin-bottom: 10px;
        }}
        .diagnosis-advice {{
            font-size: 14px;
            line-height: 1.6;
            color: #ccc;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            text-align: center;
            font-size: 12px;
            color: #666;
            line-height: 1.8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>ValCoach 赛后诊断报告</h1>
            <div class="player-id">{player_id}</div>
            <div class="subtitle">生成时间: {now_str} | 最近 20 场排位赛分析</div>
        </div>

        {radar_html}

        <h2 class="section-title">指标对比</h2>
        <table>
            <thead>
                <tr>
                    <th>指标</th>
                    <th>你的数值</th>
                    <th>高分基准</th>
                    <th>差距</th>
                </tr>
            </thead>
            <tbody>
                {metrics_rows}
            </tbody>
        </table>

        <h2 class="section-title">核心短板分析</h2>
        {diagnosis_html if diagnosis_html else '<p style="color: #27ae60; text-align: center; padding: 20px;">所有指标均达到或超过基准水平！继续保持！</p>'}

        <div class="footer">
            <p>本报告由 AI 生成，仅供参考。</p>
            <p>数据来源：Riot Games API。本产品未经 Riot Games 认可。</p>
            <p>ValCoach 是一个独立的第三方分析工具。</p>
        </div>
    </div>
</body>
</html>"""

    return html

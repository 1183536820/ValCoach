"""Rule-based diagnosis engine for video analysis metrics."""

from typing import List, Dict, Any
from .video_analyzer import VideoAnalysisResult


DIAGNOSIS_THRESHOLDS = {
    "reaction_time": {
        "good": 200,
        "warning": 350,
        "bad": 350,
        "unit": "ms",
        "label": "反应时间",
    },
    "stutter_pct": {
        "good": 5,
        "warning": 15,
        "bad": 15,
        "unit": "%",
        "label": "帧卡顿率",
    },
    "avg_fps": {
        "good": 144,
        "warning": 60,
        "bad": 60,
        "unit": "fps",
        "label": "平均帧率",
    },
    "shots_per_round": {
        "good": 4,
        "warning": 6,
        "bad": 6,
        "unit": "",
        "label": "每回合开枪数",
    },
    "rounds_detected": {
        "good": 24,
        "warning": 12,
        "bad": 6,
        "unit": "",
        "label": "检测回合数",
    },
}

DRILL_RECOMMENDATIONS = {
    "reaction_time": [
        "每天进行 15 分钟 Aim Lab / KovaaK's 点击训练（Gridshot / Microshot）",
        "在训练场练习 '死斗模式'，专注第一时间瞄准头部",
        "调整鼠标灵敏度（建议 eDPI 200-400），避免过灵或过钝",
    ],
    "stutter_pct": [
        "降低游戏内画质设置（尤其是阴影和反射）",
        "关闭后台无关程序（浏览器、录屏软件等）",
        "检查 Windows 电源管理是否设为 '高性能' 模式",
        "尝试禁用全屏优化（右键 Valorant.exe → 属性 → 兼容性）",
    ],
    "avg_fps": [
        "降低渲染分辨率至 1080p",
        "更新显卡驱动至最新版本",
        "确认是否启用了 '多线程渲染'",
    ],
    "shots_per_round": [
        "练习 '先停后打'：急停后再开枪，提高子弹利用率",
        "在训练场练习 '一次爆头' 挑战，减少无效扫射",
        "回放自己的录像，检查是否在跑动中开枪",
    ],
    "rounds_detected": [
        "确保录制时包含完整的对局过程（从选择英雄到比赛结束）",
        "避免在录制中切屏或暂停，以免影响黑屏检测",
    ],
}

DIAGNOSIS_SEVERITY_PRAISE = {
    "reaction_time": {
        "fast": "你的反应速度很快，说明你的神经连接和专注度处于优秀水平。继续保持！",
        "normal": "反应速度处于平均水平，可以通过针对性训练进一步提升。",
        "slow": "反应速度偏慢，建议每天做 10 分钟反应训练，一个月内可见明显提升。",
    },
    "stutter_pct": {
        "good": "你的电脑性能很好，帧率稳定，游戏体验流畅。",
        "normal": "偶尔的卡顿可能影响了你的发挥，建议关闭后台程序。",
        "bad": "频繁卡顿严重影响了游戏体验和竞技表现，建议优先解决硬件/系统问题。",
    },
}


def diagnose_video(result: VideoAnalysisResult) -> List[Dict[str, Any]]:
    """Run rule-based diagnosis on video analysis result."""
    diagnoses = []

    if result.error:
        diagnoses.append({
            "metric": "error",
            "label": "分析错误",
            "severity": "high",
            "advice": f"视频分析过程中出错: {result.error}。请检查视频文件是否完整。",
        })
        return diagnoses

    # Reaction time diagnosis
    if result.crosshair and result.crosshair.avg_reaction_time_ms > 0:
        rt = result.crosshair.avg_reaction_time_ms
        thresholds = DIAGNOSIS_THRESHOLDS["reaction_time"]
        if rt <= thresholds["good"]:
            severity = "low"
            praise = DIAGNOSIS_SEVERITY_PRAISE["reaction_time"]["fast"]
        elif rt <= thresholds["warning"]:
            severity = "medium"
            praise = DIAGNOSIS_SEVERITY_PRAISE["reaction_time"]["normal"]
        else:
            severity = "high"
            praise = DIAGNOSIS_SEVERITY_PRAISE["reaction_time"]["slow"]

        diagnoses.append({
            "metric": "reaction_time",
            "label": thresholds["label"],
            "value": rt,
            "unit": thresholds["unit"],
            "severity": severity,
            "advice": praise,
            "drills": DRILL_RECOMMENDATIONS["reaction_time"],
        })

    # Stutter / FPS diagnosis
    if result.performance:
        stutter_pct = result.performance.stutter_pct
        thresholds = DIAGNOSIS_THRESHOLDS["stutter_pct"]
        if stutter_pct <= thresholds["good"]:
            severity = "low"
            praise = DIAGNOSIS_SEVERITY_PRAISE["stutter_pct"]["good"]
        elif stutter_pct <= thresholds["warning"]:
            severity = "medium"
            praise = DIAGNOSIS_SEVERITY_PRAISE["stutter_pct"]["normal"]
        else:
            severity = "high"
            praise = DIAGNOSIS_SEVERITY_PRAISE["stutter_pct"]["bad"]

        diagnoses.append({
            "metric": "stutter_pct",
            "label": thresholds["label"],
            "value": stutter_pct,
            "unit": thresholds["unit"],
            "severity": severity,
            "advice": praise,
            "drills": DRILL_RECOMMENDATIONS["stutter_pct"] if severity != "low" else [],
        })

        avg_fps = result.performance.avg_fps
        fps_thresholds = DIAGNOSIS_THRESHOLDS["avg_fps"]
        if avg_fps < fps_thresholds["bad"]:
            diagnoses.append({
                "metric": "avg_fps",
                "label": fps_thresholds["label"],
                "value": avg_fps,
                "unit": fps_thresholds["unit"],
                "severity": "high",
                "advice": f"平均帧率仅 {avg_fps:.0f} FPS，可能影响了你的瞄准和跟枪。建议优化系统设置。",
                "drills": DRILL_RECOMMENDATIONS["avg_fps"],
            })

    # Shot behavior diagnosis
    if result.crosshair and result.scene and result.scene.total_rounds > 0:
        shots_per_round = result.crosshair.shots_per_round
        thresholds = DIAGNOSIS_THRESHOLDS["shots_per_round"]
        if shots_per_round > thresholds["bad"]:
            diagnoses.append({
                "metric": "shots_per_round",
                "label": thresholds["label"],
                "value": shots_per_round,
                "unit": thresholds["unit"],
                "severity": "medium",
                "advice": f"每回合开枪 {shots_per_round:.1f} 次，偏高。可能扫射过多或子弹利用率不足。",
                "drills": DRILL_RECOMMENDATIONS["shots_per_round"],
            })

    # Round detection quality
    if result.scene:
        if result.scene.total_rounds < 6:
            diagnoses.append({
                "metric": "rounds_detected",
                "label": DIAGNOSIS_THRESHOLDS["rounds_detected"]["label"],
                "value": result.scene.total_rounds,
                "unit": DIAGNOSIS_THRESHOLDS["rounds_detected"]["unit"],
                "severity": "high",
                "advice": f"仅检测到 {result.scene.total_rounds} 个回合，可能视频不完整或录制质量不佳。",
                "drills": DRILL_RECOMMENDATIONS["rounds_detected"],
            })

    return diagnoses

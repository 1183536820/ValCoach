"""Video analysis orchestrator — runs all frame analyzers in sequence."""

import os
import time
from typing import Optional, Callable, List
from dataclasses import dataclass, field

from .frame_analyzers.performance import PerformanceAnalyzer, PerformanceResult
from .frame_analyzers.scene import SceneAnalyzer, SceneResult
from .frame_analyzers.crosshair import CrosshairAnalyzer, CrosshairMetrics


@dataclass
class VideoAnalysisResult:
    performance: Optional[PerformanceResult] = None
    scene: Optional[SceneResult] = None
    crosshair: Optional[CrosshairMetrics] = None
    total_frames: int = 0
    duration_sec: float = 0.0
    video_fps: float = 0.0
    error: Optional[str] = None


class VideoAnalyzer:
    """Orchestrate multiple frame analyzers over a video file."""

    def __init__(self, video_path: str):
        self.video_path = video_path
        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

    def analyze(
        self,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        skip_performance: bool = False,
        skip_scene: bool = False,
        skip_crosshair: bool = False,
    ) -> VideoAnalysisResult:
        """Run selected analyzers and merge results."""
        result = VideoAnalysisResult()

        def _report(stage: str, pct: float):
            if progress_callback:
                progress_callback(stage, pct)

        try:
            # 1. Performance (must run first to get total_frames / fps)
            if not skip_performance:
                _report("performance", 0.0)
                perf = PerformanceAnalyzer(self.video_path)
                perf_result = perf.analyze(
                    progress_callback=lambda p: _report("performance", p * 0.35)
                )
                result.performance = perf_result
                result.total_frames = perf_result.total_frames
                result.duration_sec = perf_result.duration_sec
            else:
                # minimal video info even when skipping
                import cv2
                cap = cv2.VideoCapture(self.video_path)
                if cap.isOpened():
                    result.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    result.video_fps = cap.get(cv2.CAP_PROP_FPS)
                    result.duration_sec = result.total_frames / max(1, result.video_fps)
                    cap.release()

            # 2. Scene / round detection
            if not skip_scene:
                _report("scene", 0.35)
                scene = SceneAnalyzer(self.video_path)
                scene_result = scene.analyze(
                    progress_callback=lambda p: _report("scene", 0.35 + p * 0.25)
                )
                result.scene = scene_result
                if result.video_fps <= 0 and scene_result.rounds:
                    result.video_fps = scene_result.rounds[0].start_frame / max(0.001, scene_result.rounds[0].start_time_sec)

            # 3. Crosshair / shot detection (needs round info for reaction time)
            if not skip_crosshair:
                _report("crosshair", 0.60)
                crosshair = CrosshairAnalyzer(self.video_path)
                rounds_info = result.scene.rounds if result.scene else None
                crosshair_result = crosshair.analyze(
                    rounds_info=rounds_info,
                    progress_callback=lambda p: _report("crosshair", 0.60 + p * 0.38),
                )
                result.crosshair = crosshair_result

            _report("done", 1.0)

        except Exception as e:
            result.error = str(e)
            _report("error", 1.0)

        return result

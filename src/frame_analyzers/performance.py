"""FPS & stutter analysis via frame differencing."""

from typing import List, Dict, Any, Optional, Tuple
import cv2
import numpy as np
from dataclasses import dataclass, field


@dataclass
class FpsSample:
    frame_idx: int
    time_sec: float
    fps: float
    is_stutter: bool = False
    frame_diff: float = 0.0


@dataclass
class StutterEvent:
    frame_idx: int
    time_sec: float
    duration_frames: int
    duration_sec: float


@dataclass
class PerformanceResult:
    fps_samples: List[FpsSample] = field(default_factory=list)
    stutters: List[StutterEvent] = field(default_factory=list)
    avg_fps: float = 0.0
    min_fps: float = 0.0
    p1_low_fps: float = 0.0
    stutter_pct: float = 0.0
    total_frames: int = 0
    duration_sec: float = 0.0


class PerformanceAnalyzer:
    """Analyze video for FPS, frame times, and stutters."""

    STUTTER_DIFF_THRESHOLD = 15.0   # Mean pixel diff below this = repeat frame
    MIN_STUTTER_FRAMES = 2          # At least N consecutive repeat frames

    def __init__(self, video_path: str):
        self.video_path = video_path

    def analyze(self, progress_callback=None, sample_interval: int = 1) -> PerformanceResult:
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {self.video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if video_fps <= 0:
            video_fps = 60.0

        result = PerformanceResult(total_frames=total_frames)

        prev_gray = None
        prev_valid_frame = None
        fps_samples = []
        stutter_candidates = []

        for i in range(0, total_frames, sample_interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            time_sec = i / video_fps

            if prev_gray is not None:
                diff = float(cv2.mean(cv2.absdiff(gray, prev_gray))[0])
                is_stutter = diff < self.STUTTER_DIFF_THRESHOLD
            else:
                diff = 0.0
                is_stutter = False

            # Compute instant FPS from frame diff (lower diff = more similar = lower effective FPS)
            if diff > 0:
                instant_fps = video_fps * (1.0 - max(0, min(1, 1.0 - diff / 255.0 * 2)))
                instant_fps = max(10.0, min(video_fps, instant_fps))
            else:
                instant_fps = video_fps

            fps_samples.append(FpsSample(
                frame_idx=i,
                time_sec=time_sec,
                fps=round(instant_fps, 1),
                is_stutter=is_stutter,
                frame_diff=round(diff, 2),
            ))

            if is_stutter:
                stutter_candidates.append(i)
            prev_gray = gray

            if progress_callback and i % max(1, 60 * sample_interval) == 0:
                progress_callback(i / total_frames)

        cap.release()

        # Aggregate stutters into events
        result.stutters = self._aggregate_stutters(stutter_candidates, video_fps)
        result.fps_samples = fps_samples

        # Compute aggregate stats
        fps_values = [s.fps for s in fps_samples if s.fps > 0]
        if fps_values:
            result.avg_fps = round(sum(fps_values) / len(fps_values), 1)
            result.min_fps = round(min(fps_values), 1)
            fps_values.sort()
            p1_idx = max(0, int(len(fps_values) * 0.01))
            result.p1_low_fps = round(fps_values[p1_idx], 1)

        stutter_frames = sum(1 for s in fps_samples if s.is_stutter)
        result.stutter_pct = round(stutter_frames / len(fps_samples) * 100, 2) if fps_samples else 0
        result.duration_sec = len(fps_samples) / video_fps if fps_samples else 0

        return result

    def _aggregate_stutters(self, candidates: List[int], video_fps: float) -> List[StutterEvent]:
        if not candidates:
            return []
        events = []
        start = candidates[0]
        count = 1
        for i in range(1, len(candidates)):
            if candidates[i] == candidates[i - 1] + 1:
                count += 1
            else:
                if count >= self.MIN_STUTTER_FRAMES:
                    events.append(StutterEvent(
                        frame_idx=start,
                        time_sec=start / video_fps,
                        duration_frames=count,
                        duration_sec=count / video_fps,
                    ))
                start = candidates[i]
                count = 1
        if count >= self.MIN_STUTTER_FRAMES:
            events.append(StutterEvent(
                frame_idx=start,
                time_sec=start / video_fps,
                duration_frames=count,
                duration_sec=count / video_fps,
            ))
        return events

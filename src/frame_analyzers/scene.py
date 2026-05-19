"""Scene detection: round boundaries, black screens, loading screens."""

from typing import List, Optional
from dataclasses import dataclass, field
import cv2
import numpy as np


@dataclass
class RoundInfo:
    round_number: int
    start_frame: int
    start_time_sec: float
    end_frame: int
    end_time_sec: float
    duration_sec: float = 0.0


@dataclass
class SceneResult:
    rounds: List[RoundInfo] = field(default_factory=list)
    total_rounds: int = 0
    avg_round_duration_sec: float = 0.0


class SceneAnalyzer:
    """Detect round transitions via black screen and loading screen detection."""

    BLACKSCREEN_THRESHOLD = 10     # Mean pixel value below this = black screen
    LOADING_BRIGHT_THRESHOLD = 240  # Very bright frames may be loading screens
    MIN_ROUND_FRAMES = 30          # Minimum frames for a valid round

    def __init__(self, video_path: str):
        self.video_path = video_path

    def analyze(self, progress_callback=None) -> SceneResult:
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {self.video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if video_fps <= 0:
            video_fps = 60.0

        transitions = []  # frame indices where scene changes
        prev_mean = 0.0

        for i in range(total_frames):
            ret, frame = cap.read()
            if not ret:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mean_val = float(cv2.mean(gray)[0])

            # Detect black screen transitions
            if mean_val < self.BLACKSCREEN_THRESHOLD and prev_mean > self.BLACKSCREEN_THRESHOLD * 2:
                transitions.append(i)

            prev_mean = mean_val

            if progress_callback and i % 60 == 0:
                progress_callback(i / total_frames)

        cap.release()

        # Build round segments from transitions
        rounds = []
        for j in range(len(transitions) - 1):
            start = transitions[j]
            end = transitions[j + 1]
            if end - start >= self.MIN_ROUND_FRAMES:
                rounds.append(RoundInfo(
                    round_number=len(rounds) + 1,
                    start_frame=start,
                    start_time_sec=start / video_fps,
                    end_frame=end,
                    end_time_sec=end / video_fps,
                    duration_sec=(end - start) / video_fps,
                ))

        result = SceneResult(rounds=rounds, total_rounds=len(rounds))
        if rounds:
            result.avg_round_duration_sec = round(
                sum(r.duration_sec for r in rounds) / len(rounds), 1
            )

        return result

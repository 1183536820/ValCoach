"""Crosshair / aim analysis: reaction time, shot detection, FOV center tracking."""

from typing import List, Tuple, Optional
from dataclasses import dataclass, field
import cv2
import numpy as np
from .scene import SceneAnalyzer


@dataclass
class ShotEvent:
    frame_idx: int
    time_sec: float
    round_number: int = 0


@dataclass
class CrosshairMetrics:
    shot_events: List[ShotEvent] = field(default_factory=list)
    reaction_times_ms: List[float] = field(default_factory=list)
    avg_reaction_time_ms: float = 0.0
    shots_per_round: float = 0.0
    total_shots: int = 0


class CrosshairAnalyzer:
    """Analyze crosshair center, detect shots via muzzle flash, estimate reaction time."""

    MUZZLE_FLASH_THRESHOLD = 200   # Brightness threshold for muzzle flash
    CENTER_RADIUS = 4              # Pixel radius around center to check
    MIN_SHOT_INTERVAL_FRAMES = 3   # Minimum frames between shots

    def __init__(self, video_path: str):
        self.video_path = video_path

    def analyze(self, rounds_info=None, progress_callback=None) -> CrosshairMetrics:
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {self.video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        if video_fps <= 0:
            video_fps = 60.0

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cx, cy = width // 2, height // 2

        shot_events = []
        last_shot_frame = -self.MIN_SHOT_INTERVAL_FRAMES

        # Process at reduced sample rate for speed
        sample_interval = max(1, int(video_fps / 4))  # ~4 fps

        for i in range(0, total_frames, sample_interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret:
                break

            # Check center region for brightness (muzzle flash detection)
            center_roi = frame[
                max(0, cy - self.CENTER_RADIUS):cy + self.CENTER_RADIUS + 1,
                max(0, cx - self.CENTER_RADIUS):cx + self.CENTER_RADIUS + 1
            ]
            if center_roi.size == 0:
                continue

            center_brightness = float(np.mean(cv2.cvtColor(center_roi, cv2.COLOR_BGR2GRAY)))

            if center_brightness > self.MUZZLE_FLASH_THRESHOLD:
                if i - last_shot_frame >= self.MIN_SHOT_INTERVAL_FRAMES:
                    time_sec = i / video_fps
                    shot_events.append(ShotEvent(frame_idx=i, time_sec=round(time_sec, 2)))
                    last_shot_frame = i

            if progress_callback and i % 300 == 0:
                progress_callback(i / total_frames)

        cap.release()

        result = CrosshairMetrics(shot_events=shot_events, total_shots=len(shot_events))

        # Assign round numbers if rounds_info provided
        if rounds_info:
            for shot in shot_events:
                for r in rounds_info:
                    if r.start_frame <= shot.frame_idx <= r.end_frame:
                        shot.round_number = r.round_number
                        break

            # Compute reaction times (time from round start to first shot)
            reaction_times = []
            for r in rounds_info:
                round_shots = [s for s in shot_events
                               if r.start_frame <= s.frame_idx <= r.end_frame]
                if round_shots:
                    first_shot = round_shots[0]
                    rt_ms = (first_shot.frame_idx - r.start_frame) / video_fps * 1000
                    reaction_times.append(rt_ms)

            if reaction_times:
                result.reaction_times_ms = [round(rt, 1) for rt in reaction_times]
                result.avg_reaction_time_ms = round(sum(reaction_times) / len(reaction_times), 1)

        # Shots per round
        if rounds_info:
            result.shots_per_round = round(len(shot_events) / max(1, len(rounds_info)), 1)

        return result

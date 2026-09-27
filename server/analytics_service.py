"""Actual session analytics, bounded live history, events, and summary metrics."""

from __future__ import annotations

import math
import statistics
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .performance_logger import PerformanceLogger


class AnalyticsService:
    def __init__(self, reports_dir: Path, logs_dir: Path) -> None:
        self.reports_dir, self.logs_dir = reports_dir, logs_dir
        self.history: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self._previous: dict[str, bool] = {}
        self.start(config={})

    def start(self, config: dict[str, Any]) -> None:
        self.session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:6]
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.logger = PerformanceLogger(self.reports_dir, self.logs_dir, self.session_id)
        self.rows: list[dict[str, Any]] = []
        self.history, self.events, self._previous = [], [], {}
        self.first_detection: float | None = None
        self.first_lock: float | None = None
        self.last_loss_at: float | None = None
        self.reacquisitions: list[float] = []
        self.lock_started: float | None = None
        self.total_lock_time = 0.0
        self.out_fov_started: float | None = None
        self.total_out_fov_time = 0.0
        self.los_blocked_started: float | None = None
        self.total_los_blocked_time = 0.0
        self.link_down_started: float | None = None
        self.total_link_downtime = 0.0
        self.config = config

    def add_event(self, timestamp: float, message: str, category: str = "system") -> None:
        event = {"timestamp": round(timestamp, 2), "message": message, "category": category}
        self.events.append(event)
        self.events = self.events[-120:]
        self.logger.event(event)

    def _transition(self, name: str, state: bool, timestamp: float, on: str, off: str, category: str) -> None:
        previous = self._previous.get(name)
        if previous is not None and previous != state:
            self.add_event(timestamp, on if state else off, category)
        self._previous[name] = state

    def record(self, row: dict[str, Any]) -> None:
        time_s = float(row["timestamp"])
        if row["detected"] and self.first_detection is None:
            self.first_detection = time_s
            self.add_event(time_s, f"Target {row['target_id']} detected", "tracking")
        if row["locked"] and self.first_lock is None:
            self.first_lock = time_s
            self.add_event(time_s, f"Target {row['target_id']} locked", "tracking")
        if not row["locked"] and self._previous.get("locked"):
            self.last_loss_at = time_s
            self.add_event(time_s, "Target temporarily lost", "tracking")
        if row["locked"] and self.last_loss_at is not None:
            elapsed = time_s - self.last_loss_at
            self.reacquisitions.append(elapsed)
            self.add_event(time_s, f"Target reacquired in {elapsed:.2f}s", "tracking")
            self.last_loss_at = None
        self._transition("locked", row["locked"], time_s, "Target lock acquired", "Target lock released", "tracking")
        self._transition("fov_ok", row["fov_ok"], time_s, "FOV OK", "FOV violation", "geometry")
        self._transition("los_clear", row["los_clear"], time_s, "LOS clear", "LOS blocked", "geometry")
        self._transition("fsoc_link", row["fsoc_link"], time_s, "FSOC link ready", "FSOC link not ready", "link")
        dt = float(row.get("dt", 0.0))
        self.total_lock_time += dt if row["locked"] else 0.0
        self.total_out_fov_time += dt if not row["fov_ok"] else 0.0
        self.total_los_blocked_time += dt if not row["los_clear"] else 0.0
        self.total_link_downtime += dt if not row["fsoc_link"] else 0.0
        self.rows.append(row)
        self.logger.record(row)
        self.history.append({key: row[key] for key in (
            "timestamp", "target_azimuth", "target_elevation", "camera_pan", "camera_tilt",
            "pixel_error", "angular_error", "pan_error", "tilt_error", "confidence", "distance",
            "fps", "processing_time_ms", "disturbance_level", "fsoc_link", "beacon_hidden",
        )})
        self.history = self.history[-240:]

    @staticmethod
    def _values(rows: list[dict[str, Any]], key: str) -> list[float]:
        return [float(row.get(key, 0.0) or 0.0) for row in rows]

    def summary(self) -> dict[str, Any]:
        rows = self.rows
        if not rows:
            return {"session_id": self.session_id, "started_at": self.started_at, "duration": 0.0}
        duration = float(rows[-1]["timestamp"])
        fps, error, angular, processing, confidence = (self._values(rows, key) for key in ("fps", "pixel_error", "angular_error", "processing_time_ms", "confidence"))
        locked = sum(bool(row["locked"]) for row in rows)
        linked = sum(bool(row["fsoc_link"]) for row in rows)
        fov_ok = sum(bool(row["fov_ok"]) for row in rows)
        losses = sum(1 for event in self.events if "temporarily lost" in event["message"])
        return {
            "session_id": self.session_id, "started_at": self.started_at, "duration": round(duration, 2), "total_frames_processed": len(rows),
            "total_frames_dropped": sum(1 for row in rows if row.get("dt", 0) > 1 / 18), "frame_drop_rate": round(100 * sum(1 for row in rows if row.get("dt", 0) > 1 / 18) / len(rows), 2),
            "average_fps": round(statistics.fmean(fps), 2), "minimum_fps": round(min(fps), 2), "maximum_fps": round(max(fps), 2),
            "acquisition_time": self.first_detection, "time_to_first_detection": self.first_detection, "time_to_first_lock": self.first_lock,
            "average_tracking_error": round(statistics.fmean(error), 3), "maximum_tracking_error": round(max(error), 3), "rms_tracking_error": round(math.sqrt(statistics.fmean(value * value for value in error)), 3),
            "average_angular_error": round(statistics.fmean(angular), 3), "maximum_angular_error": round(max(angular), 3),
            "average_processing_time": round(statistics.fmean(processing), 3), "maximum_processing_time": round(max(processing), 3),
            "average_detection_confidence": round(statistics.fmean(confidence), 3), "minimum_detection_confidence": round(min(confidence), 3), "maximum_detection_confidence": round(max(confidence), 3),
            "target_loss_count": losses, "target_reacquisition_count": len(self.reacquisitions), "average_reacquisition_time": round(statistics.fmean(self.reacquisitions), 3) if self.reacquisitions else None, "maximum_reacquisition_time": round(max(self.reacquisitions), 3) if self.reacquisitions else None,
            "total_time_target_locked": round(self.total_lock_time, 2), "lock_acquisition_count": sum(1 for event in self.events if event["message"] == "Target lock acquired"), "lock_retention_rate": round(100 * locked / len(rows), 2),
            "fov_violation_count": sum(1 for event in self.events if event["message"] == "FOV violation"), "total_time_outside_fov": round(self.total_out_fov_time, 2), "fov_compliance": round(100 * fov_ok / len(rows), 2),
            "los_interruption_count": sum(1 for event in self.events if event["message"] == "LOS blocked"), "total_los_blocked_time": round(self.total_los_blocked_time, 2), "los_availability": round(100 * sum(bool(row["los_clear"]) for row in rows) / len(rows), 2),
            "fsoc_link_retention_rate": round(100 * linked / len(rows), 2), "total_fsoc_link_downtime": round(self.total_link_downtime, 2),
            "alignment_success_count": sum(1 for event in self.events if event["message"] == "FSOC link ready"), "alignment_failure_count": sum(1 for event in self.events if event["message"] == "FSOC link not ready"),
            "average_azimuth_error": round(statistics.fmean(abs(float(row["azimuth_error"])) for row in rows), 3), "average_elevation_error": round(statistics.fmean(abs(float(row["elevation_error"])) for row in rows), 3), "average_pan_error": round(statistics.fmean(abs(float(row["pan_error"])) for row in rows), 3), "average_tilt_error": round(statistics.fmean(abs(float(row["tilt_error"])) for row in rows), 3),
            "settling_time": self.first_lock, "time_to_stable_alignment": self.first_lock, "tracking_stability_metric": round(1 / (1 + statistics.pstdev(angular)), 3) if len(angular) > 1 else 0.0,
        }

    def finalize(self, config: dict[str, Any]) -> dict[str, Any]:
        summary = self.summary()
        disturbances = config.get("disturbances", {})
        active_duration = lambda field, off: round(sum(float(row.get("dt", 0)) for row in self.rows if row.get(field) != off), 2)
        summary["disturbance_exposure"] = {
            "platform_vibration": {**disturbances.get("vibration", {}), "duration": active_duration("platform_vibration", "OFF")},
            "camera_motion": {**disturbances.get("camera_motion", {}), "duration": active_duration("camera_motion", "OFF")},
            "atmospheric_turbulence": {**disturbances.get("turbulence", {}), "duration": active_duration("atmospheric_turbulence", "OFF")},
            "sensor_noise": {"intensity": disturbances.get("sensor_noise", 0), "duration": active_duration("sensor_noise", 0)},
            "fog": {"level": disturbances.get("fog", 0), "duration": active_duration("fog", 0)},
            "noise": {"level": disturbances.get("noise", 0), "duration": active_duration("noise", 0)},
            "jitter": {"level": disturbances.get("jitter", 0), "duration": active_duration("jitter", 0)},
            "rain": {"level": disturbances.get("rain", 0), "duration": active_duration("rain", 0)},
        }
        self.logger.save(summary, config)
        return summary

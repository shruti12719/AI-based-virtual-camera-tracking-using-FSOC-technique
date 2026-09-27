"""Web adapter for the supplied FSOC 2D simulator.

The classes in ``sim``, ``vision``, ``control`` and ``disturbance`` are copied
unchanged from the supplied project.  This module only runs that pipeline and
serializes its real state for the browser; it does not fabricate a second
simulation in JavaScript.
"""

from __future__ import annotations

import base64
import copy
import math
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from control.ptz_controller import compute_delta
from disturbance.manager import DisturbanceManager
from sim.overlay import draw_crosshair
from sim.scene import VirtualScene
from sim.virtual_camera import VirtualPTZCamera
from vision.classical_detector import detect_beacon_classical, score_candidate
from vision.kalman_tracker import BeaconKalmanTracker
from vision.preprocess import denoise_for_detection

from .analytics_service import AnalyticsService


FRAME_W, FRAME_H = 640, 480
PRIMARY_ID = "BEACON-PRIMARY"
LEVELS = {"OFF": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}

DEFAULT_CONFIG: dict[str, Any] = {
    "motion": {"pattern": "circular", "speed": 1.0, "acceleration": 1.0, "altitude": 20.0, "distance": 120.0, "radius": 30.0, "switch_interval": 7.0},
    "simulation": {"speed_multiplier": 1.0, "decoy_count": 4, "beacon_hidden": False},
    "camera": {"fov_horizontal": 32.0, "fov_vertical": 24.0, "pan_limit": 180.0, "tilt_limit": 70.0, "max_rate": 78.0, "alignment_threshold": 1.8, "stable_duration": 1.2},
    "tracking": {"detector": "fusion"},
    "lock": {"mode": "auto", "active_target_id": PRIMARY_ID},
    "environment": {"obstacle_enabled": False, "obstacle_center": [28.0, 6.0, 0.0], "obstacle_size": [8.0, 18.0, 16.0]},
    "disturbances": {
        "vibration": {"level": "OFF", "amplitude": 0.0, "frequency": 12.5, "x": 1.0, "y": 0.75, "z": 0.35},
        "camera_motion": {"level": "OFF", "amplitude": 0.0},
        "turbulence": {"level": "OFF"},
        "sensor_noise": 0.0, "fog": 0, "noise": 0, "jitter": 0, "rain": 0,
    },
}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def deep_merge(destination: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key not in destination:
            continue
        if isinstance(destination[key], dict) and isinstance(value, dict):
            deep_merge(destination[key], value)
        else:
            destination[key] = value


class SimulationService:
    """Runs the supplied 2D simulator and publishes its shared web state."""

    def __init__(self, analytics: AnalyticsService) -> None:
        self.analytics = analytics
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        self.optional_yolo: Any | None = None
        self.reset(new_session=False)

    def reset(self, new_session: bool = True) -> None:
        self.running = False
        self.time_s = 0.0
        self.frame = 0
        self.scene = VirtualScene(pattern=self.config["motion"]["pattern"], n_decoys=int(self.config["simulation"]["decoy_count"]))
        self.full_frame, start = self.scene.render()
        self.camera = VirtualPTZCamera()
        self.camera.pan_x, self.camera.tilt_y = start
        self.screen_center = (self.camera.fov_w // 2, self.camera.fov_h // 2)
        self.tracker = BeaconKalmanTracker(init_offset=(0, 0), max_coast_frames=None)
        self.disturbance_mgr = DisturbanceManager()
        self._apply_disturbance_config()
        self.beacon_hidden = bool(self.config["simulation"]["beacon_hidden"])
        self.reacquire_active = False
        self.reacquire_target_world: tuple[float, float] | None = None
        self.reacquire_offset: tuple[float, float] | None = None
        self.kalman_prediction_world: tuple[float, float] | None = None
        self.last_true_world = (float(start[0]), float(start[1]))
        self.last_world = self.last_true_world
        self.last_velocity = (0.0, 0.0)
        self.last_measurement: tuple[float, float] | None = None
        self.last_tracked: tuple[float, float] | None = None
        self.detected = self.locked = False
        self.search_state = "READY"
        self.source = "KALMAN"
        self.display_source = "KALMAN"
        self.pending_source = "KALMAN"
        self.source_hold_count = 0
        self.display_confidence = 0.0
        self.sim_assist_active = False
        self.trajectories: dict[str, list[list[float]]] = {PRIMARY_ID: []}
        self.camera_trajectory: list[list[float]] = []
        self.last_image = self._camera_image(self.camera.crop(self.full_frame), None, None, False)
        if new_session:
            self.analytics.start(self.config)

    def restore_defaults(self) -> None:
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        self.optional_yolo = None
        self.reset(new_session=True)

    def _apply_disturbance_config(self) -> None:
        d = self.config["disturbances"]
        sensor = int(round(clamp(float(d.get("sensor_noise", 0.0)), 0.0, 0.35) / 0.35 * 3))
        vibration = LEVELS.get(str(d.get("vibration", {}).get("level", "OFF")).upper(), 0)
        motion = LEVELS.get(str(d.get("camera_motion", {}).get("level", "OFF")).upper(), 0)
        turbulence = LEVELS.get(str(d.get("turbulence", {}).get("level", "OFF")).upper(), 0)
        levels = {
            "fog": int(clamp(float(d.get("fog", turbulence)), 0, 3)),
            "noise": int(clamp(float(d.get("noise", sensor)), 0, 3)),
            "jitter": int(clamp(float(d.get("jitter", max(vibration, motion))), 0, 3)),
            "rain": int(clamp(float(d.get("rain", turbulence)), 0, 3)),
        }
        for category, level in levels.items():
            self.disturbance_mgr.set_level(category, level)
            d[category] = level

    def configure(self, patch: dict[str, Any]) -> None:
        previous_hidden = bool(self.config["simulation"]["beacon_hidden"])
        previous_decoys = int(self.config["simulation"]["decoy_count"])
        deep_merge(self.config, patch)
        motion = self.config["motion"]
        requested = str(motion["pattern"])
        motion["pattern"] = requested if requested in {"circular", "figure8", "straight", "random", "auto"} else "circular"
        motion["speed"] = clamp(float(motion["speed"]), 0.2, 3.0)
        self.scene.angular_speed = 0.4 * motion["speed"]
        if motion["pattern"] == "auto":
            self.scene.enable_auto_rotate()
        else:
            self.scene.disable_auto_rotate()
            self.scene.set_pattern(motion["pattern"])
        simulation = self.config["simulation"]
        simulation["speed_multiplier"] = clamp(float(simulation["speed_multiplier"]), 0.25, 4.0)
        simulation["decoy_count"] = int(clamp(float(simulation["decoy_count"]), 0, 10))
        if simulation["decoy_count"] != previous_decoys:
            self.scene.regenerate_decoys(simulation["decoy_count"])
            self.analytics.add_event(self.time_s, f"Decoy count set to {simulation['decoy_count']}", "scenario")
        self._apply_disturbance_config()
        requested_hidden = bool(simulation["beacon_hidden"])
        if requested_hidden != previous_hidden:
            self.config["simulation"]["beacon_hidden"] = previous_hidden
            self.toggle_beacon()
        if str(self.config["tracking"].get("detector")) == "yolo" and self.optional_yolo is None:
            try:
                from vision.yolo_detector import YoloBeaconDetector
                self.optional_yolo = YoloBeaconDetector(str(Path(__file__).resolve().parents[1] / "beacon_yolo.pt"))
                self.analytics.add_event(self.time_s, "YOLO detector loaded", "tracking")
            except Exception as error:
                self.config["tracking"]["detector"] = "fusion"
                self.analytics.add_event(self.time_s, f"YOLO unavailable; using classical fusion ({error.__class__.__name__})", "system")

    def set_target(self, target_id: str) -> None:
        if target_id != PRIMARY_ID:
            self.analytics.add_event(self.time_s, f"{target_id} is a visual decoy and cannot control PTZ", "tracking")
            return
        self.config["lock"]["active_target_id"] = PRIMARY_ID

    def set_lock_mode(self, mode: str) -> None:
        if mode in {"auto", "manual"}:
            self.config["lock"]["mode"] = mode
            self.analytics.add_event(self.time_s, f"{mode.title()} primary lock selected", "tracking")

    def toggle_beacon(self) -> None:
        if not self.beacon_hidden:
            self.beacon_hidden = True
            self.config["simulation"]["beacon_hidden"] = True
            self.reacquire_active = False
            self.reacquire_offset = None
            self.reacquire_target_world = None
            self.search_state = "PREDICTING"
            self.analytics.add_event(self.time_s, "Primary beacon hidden; world Kalman prediction active", "tracking")
            return
        self.beacon_hidden = False
        self.config["simulation"]["beacon_hidden"] = False
        self.reacquire_target_world = self.kalman_prediction_world
        self.reacquire_active = self.reacquire_target_world is not None
        self.reacquire_offset = None
        self.search_state = "REACQUIRING" if self.reacquire_active else "SEEKING"
        self.analytics.add_event(self.time_s, "Primary beacon restored at its latest Kalman world prediction" if self.reacquire_active else "Primary beacon restored; awaiting first optical lock", "tracking")

    @staticmethod
    def _remove_beacon(frame: np.ndarray, position: tuple[float, float]) -> np.ndarray:
        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        cv2.circle(mask, tuple(map(int, position)), 26, 255, -1)
        return cv2.inpaint(frame, mask, 5, cv2.INPAINT_TELEA)

    def _relocate_beacon(self, frame: np.ndarray, raw: tuple[float, float], target: tuple[float, float]) -> np.ndarray:
        """Use the supplied rendered optical signal, moved to Kalman's world point."""
        image = frame.copy()
        ox, oy = map(lambda value: int(round(value)), raw)
        tx, ty = map(lambda value: int(round(value)), target)
        radius, h, w = 28, *image.shape[:2]
        x0, x1, y0, y1 = max(0, ox - radius), min(w, ox + radius + 1), max(0, oy - radius), min(h, oy + radius + 1)
        patch = image[y0:y1, x0:x1].copy()
        if patch.size == 0:
            return image
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        alpha = cv2.inRange(hsv, np.array([0, 0, 150], np.uint8), np.array([180, 110, 255], np.uint8))
        alpha = cv2.GaussianBlur(alpha, (5, 5), 0)
        image = self._remove_beacon(image, raw)
        px0, py0 = tx - (ox - x0), ty - (oy - y0)
        px1, py1 = px0 + patch.shape[1], py0 + patch.shape[0]
        dx0, dy0, dx1, dy1 = max(0, px0), max(0, py0), min(w, px1), min(h, py1)
        if dx1 <= dx0 or dy1 <= dy0:
            return image
        sx0, sy0 = dx0 - px0, dy0 - py0
        source = patch[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)].astype(np.float32)
        blend = alpha[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)].astype(np.float32)[..., None] / 255.0
        destination = image[dy0:dy1, dx0:dx1].astype(np.float32)
        image[dy0:dy1, dx0:dx1] = (source * blend + destination * (1 - blend)).astype(np.uint8)
        return image

    @staticmethod
    def _data_url(image: np.ndarray) -> str:
        # The simulation's detector consumes the native PTZ crop.  Only this
        # display copy is enlarged and high-quality encoded for the browser,
        # keeping the optical boresight legible without changing detection.
        display = cv2.resize(image, None, fx=3, fy=3, interpolation=cv2.INTER_LANCZOS4)
        ok, encoded = cv2.imencode(".jpg", display, [cv2.IMWRITE_JPEG_QUALITY, 94])
        return "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("ascii") if ok else ""

    def _world3(self, point: tuple[float, float] | None) -> list[float] | None:
        if point is None:
            return None
        return [round((float(point[0]) - FRAME_W / 2) * .26, 3), 5.0, round((FRAME_H / 2 - float(point[1])) * .22, 3)]

    def _camera_image(self, cropped: np.ndarray, tracked: tuple[float, float] | None, measurement: tuple[float, float] | None, hidden: bool) -> str:
        image = cropped.copy()
        draw_crosshair(image, self.screen_center, size=14, gap=5, color=(0, 255, 255), thickness=1)
        if tracked is not None:
            point = tuple(map(int, tracked))
            color = (235, 180, 95) if hidden else (0, 255, 0)
            cv2.circle(image, point, 18 if hidden else 12, color, 2)
            if hidden:
                cv2.line(image, (point[0] - 25, point[1]), (point[0] + 25, point[1]), color, 2)
                cv2.line(image, (point[0], point[1] - 25), (point[0], point[1] + 25), color, 2)
        if measurement is not None and not hidden:
            mx, my = map(int, measurement)
            cv2.rectangle(image, (mx - 17, my - 17), (mx + 17, my + 17), (130, 105, 255), 1)
        return self._data_url(image)

    def _hysteresis(self, source: str, confidence: float) -> tuple[str, float]:
        alpha = .12
        self.display_confidence = confidence if self.frame <= 1 else alpha * confidence + (1 - alpha) * self.display_confidence
        source = source.upper()
        if source == self.display_source:
            self.pending_source, self.source_hold_count = source, 0
        elif source == self.pending_source:
            self.source_hold_count += 1
        else:
            self.pending_source, self.source_hold_count = source, 1
        if self.source_hold_count >= 5:
            self.display_source, self.source_hold_count = self.pending_source, 0
        return self.display_source, float(clamp(self.display_confidence, 0, 1))

    def _segment_hits_obstacle(self, end: list[float]) -> bool:
        if not self.config["environment"]["obstacle_enabled"]:
            return False
        center = self.config["environment"]["obstacle_center"]
        size = self.config["environment"]["obstacle_size"]
        # A deliberately conservative 2D LOS test for the visual obstacle.
        for fraction in np.linspace(.05, 1.0, 60):
            point = [end[0] * fraction, 5.0, end[2] * fraction]
            if all(abs(point[index] - center[index]) <= size[index] / 2 for index in range(3)):
                return True
        return False

    def step(self, dt: float) -> dict[str, Any]:
        started = time.perf_counter()
        dt = clamp(float(dt), .005, .1)
        if not self.running:
            return self._payload(dt, 0.0, None, None, self.last_tracked, False)

        scaled_dt = dt * float(self.config["simulation"]["speed_multiplier"])
        # VirtualScene owns the real trajectory and decoy updates.
        self.scene._last_time -= max(0.0, scaled_dt - dt)
        full_frame, raw = self.scene.render()
        raw_world = (float(raw[0]), float(raw[1]))
        true_world = raw_world
        if self.reacquire_active:
            if self.reacquire_offset is None and self.reacquire_target_world is not None:
                self.reacquire_offset = (self.reacquire_target_world[0] - raw_world[0], self.reacquire_target_world[1] - raw_world[1])
            if self.reacquire_offset is not None:
                true_world = (raw_world[0] + self.reacquire_offset[0], raw_world[1] + self.reacquire_offset[1])
                full_frame = self._relocate_beacon(full_frame, raw_world, true_world)
        if self.beacon_hidden:
            full_frame = self._remove_beacon(full_frame, true_world)
        full_frame = self.disturbance_mgr.apply_to_frame(full_frame)
        cropped = self.camera.crop(full_frame)
        local_truth = (int(round(true_world[0] - (self.camera.pan_x - self.camera.fov_w / 2))), int(round(true_world[1] - (self.camera.tilt_y - self.camera.fov_h / 2))))
        fov_ok = 0 <= local_truth[0] < self.camera.fov_w and 0 <= local_truth[1] < self.camera.fov_h

        yolo_pos: tuple[int, int] | None = None
        classical_pos: tuple[int, int] | None = None
        yolo_score = classical_score = 0.0
        input_frame = denoise_for_detection(cropped) if any(self.disturbance_mgr.state.values()) else cropped
        gray = cv2.cvtColor(input_frame, cv2.COLOR_BGR2GRAY)
        if not self.beacon_hidden:
            try:
                classical_pos, classical_score = detect_beacon_classical(input_frame, gray=gray)
            except Exception:
                classical_pos, classical_score = None, 0.0
            if self.optional_yolo is not None:
                try:
                    yolo_pos, _ = self.optional_yolo.detect(input_frame)
                    if yolo_pos is not None:
                        yolo_score = score_candidate(gray, yolo_pos[0], yolo_pos[1])
                except Exception:
                    yolo_pos, yolo_score = None, 0.0
        candidates = [(point, score, source) for point, score, source in ((yolo_pos, yolo_score, "YOLO"), (classical_pos, classical_score, "CLASSICAL")) if point is not None and score >= .5]
        measurement: tuple[float, float] | None = None
        tracked: tuple[float, float] | None = None
        confidence = 0.0
        self.sim_assist_active = False
        if candidates and not self.beacon_hidden:
            local, score, source = max(candidates, key=lambda item: item[1])
            world = (float(self.camera.pan_x) + local[0] - self.screen_center[0], float(self.camera.tilt_y) + local[1] - self.screen_center[1])
            tracked, kf_conf = self.tracker.update(world)
            measurement, confidence = (float(local[0]), float(local[1])), max(float(score), float(kf_conf))
            self.source, self.detected, self.locked = source, True, True
            self.kalman_prediction_world = tracked
        elif self.beacon_hidden:
            tracked, confidence = self.tracker.update(None)
            self.kalman_prediction_world = tracked
            self.source, self.detected, self.locked, self.search_state = "KALMAN", False, tracked is not None, "PREDICTING"
        elif self.reacquire_active and self.reacquire_target_world is not None:
            tracked, confidence = self.tracker.update(self.reacquire_target_world)
            self.kalman_prediction_world = tracked
            self.source, self.detected, self.locked, self.search_state = "KALMAN-REACQUIRED", True, tracked is not None, "LOCKED"
            self.reacquire_active = False
            self.reacquire_target_world = None
        elif fov_ok:
            # Preserve the source simulator-assisted recovery behavior when optics fail.
            assist = (float(self.camera.pan_x) + local_truth[0] - self.screen_center[0], float(self.camera.tilt_y) + local_truth[1] - self.screen_center[1])
            tracked, confidence = self.tracker.update(assist)
            self.source, self.detected, self.locked, self.sim_assist_active = "SIM-ASSIST", False, tracked is not None, True
            self.kalman_prediction_world = tracked
        else:
            self.source, self.detected, self.locked, self.search_state = "WORLD-GUIDE", False, False, "SEEKING"

        if tracked is not None:
            local_tracked = (float(tracked[0]) - self.camera.pan_x + self.screen_center[0], float(tracked[1]) - self.camera.tilt_y + self.screen_center[1])
            dx, dy = compute_delta(local_tracked, self.screen_center, gain=.45)
            self.camera.apply_delta(dx, dy)
            self.search_state = "PREDICTING" if self.beacon_hidden else "LOCKED"
            pixel_error = math.hypot(local_tracked[0] - self.screen_center[0], local_tracked[1] - self.screen_center[1])
        else:
            local_tracked = None
            self.camera.apply_delta((true_world[0] - self.camera.pan_x) * .60, (true_world[1] - self.camera.tilt_y) * .60)
            pixel_error = float("nan")
        self.frame += 1
        self.time_s += scaled_dt
        self.last_true_world, self.last_tracked = true_world, tracked
        source, confidence = self._hysteresis(self.source, float(confidence))
        self.last_image = self._camera_image(cropped, local_tracked, measurement, self.beacon_hidden)
        processing_ms = (time.perf_counter() - started) * 1000
        return self._payload(dt, processing_ms, measurement, local_tracked, tracked, fov_ok, pixel_error=pixel_error, source=source, confidence=confidence)

    def _payload(self, dt: float, processing_ms: float, measurement: tuple[float, float] | None, local_tracked: tuple[float, float] | None, tracked: tuple[float, float] | None, fov_ok: bool, *, pixel_error: float | None = None, source: str | None = None, confidence: float | None = None) -> dict[str, Any]:
        true_3d = self._world3(self.last_true_world) or [0.0, 5.0, 0.0]
        tracked_3d = self._world3(tracked)
        current_3d = tracked_3d if self.beacon_hidden and tracked_3d else true_3d
        decoys = []
        trajectories: dict[str, list[list[float]]] = self.trajectories
        for index, decoy in enumerate(self.scene._decoys, 1):
            point = self._world3((float(decoy["x"]), float(decoy["y"]))) or [0.0, 5.0, 0.0]
            decoys.append({"id": f"DECOY-{index:02d}", "role": "decoy", "position": point, "velocity": [0.0, 0.0, 0.0], "confidence": 0.0, "visible": True, "active": False, "optical_visible": True, "bounding_box": None, "centroid": None})
            trajectories.setdefault(f"DECOY-{index:02d}", []).append(point)
            trajectories[f"DECOY-{index:02d}"] = trajectories[f"DECOY-{index:02d}"][-120:]
        trajectories[PRIMARY_ID].append(current_3d)
        trajectories[PRIMARY_ID] = trajectories[PRIMARY_ID][-180:]
        camera_position = [0.0, 5.0, 0.0]
        self.camera_trajectory.append(camera_position)
        self.camera_trajectory = self.camera_trajectory[-120:]
        target_bearing = math.degrees(math.atan2(current_3d[2], current_3d[0] or .0001))
        camera_bearing = math.degrees(math.atan2((FRAME_H / 2 - self.camera.tilt_y) * .22, (self.camera.pan_x - FRAME_W / 2) * .26 or .0001))
        distance = float(self.scene.estimate_distance_m() or math.hypot(current_3d[0], current_3d[2]))
        angular_error = abs(target_bearing - camera_bearing)
        los_clear = not self._segment_hits_obstacle(current_3d)
        source = source or self.display_source
        confidence = float(confidence if confidence is not None else self.display_confidence)
        pixel_error = float(pixel_error if pixel_error is not None and math.isfinite(pixel_error) else (math.hypot(local_tracked[0] - self.screen_center[0], local_tracked[1] - self.screen_center[1]) if local_tracked else 0.0))
        fsoc_link = bool(self.locked and not self.beacon_hidden and fov_ok and los_clear and pixel_error < 18)
        bbox = [local_tracked[0] - 18, local_tracked[1] - 18, 36, 36] if local_tracked and not self.beacon_hidden else None
        primary = {"id": PRIMARY_ID, "role": "primary", "position": current_3d, "velocity": [0.0, 0.0, 0.0], "confidence": confidence, "visible": not self.beacon_hidden, "active": True, "optical_visible": not self.beacon_hidden, "bounding_box": bbox, "centroid": list(local_tracked) if local_tracked and not self.beacon_hidden else None}
        disturbance_level = sum(int(value) for value in self.disturbance_mgr.state.values())
        row = {"timestamp": self.time_s, "dt": dt, "target_id": PRIMARY_ID, "detected": self.detected, "locked": self.locked, "fov_ok": fov_ok, "los_clear": los_clear, "fsoc_link": fsoc_link, "target_azimuth": target_bearing, "target_elevation": 0.0, "camera_pan": camera_bearing, "camera_tilt": 0.0, "pixel_error": pixel_error, "angular_error": angular_error, "azimuth_error": target_bearing - camera_bearing, "elevation_error": 0.0, "pan_error": target_bearing - camera_bearing, "tilt_error": 0.0, "confidence": confidence, "distance": distance, "fps": round(1 / dt, 2) if dt else 0.0, "processing_time_ms": processing_ms, "disturbance_level": disturbance_level, "beacon_hidden": self.beacon_hidden, "platform_vibration": self.config["disturbances"]["vibration"]["level"], "camera_motion": self.config["disturbances"]["camera_motion"]["level"], "atmospheric_turbulence": self.config["disturbances"]["turbulence"]["level"], "sensor_noise": self.config["disturbances"]["sensor_noise"], "fog": self.config["disturbances"]["fog"], "noise": self.config["disturbances"]["noise"], "jitter": self.config["disturbances"]["jitter"], "rain": self.config["disturbances"]["rain"]}
        if self.running:
            self.analytics.record(row)
        return {"type": "telemetry", "timestamp": round(self.time_s, 3), "running": self.running, "active_target_id": PRIMARY_ID, "primary_target_id": PRIMARY_ID, "lock_mode": self.config["lock"]["mode"], "uav1": {"id": "FSOC-TERMINAL", "position": camera_position}, "targets": [primary, *decoys], "camera": {"pan": camera_bearing, "tilt": 0.0, "commanded_pan": camera_bearing, "commanded_tilt": 0.0, "fov_horizontal": self.config["camera"]["fov_horizontal"], "fov_vertical": self.config["camera"]["fov_vertical"]}, "target_angles": {"azimuth": target_bearing, "elevation": 0.0, "distance": distance}, "tracking": {"pixel_error": pixel_error, "angular_error": angular_error, "azimuth_error": target_bearing - camera_bearing, "elevation_error": 0.0, "confidence": confidence, "detector": source, "detected": self.detected, "locked": self.locked, "predicted": list(local_tracked) if local_tracked else None, "predicted_world": tracked_3d, "measured": list(measurement) if measurement else None, "prediction_active": self.beacon_hidden, "alignment_stable": fsoc_link}, "system": {"fps": round(1 / dt, 2) if dt else 0.0, "processing_time_ms": round(processing_ms, 2), "fov_ok": fov_ok, "los_clear": los_clear, "fsoc_link": fsoc_link, "link_reason": "FSOC link active" if fsoc_link else "Optical beacon intentionally hidden; Kalman world prediction continues" if self.beacon_hidden else "Waiting for a stable optical lock"}, "disturbances": self.config["disturbances"], "environment": self.config["environment"], "simulation": {"speed_multiplier": self.config["simulation"]["speed_multiplier"], "decoy_count": self.config["simulation"]["decoy_count"], "beacon_hidden": self.beacon_hidden, "active_pattern": self.scene.pattern}, "camera_view": {"width": self.camera.fov_w, "height": self.camera.fov_h, "image": self.last_image, "beacon_hidden": self.beacon_hidden}, "trajectories": trajectories, "camera_trajectory": self.camera_trajectory, "history": self.analytics.history, "events": self.analytics.events, "performance": self.analytics.summary(), "config": self.config}

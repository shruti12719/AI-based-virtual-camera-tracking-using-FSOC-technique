export type Vec3 = [number, number, number]

export interface Disturbances {
  vibration: { level: string; amplitude: number; frequency: number; x: number; y: number; z: number }
  camera_motion: { level: string; amplitude: number }
  turbulence: { level: string }
  sensor_noise: number
  fog: number
  noise: number
  jitter: number
  rain: number
}

export interface AppConfig {
  motion: { pattern: string; speed: number; acceleration: number; altitude: number; distance: number; radius: number; switch_interval: number }
  simulation: { speed_multiplier: number; decoy_count: number; beacon_hidden: boolean }
  camera: { fov_horizontal: number; fov_vertical: number; pan_limit: number; tilt_limit: number; max_rate: number; alignment_threshold: number; stable_duration: number }
  tracking: { detector: string }
  lock: { mode: 'auto' | 'manual'; active_target_id: string }
  environment: { obstacle_enabled: boolean; obstacle_center: Vec3; obstacle_size: Vec3 }
  disturbances: Disturbances
}

export interface Target {
  id: string
  role: 'primary' | 'decoy'
  position: Vec3
  velocity: Vec3
  confidence: number
  visible: boolean
  active: boolean
  optical_visible: boolean
  bounding_box: [number, number, number, number] | null
  centroid: [number, number] | null
}

export interface HistoryPoint {
  timestamp: number
  target_azimuth: number
  target_elevation: number
  camera_pan: number
  camera_tilt: number
  pixel_error: number
  angular_error: number
  pan_error: number
  tilt_error: number
  confidence: number
  distance: number
  fps: number
  processing_time_ms: number
  disturbance_level: number
  fsoc_link: boolean
  beacon_hidden: boolean
}

export interface PerformanceSummary {
  session_id: string
  duration: number
  average_fps: number
  minimum_fps: number
  maximum_fps: number
  acquisition_time?: number | null
  average_tracking_error: number
  maximum_tracking_error: number
  average_processing_time: number
  maximum_processing_time: number
  average_detection_confidence: number
  target_loss_count: number
  lock_retention_rate: number
  fov_compliance: number
  los_availability: number
  fsoc_link_retention_rate: number
  total_frames_processed?: number
  rms_tracking_error?: number
  [key: string]: number | string | boolean | Record<string, unknown> | null | undefined
}

export interface Telemetry {
  type: 'telemetry'
  timestamp: number
  running: boolean
  active_target_id: string
  primary_target_id: string
  lock_mode: 'auto' | 'manual'
  uav1: { id: string; position: Vec3 }
  targets: Target[]
  camera: { pan: number; tilt: number; commanded_pan: number; commanded_tilt: number; fov_horizontal: number; fov_vertical: number }
  target_angles: { azimuth: number; elevation: number; distance: number }
  tracking: { pixel_error: number; angular_error: number; azimuth_error: number; elevation_error: number; confidence: number; detector: string; detected: boolean; locked: boolean; predicted: [number, number] | null; predicted_world: Vec3 | null; measured: [number, number] | null; prediction_active: boolean; alignment_stable: boolean }
  system: { fps: number; processing_time_ms: number; fov_ok: boolean; los_clear: boolean; fsoc_link: boolean; link_reason: string }
  disturbances: Disturbances
  environment: { obstacle_enabled: boolean; obstacle_center: Vec3; obstacle_size: Vec3 }
  simulation: { speed_multiplier: number; decoy_count: number; beacon_hidden: boolean; active_pattern: string }
  camera_view: { width: number; height: number; image: string; beacon_hidden: boolean }
  trajectories: Record<string, Vec3[]>
  camera_trajectory: Vec3[]
  history: HistoryPoint[]
  events: { timestamp: number; message: string; category: string }[]
  performance: PerformanceSummary
  config: AppConfig
}

export type DeepPartial<T> = { [K in keyof T]?: T[K] extends object ? DeepPartial<T[K]> : T[K] }
export type Command =
  | { action: 'start' | 'pause' | 'reset' | 'reset_defaults' | 'toggle_beacon' | 'generate_report' }
  | { action: 'configure'; config: DeepPartial<AppConfig> }
  | { action: 'set_target'; target_id: string }
  | { action: 'set_lock_mode'; lock_mode: 'auto' | 'manual' }

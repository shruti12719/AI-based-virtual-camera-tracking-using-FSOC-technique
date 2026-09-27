import './boresight.css'
import type { Telemetry } from '../types/simulation'

type MarkerType = 'actual' | 'measured' | 'predicted'

function Marker({ point, type, label, state }: { point: [number, number] | null; type: MarkerType; label: string; state: Telemetry }) {
  if (!point) return null
  return <span aria-label={`${label} target position`} className={`camera-marker ${type}`} style={{ left: `${point[0] / state.camera_view.width * 100}%`, top: `${point[1] / state.camera_view.height * 100}%` }}><span>{label}</span></span>
}

export function CameraView({ state }: { state: Telemetry }) {
  const hidden = state.simulation.beacon_hidden
  const primary = state.targets.find((target) => target.role === 'primary')
  const box = primary?.bounding_box
  const prediction = state.tracking.predicted
  const headline = hidden ? prediction ? 'PREDICTIVE TRACK' : 'ESTIMATE UNAVAILABLE' : state.tracking.locked ? 'PRIMARY LOCKED' : state.tracking.detected ? 'PRIMARY DETECTED' : 'ACQUIRING PRIMARY'
  const signal = hidden ? 'OPTICAL SIGNAL MASKED' : state.tracking.detected ? 'OPTICAL DETECTION LIVE' : 'SEARCHING OPTICAL FIELD'
  const marker = hidden ? prediction : state.tracking.measured ?? prediction
  const pixelError = marker ? Math.hypot(marker[0] - state.camera_view.width / 2, marker[1] - state.camera_view.height / 2) : null
  const source = hidden ? 'WORLD KALMAN' : state.tracking.detector.toUpperCase()

  return <section className="panel camera-panel"><header className="panel-head camera-panel-head"><div><span className="eyebrow">CAM-01 / image-forming optical sensor</span><h2>2D optical boresight</h2></div><span className={`status-tag ${hidden ? 'predicting' : state.tracking.locked ? 'good' : 'warn'}`}>{headline}</span></header>
    <div className={`camera-frame boresight-frame ${hidden ? 'prediction-mode' : ''}`}>
      {state.camera_view.image ? <img src={state.camera_view.image} alt="Live Python-generated FSOC camera observation" /> : <div className="camera-empty">Preparing optical camera stream</div>}
      <span className="camera-scanlines" /><span className="camera-vignette" /><span className="boresight-grid" aria-hidden="true"><i /><i /><i /><i /></span>
      <span className="camera-crosshair" aria-label="Boresight centre"><i /></span>
      <div className="boresight-topline"><span>CAM-01 / BORESIGHT</span><span>{source}</span></div>
      {!hidden && <Marker point={primary?.centroid ?? null} type="actual" label="OPTICAL" state={state} />}
      {!hidden && <Marker point={state.tracking.measured} type="measured" label="DETECTED" state={state} />}
      {prediction && <Marker point={prediction} type="predicted" label={hidden ? 'KALMAN' : 'PREDICTED'} state={state} />}
      {box && !hidden && <span className="detection-box" aria-label="Detected beacon boundary" style={{ left: `${box[0] / state.camera_view.width * 100}%`, top: `${box[1] / state.camera_view.height * 100}%`, width: `${box[2] / state.camera_view.width * 100}%`, height: `${box[3] / state.camera_view.height * 100}%` }} />}
      <div className="boresight-readout left"><strong>{primary?.id ?? 'PRIMARY_BEACON'}</strong><span>{signal}</span><span>{hidden ? 'TRACK MODE: KALMAN' : `CONFIDENCE: ${state.tracking.confidence.toFixed(2)}`}</span></div>
      <div className="boresight-readout right"><span>PAN {state.camera.pan.toFixed(2)}&deg;</span><span>TILT {state.camera.tilt.toFixed(2)}&deg;</span><span>RANGE {state.target_angles.distance.toFixed(1)} M</span></div>
      <div className="boresight-status"><span>{state.system.fov_ok ? 'FOV IN LIMITS' : 'FOV EXCEEDED'}</span><span>{state.system.los_clear ? 'LOS CLEAR' : 'LOS BLOCKED'}</span><span>{pixelError === null ? 'ERR --' : `ERR ${pixelError.toFixed(1)} PX`}</span></div>
    </div>
    <footer className="camera-legend boresight-legend"><span><i className="actual" />Optical beacon</span><span><i className="measured" />Detected centroid</span><span><i className="predicted" />Kalman prediction</span><span className={hidden ? 'legend-note predicting' : 'legend-note'}>{hidden ? 'Optical beacon hidden — blue track is estimated' : 'Reticle centred on commanded boresight'}</span></footer>
  </section>
}

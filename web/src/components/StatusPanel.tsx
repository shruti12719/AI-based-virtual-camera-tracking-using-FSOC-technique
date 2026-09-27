import type { Telemetry } from '../types/simulation'

function Status({ label, value, positive, predicting = false }: { label: string; value: string; positive: boolean; predicting?: boolean }) {
  return <article className={`status-card ${positive ? 'positive' : 'negative'} ${predicting ? 'predicting' : ''}`}><span>{label}</span><strong><i />{value}</strong></article>
}

function Readout({ label, value }: { label: string; value: string }) { return <div className="readout"><span>{label}</span><strong>{value}</strong></div> }

export function StatusPanel({ state }: { state: Telemetry }) {
  const primaryMode = state.simulation.beacon_hidden ? 'PREDICTING' : state.tracking.locked ? 'LOCKED' : state.tracking.detected ? 'DETECTED' : 'SEARCHING'
  return <aside className="status-stack">
    <section className="panel status-panel"><div className="panel-title">Mission status</div><div className="status-grid">
      <Status label="Primary beacon" value={primaryMode} positive={state.tracking.detected || state.tracking.prediction_active} predicting={state.simulation.beacon_hidden} />
      <Status label="Camera FOV" value={state.system.fov_ok ? 'IN VIEW' : 'OUT OF VIEW'} positive={state.system.fov_ok} />
      <Status label="Line of sight" value={state.system.los_clear ? 'CLEAR' : 'BLOCKED'} positive={state.system.los_clear} />
      <Status label="FSOC link" value={state.system.fsoc_link ? 'ACTIVE' : 'PENDING'} positive={state.system.fsoc_link} />
      <Status label="Kalman" value={state.tracking.prediction_active ? 'COASTING' : 'CORRECTING'} positive={state.tracking.prediction_active || state.tracking.detected} predicting={state.tracking.prediction_active} />
      <Status label="Scenario" value={state.simulation.active_pattern.toUpperCase()} positive />
    </div></section>
    <section className="panel telemetry-panel"><div className="panel-title">Live optical telemetry</div>
      <Readout label="Range" value={`${state.target_angles.distance.toFixed(1)} m`} /><Readout label="Azimuth / elevation" value={`${state.target_angles.azimuth.toFixed(2)}° / ${state.target_angles.elevation.toFixed(2)}°`} />
      <Readout label="Camera pan / tilt" value={`${state.camera.pan.toFixed(2)}° / ${state.camera.tilt.toFixed(2)}°`} /><Readout label="Angular error" value={`${state.tracking.angular_error.toFixed(2)}°`} />
      <Readout label="Image error" value={`${state.tracking.pixel_error.toFixed(2)} px`} /><Readout label="Detection confidence" value={state.tracking.confidence.toFixed(2)} />
      <Readout label="Frame rate / latency" value={`${state.system.fps.toFixed(1)} FPS / ${state.system.processing_time_ms.toFixed(2)} ms`} />
      <div className={`link-readout ${state.system.fsoc_link ? 'ready' : state.simulation.beacon_hidden ? 'predicting' : ''}`}>{state.system.link_reason}</div>
    </section>
  </aside>
}

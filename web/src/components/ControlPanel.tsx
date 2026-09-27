import type { ReactNode } from 'react'
import type { AppConfig, Command, DeepPartial, Telemetry } from '../types/simulation'

function SelectRow({ label, value, children, onChange }: { label: string; value: string | number; children: ReactNode; onChange: (value: string) => void }) {
  return <label className="control-row"><span>{label}</span><select value={value} onChange={(event) => onChange(event.target.value)}>{children}</select></label>
}

function RangeRow({ label, value, min, max, step = .01, suffix = '', onChange }: { label: string; value: number; min: number; max: number; step?: number; suffix?: string; onChange: (value: number) => void }) {
  const digits = step < 1 ? 2 : 0
  return <label className="range-row"><span>{label}<small>{value.toFixed(digits)}{suffix}</small></span><input type="range" min={min} max={max} step={step} value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>
}

export function ControlPanel({ state, send }: { state: Telemetry; send: (value: Command) => void }) {
  const config = state.config
  const update = (patch: DeepPartial<AppConfig>) => send({ action: 'configure', config: patch })
  const disturbance = config.disturbances
  return <aside className="control-stack">
    <section className="panel compact-panel"><div className="panel-title">Mission controls</div>
      <div className="button-grid four"><button className="action primary" onClick={() => send({ action: 'start' })}>Start</button><button className="action" onClick={() => send({ action: 'pause' })}>Pause</button><button className="action" onClick={() => send({ action: 'toggle_beacon' })}>{state.simulation.beacon_hidden ? 'Show beacon' : 'Hide beacon'}</button><button className="action muted" onClick={() => send({ action: 'reset' })}>Reset</button></div>
      <SelectRow label="Primary path" value={config.motion.pattern} onChange={(value) => update({ motion: { pattern: value } })}><option value="auto">Auto pattern rotation</option><option value="circular">Circular</option><option value="figure8">Figure-eight</option><option value="waypoint">Random waypoint</option></SelectRow>
      <RangeRow label="Simulation speed" value={config.simulation.speed_multiplier} min={.25} max={4} step={.25} suffix="x" onChange={(value) => update({ simulation: { speed_multiplier: value } })} />
      <RangeRow label="Primary velocity" value={config.motion.speed} min={.2} max={3} step={.1} onChange={(value) => update({ motion: { speed: value } })} />
      <RangeRow label="Auto-switch interval" value={config.motion.switch_interval} min={5} max={40} step={1} suffix=" s" onChange={(value) => update({ motion: { switch_interval: value } })} />
    </section>
    <section className="panel compact-panel"><div className="panel-title">Target & tracking</div>
      <SelectRow label="PTZ target" value={state.active_target_id} onChange={(value) => send({ action: 'set_target', target_id: value })}>{state.targets.map((target) => <option key={target.id} value={target.id}>{target.role === 'primary' ? 'PRIMARY BEACON' : `${target.id} (DECOY)`}</option>)}</SelectRow>
      <SelectRow label="Lock mode" value={state.lock_mode} onChange={(value) => send({ action: 'set_lock_mode', lock_mode: value as 'auto' | 'manual' })}><option value="auto">Auto lock primary only</option><option value="manual">Manual primary lock</option></SelectRow>
      <SelectRow label="Detector" value={config.tracking.detector} onChange={(value) => update({ tracking: { detector: value } })}><option value="bright">Image-derived beacon</option><option value="yolo">YOLO (optional)</option></SelectRow>
      <RangeRow label="Decoy targets" value={config.simulation.decoy_count} min={0} max={10} step={1} onChange={(value) => update({ simulation: { decoy_count: value } })} />
      <p className="control-note">Decoys are visible in both views but cannot take control of the optical PTZ loop.</p>
    </section>
    <section className="panel compact-panel"><div className="panel-title">Disturbance envelope</div>
      <SelectRow label="Platform vibration" value={disturbance.vibration.level} onChange={(value) => update({ disturbances: { vibration: { level: value } } })}><option>OFF</option><option>LOW</option><option>MEDIUM</option><option>HIGH</option></SelectRow>
      <SelectRow label="Camera motion" value={disturbance.camera_motion.level} onChange={(value) => update({ disturbances: { camera_motion: { level: value } } })}><option>OFF</option><option>LOW</option><option>MEDIUM</option><option>HIGH</option></SelectRow>
      <SelectRow label="Atmospheric turbulence" value={disturbance.turbulence.level} onChange={(value) => update({ disturbances: { turbulence: { level: value } } })}><option>OFF</option><option>LOW</option><option>MEDIUM</option><option>HIGH</option></SelectRow>
      <RangeRow label="Sensor noise" value={disturbance.sensor_noise} min={0} max={.35} step={.01} onChange={(value) => update({ disturbances: { sensor_noise: value } })} />
      <label className="check-row"><span>Line-of-sight obstacle</span><input type="checkbox" checked={config.environment.obstacle_enabled} onChange={(event) => update({ environment: { obstacle_enabled: event.target.checked } })} /></label>
    </section>
  </aside>
}

import { useState } from 'react'
import { Analytics, Scorecard } from './components/Analytics'
import { CameraView } from './components/CameraView'
import { ControlPanel } from './components/ControlPanel'
import { Events, Reports } from './components/EventsAndReports'
import { ScenarioSettings } from './components/ScenarioSettings'
import { StatusPanel } from './components/StatusPanel'
import { useTelemetry } from './hooks/useTelemetry'
import type { Command, Telemetry } from './types/simulation'
import { WorldScene, type WorldOptions } from './three/WorldScene'

type Page = 'mission' | 'analysis' | 'reports' | 'scenarios' | 'system'
type MissionMode = 'world' | 'camera'
type DockTab = 'status' | 'controls' | 'events' | 'metrics'

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return <button className={`scene-toggle ${checked ? 'on' : ''}`} onClick={onChange}>{label}</button>
}

function MissionDock({ state, send, active, onChange }: { state: Telemetry; send: (value: Command) => void; active: DockTab; onChange: (tab: DockTab) => void }) {
  const tabs: [DockTab, string][] = [['status', 'Status'], ['controls', 'Controls'], ['events', 'Event log'], ['metrics', 'Metrics']]
  return <aside className="mission-dock" aria-label="Mission control side panels">
    <div className="dock-tabs" role="tablist" aria-label="Mission side panels">
      {tabs.map(([id, label]) => <button key={id} role="tab" aria-selected={active === id} className={active === id ? 'selected' : ''} onClick={() => onChange(id)}>{label}</button>)}
    </div>
    <div className="dock-content">
      {active === 'status' && <StatusPanel state={state} />}
      {active === 'controls' && <ControlPanel state={state} send={send} />}
      {active === 'events' && <Events state={state} />}
      {active === 'metrics' && <Scorecard state={state} />}
    </div>
  </aside>
}

function WorldView({ state, options, toggle, reset }: { state: Telemetry; options: WorldOptions; toggle: (key: keyof Omit<WorldOptions, 'resetKey'>) => void; reset: () => void }) {
  return <section className="panel scene-panel world-panel"><header className="panel-head"><div><span className="eyebrow">Terminal, FOV, beam, LOS, target trajectories</span><h2>3D mobile FSOC geometry</h2></div><span className={`status-tag ${state.system.los_clear ? 'good' : 'bad'}`}>{state.system.los_clear ? 'LOS CLEAR' : 'LOS BLOCKED'}</span></header><WorldScene state={state} options={options} /><footer className="scene-tools"><Toggle label="Grid" checked={options.grid} onChange={() => toggle('grid')} /><Toggle label="Axes" checked={options.axes} onChange={() => toggle('axes')} /><Toggle label="Target labels" checked={options.labels} onChange={() => toggle('labels')} /><Toggle label="Trajectories" checked={options.trajectories} onChange={() => toggle('trajectories')} /><Toggle label="FOV" checked={options.fov} onChange={() => toggle('fov')} /><Toggle label="Optical beam" checked={options.beam} onChange={() => toggle('beam')} /><button className="scene-toggle" onClick={reset}>Reset view</button></footer></section>
}

function SystemAbout() {
  return <section className="about-layout"><section className="panel about-hero"><span className="eyebrow">System / about</span><h2>AI-Based Virtual Camera Tracking System for Mobile FSOC Coarse Alignment</h2><p>This browser application uses one Python-authoritative simulation state. Its camera image, detector result, Kalman world prediction, PTZ response, 3D terminal geometry, LOS state, event history, analytics and engineering reports are derived from that same state.</p><div className="flow"><span>Primary beacon + decoys</span><b>→</b><span>Image-forming camera</span><b>→</b><span>Detection</span><b>→</b><span>World Kalman filter</span><b>→</b><span>PID pan / tilt</span><b>→</b><span>FSOC readiness</span></div></section><section className="about-grid"><article className="panel about-card"><h3>What the colors mean</h3><p><i className="swatch cyan" />Cyan/white: primary optical beacon and clear geometry.</p><p><i className="swatch blue" />Blue phantom: world-coordinate Kalman prediction while the beacon is hidden.</p><p><i className="swatch amber" />Amber: alignment or acquisition is still pending.</p><p><i className="swatch red" />Red: line-of-sight or link failure.</p></article><article className="panel about-card"><h3>Technical boundaries</h3><p>Atmospheric turbulence and weather are image-domain approximations for controlled engineering demonstrations; they are not a full physical optical propagation or link-budget model.</p><p>YOLO is optional. If its independent model or runtime is unavailable, the image-derived detector remains active and the simulator stays functional.</p></article><article className="panel about-card"><h3>Operator workflow</h3><p>Select a scenario, start the mission, inspect the 3D and 2D views, hide the beacon only after an optical lock, then restore it to see Kalman-continuous reacquisition. Analyze telemetry and export a PDF/CSV session report.</p></article></section></section>
}

export default function App() {
  const { state, connection, error, clearError, reportError, send } = useTelemetry()
  const [page, setPage] = useState<Page>('mission')
  const [missionMode, setMissionMode] = useState<MissionMode>('world')
  const [dockTab, setDockTab] = useState<DockTab>('status')
  const [options, setOptions] = useState<WorldOptions>({ grid: true, axes: false, labels: true, trajectories: true, fov: true, beam: true, resetKey: 0 })
  const toggle = (key: keyof Omit<WorldOptions, 'resetKey'>) => setOptions((current) => ({ ...current, [key]: !current[key] }))
  const resetView = () => setOptions((value) => ({ ...value, resetKey: value.resetKey + 1 }))
  if (!state) return <main className="loading"><div className="spinner" /><h1>FSOC MISSION CONTROL</h1><p>{connection === 'offline' ? 'Backend unavailable. Start FastAPI at http://127.0.0.1:8011.' : 'Connecting to the authoritative Python simulation...'}</p></main>
  const nav: [Page, string][] = [['mission', 'Mission control'], ['analysis', 'Performance analysis'], ['reports', 'Report sessions'], ['scenarios', 'Scenarios / settings'], ['system', 'System / about']]
  return <main className="app-shell"><header className="topbar"><div className="brand"><span>◈</span><div><h1>FSOC COARSE ALIGNMENT <em>MISSION CONTROL</em></h1><p>AI virtual camera tracking · mobile optical terminal coarse alignment</p></div></div><div className="header-states"><span><i className={`dot ${connection}`} />{connection.toUpperCase()}</span><span><i className={`dot ${state.running ? 'connected' : 'offline'}`} />{state.running ? 'SIMULATION RUNNING' : 'SIMULATION PAUSED'}</span><span>FPS {state.system.fps.toFixed(1)}</span><strong className={state.system.fsoc_link ? 'ready' : state.simulation.beacon_hidden ? 'predicting' : ''}>FSOC {state.system.fsoc_link ? 'ACTIVE' : state.simulation.beacon_hidden ? 'PREDICTING' : 'PENDING'}</strong></div></header>
    <nav className="nav-tabs">{nav.map(([id, label]) => <button className={page === id ? 'selected' : ''} onClick={() => setPage(id)} key={id}>{label}</button>)}</nav>
    {error && <div className="error-banner"><span>{error}</span><button onClick={clearError}>Dismiss</button></div>}
    {page === 'mission' && <><section className="mission-heading"><div><span className="eyebrow">Live shared simulation</span><h2>Mission control</h2></div><div className="mode-switch"><button className={missionMode === 'world' ? 'selected' : ''} onClick={() => setMissionMode('world')}>3D world view</button><button className={missionMode === 'camera' ? 'selected' : ''} onClick={() => setMissionMode('camera')}>2D camera view</button></div></section><section className={`mission-workspace ${missionMode === 'camera' ? 'camera-mode' : 'world-mode'}`}><section className="mission-view">{missionMode === 'world' ? <WorldView state={state} options={options} toggle={toggle} reset={resetView} /> : <CameraView state={state} />}</section><MissionDock state={state} send={send} active={dockTab} onChange={setDockTab} /></section></>}
    {page === 'analysis' && <><section className="page-intro"><span className="eyebrow">Recorded live session telemetry</span><h2>Performance analysis</h2><p>Charts use actual Python session samples while the mission runs; hidden-beacon intervals remain visible in the link-state chart.</p></section><Scorecard state={state} /><Analytics state={state} /></>}
    {page === 'reports' && <section className="reports-page"><Reports state={state} onError={reportError} /><Events state={state} /></section>}
    {page === 'scenarios' && <ScenarioSettings state={state} send={send} onError={reportError} />}
    {page === 'system' && <SystemAbout />}
  </main>
}

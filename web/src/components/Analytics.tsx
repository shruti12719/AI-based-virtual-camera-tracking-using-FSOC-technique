import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { HistoryPoint, Telemetry } from '../types/simulation'

type ChartLine = { dataKey: string; color: string; name: string }
type ChartDatum = HistoryPoint & { link_state: number; hidden_state: number }

function Chart({ title, data, lines, domain }: { title: string; data: ChartDatum[]; lines: ChartLine[]; domain?: [number, number] }) {
  return <article className="panel chart"><header><span>{title}</span></header><ResponsiveContainer width="100%" height={212}><LineChart data={data} margin={{ top: 11, right: 12, bottom: 0, left: -8 }}><XAxis dataKey="timestamp" tick={{ fill: '#7891a3', fontSize: 10 }} tickFormatter={(value) => `${Number(value).toFixed(0)}s`} minTickGap={35} axisLine={false} tickLine={false} /><YAxis domain={domain} tick={{ fill: '#7891a3', fontSize: 10 }} width={40} axisLine={false} tickLine={false} /><Tooltip contentStyle={{ background: '#081722', border: '1px solid #31576b', borderRadius: 6, fontSize: 11 }} labelFormatter={(value) => `${Number(value).toFixed(2)} s`} /><Line dataKey="pixel_error" stroke="transparent" dot={false} activeDot={false} isAnimationActive={false} hide />{lines.map((line) => <Line key={line.dataKey} type="monotone" dataKey={line.dataKey} name={line.name} stroke={line.color} strokeWidth={1.75} dot={false} isAnimationActive={false} />)}</LineChart></ResponsiveContainer><footer>{lines.map((line) => <span key={line.name}><i style={{ background: line.color }} />{line.name}</span>)}</footer></article>
}

const charts: { title: string; lines: ChartLine[]; domain?: [number, number] }[] = [
  { title: 'Camera vs Target Angles', lines: [{ dataKey: 'target_azimuth', color: '#75e2f6', name: 'Target azimuth' }, { dataKey: 'camera_pan', color: '#f2ad6a', name: 'Camera pan' }, { dataKey: 'target_elevation', color: '#ac94f4', name: 'Target elevation' }, { dataKey: 'camera_tilt', color: '#61d09a', name: 'Camera tilt' }] },
  { title: 'Pan Error vs Time', lines: [{ dataKey: 'pan_error', color: '#ff997c', name: 'Pan error' }] },
  { title: 'Tilt Error vs Time', lines: [{ dataKey: 'tilt_error', color: '#c5a1ff', name: 'Tilt error' }] },
  { title: 'Angular Tracking Error', lines: [{ dataKey: 'angular_error', color: '#ffd973', name: 'Angular error' }] },
  { title: 'Detection Confidence', lines: [{ dataKey: 'confidence', color: '#61d9a4', name: 'Confidence' }], domain: [0, 1] },
  { title: 'Primary Range vs Time', lines: [{ dataKey: 'distance', color: '#70baff', name: 'Range (m)' }] },
  { title: 'FSOC Link and Hidden Beacon', lines: [{ dataKey: 'link_state', color: '#61dfa1', name: 'Link active' }, { dataKey: 'hidden_state', color: '#70c5ff', name: 'Prediction-only' }], domain: [0, 1] },
  { title: 'Disturbance vs Image Error', lines: [{ dataKey: 'disturbance_level', color: '#a5b3c0', name: 'Disturbance' }, { dataKey: 'pixel_error', color: '#ff927d', name: 'Image error' }] },
]

export function Analytics({ state }: { state: Telemetry }) {
  const data: ChartDatum[] = state.history.map((point) => ({ ...point, link_state: point.fsoc_link ? 1 : 0, hidden_state: point.beacon_hidden ? 1 : 0 }))
  return <section className="chart-grid">{charts.map((chart) => <Chart key={chart.title} title={chart.title} data={data} lines={chart.lines} domain={chart.domain} />)}</section>
}

export function Scorecard({ state }: { state: Telemetry }) {
  const performance = state.performance
  const values = [
    ['Mean tracking error', `${performance.average_tracking_error?.toFixed(2) ?? '0'} px`], ['Maximum error', `${performance.maximum_tracking_error?.toFixed(2) ?? '0'} px`], ['RMS error', `${performance.rms_tracking_error?.toFixed(2) ?? '0'} px`],
    ['Acquisition time', performance.acquisition_time == null ? 'Awaiting' : `${performance.acquisition_time}s`], ['Lock retention', `${performance.lock_retention_rate?.toFixed(1) ?? '0'}%`], ['Mean confidence', `${performance.average_detection_confidence?.toFixed(2) ?? '0'}`],
    ['Target losses', `${performance.target_loss_count ?? 0}`], ['FSOC uptime', `${performance.fsoc_link_retention_rate?.toFixed(1) ?? '0'}%`], ['Max disturbance', `${state.history.reduce((max, point) => Math.max(max, point.disturbance_level), 0).toFixed(2)}`],
  ]
  return <section className="scorecard">{values.map(([label, value]) => <article className="panel score" key={label}><span>{label}</span><strong>{value}</strong></article>)}</section>
}

import { Grid, Html, Line, OrbitControls, Sparkles } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { useState } from 'react'
import * as THREE from 'three'
import type { Target, Telemetry, Vec3 } from '../types/simulation'

export interface WorldOptions { grid: boolean; axes: boolean; labels: boolean; trajectories: boolean; fov: boolean; beam: boolean; resetKey: number }

function DroneBody({ color, primary = false }: { color: string; primary?: boolean }) {
  return <>
    <mesh castShadow receiveShadow><boxGeometry args={[4.8, 1.05, 2.8]} /><meshStandardMaterial color={color} metalness={.7} roughness={.28} emissive={primary ? '#0a2636' : '#071018'} emissiveIntensity={primary ? 1.1 : .25} /></mesh>
    {[-1, 1].map((x) => [-1, 1].map((z) => <group key={`${x}-${z}`} position={[x * 2.82, 0, z * 2.05]}>
      <mesh rotation={[0, 0, z * .32]}><cylinderGeometry args={[.10, .10, 3.25, 8]} /><meshStandardMaterial color="#91a9b7" metalness={.7} /></mesh>
      <mesh position={[0, .08, 0]} rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[1.04, 1.04, .08, 14]} /><meshStandardMaterial color="#263e4d" /></mesh>
    </group>))}
  </>
}

function Tooltip({ target }: { target: Target }) {
  const title = target.role === 'primary' ? 'PRIMARY BEACON' : target.id
  const distance = Math.hypot(...target.position).toFixed(1)
  return <Html position={[0, 4.8, 0]} center distanceFactor={17} style={{ pointerEvents: 'none' }}>
    <div className={`target-tooltip ${target.role}`}><strong>{title}</strong><span>{target.role === 'primary' ? (target.optical_visible ? 'STATUS: TRACKING' : 'STATUS: PREDICTING') : 'STATUS: DECOY / UNTRACKED'}</span><span>{target.role === 'primary' ? `CONFIDENCE: ${(target.confidence * 100).toFixed(1)}%` : `DISTANCE: ${distance} m`}</span></div>
  </Html>
}

function TargetDrone({ target, labels }: { target: Target; labels: boolean }) {
  const [hovered, setHovered] = useState(false)
  const primary = target.role === 'primary'
  const beaconColor = target.optical_visible ? '#ddfbff' : primary ? '#54819b' : '#49616f'
  return <group position={target.position} onPointerOver={(event) => { event.stopPropagation(); setHovered(true) }} onPointerOut={() => setHovered(false)}>
    <DroneBody color={primary ? '#258fb5' : '#556e7d'} primary={primary} />
    <mesh><sphereGeometry args={[primary ? .82 : .42, 18, 18]} /><meshStandardMaterial color={beaconColor} emissive={beaconColor} emissiveIntensity={primary ? 2.4 : .65} /></mesh>
    {primary && <>
      <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[1.34, .06, 8, 28]} /><meshBasicMaterial color={target.optical_visible ? '#62e5e6' : '#5e8ba1'} /></mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[1.72, .025, 8, 28]} /><meshBasicMaterial color="#5bd9ef" transparent opacity={.55} /></mesh>
    </>}
    {(hovered || (labels && primary)) && <Tooltip target={target} />}
  </group>
}

function Terminal({ state }: { state: Telemetry }) {
  const pan = THREE.MathUtils.degToRad(state.camera.pan)
  const tilt = THREE.MathUtils.degToRad(state.camera.tilt)
  return <group position={state.uav1.position}>
    <DroneBody color="#2b94c4" />
    <group position={[1.5, -.76, 0]} rotation={[0, -pan, tilt]}>
      <mesh><sphereGeometry args={[.64, 18, 18]} /><meshStandardMaterial color="#d9edf3" metalness={.75} roughness={.15} /></mesh>
      <mesh position={[.70, 0, 0]} rotation={[0, 0, Math.PI / 2]}><cylinderGeometry args={[.25, .36, 1.12, 12]} /><meshStandardMaterial color="#081722" metalness={.7} /></mesh>
    </group>
    <Html position={[0, 4.5, 0]} center distanceFactor={17}><span className="world-label">UAV TRACKER / OPTICAL TERMINAL</span></Html>
  </group>
}

function Fov({ state }: { state: Telemetry }) {
  const [x, y, z] = state.uav1.position
  const radius = Math.tan(THREE.MathUtils.degToRad(state.camera.fov_horizontal / 2)) * 38
  return <group position={[x, y, z]} rotation={[0, -THREE.MathUtils.degToRad(state.camera.pan), THREE.MathUtils.degToRad(state.camera.tilt)]}>
    <mesh position={[19, 0, 0]} rotation={[0, 0, -Math.PI / 2]}><coneGeometry args={[radius, 38, 32, 1, true]} /><meshBasicMaterial color="#5ddcf4" transparent opacity={.07} side={THREE.DoubleSide} depthWrite={false} /></mesh>
    <Line points={[[0, 0, 0], [42, 0, 0]]} color="#69e5ef" transparent opacity={.9} lineWidth={1.2} />
  </group>
}

function KalmanGhost({ position }: { position: Vec3 }) {
  return <group position={position}>
    <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[1.5, .07, 8, 28]} /><meshBasicMaterial color="#65bbf2" transparent opacity={.95} /></mesh>
    <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[2.1, .025, 8, 28]} /><meshBasicMaterial color="#85d9ff" transparent opacity={.65} /></mesh>
    <Html position={[0, 3, 0]} center distanceFactor={17}><span className="world-label predicted">KALMAN WORLD PREDICTION</span></Html>
  </group>
}

function Scene({ state, options }: { state: Telemetry; options: WorldOptions }) {
  const primary = state.targets.find((target) => target.role === 'primary')
  const beamColor = state.system.fsoc_link ? '#5be4b0' : state.simulation.beacon_hidden ? '#65bbf2' : state.system.los_clear ? '#e9b763' : '#ed6d76'
  return <>
    <color attach="background" args={['#06111d']} /><fog attach="fog" args={['#06111d', 115, 340]} />
    <ambientLight intensity={.52} /><directionalLight castShadow position={[84, 130, 30]} intensity={1.55} />
    <pointLight position={primary?.position ?? [0, 0, 0]} color="#a7efff" intensity={primary?.optical_visible ? 2.2 : .24} distance={45} />
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -.68, 0]} receiveShadow><planeGeometry args={[460, 460]} /><meshStandardMaterial color="#061a29" roughness={.96} /></mesh>
    {options.grid && <Grid args={[420, 420]} cellSize={10} cellThickness={.5} cellColor="#193a4e" sectionSize={50} sectionColor="#2d708b" fadeDistance={330} infiniteGrid />}
    {options.axes && <axesHelper args={[24]} />}
    <Sparkles count={115} scale={[250, 55, 250]} size={1.2} speed={.14} color="#76c9e0" opacity={.26} />
    {state.environment.obstacle_enabled && <mesh position={state.environment.obstacle_center} castShadow receiveShadow><boxGeometry args={state.environment.obstacle_size} /><meshStandardMaterial color="#405968" transparent opacity={.87} /></mesh>}
    <Terminal state={state} />
    {state.targets.map((target) => <TargetDrone key={target.id} target={target} labels={options.labels} />)}
    {options.beam && primary && <Line points={[state.uav1.position, primary.position]} color={beamColor} transparent opacity={.9} lineWidth={2.5} />}
    {options.fov && <Fov state={state} />}
    {options.trajectories && Object.entries(state.trajectories).map(([id, points]) => points.length > 1 && <Line key={id} points={points} color={id === state.primary_target_id ? '#67dff2' : '#45677a'} transparent opacity={id === state.primary_target_id ? .76 : .22} lineWidth={id === state.primary_target_id ? 1.65 : .7} />)}
    {state.tracking.prediction_active && state.tracking.predicted_world && <KalmanGhost position={state.tracking.predicted_world} />}
    <OrbitControls makeDefault target={[78, 15, 0]} minDistance={35} maxDistance={300} maxPolarAngle={Math.PI / 2.06} />
  </>
}

export function WorldScene({ state, options }: { state: Telemetry; options: WorldOptions }) {
  return <div className="world-canvas"><Canvas key={options.resetKey} shadows dpr={[1, 1.65]} camera={{ position: [-58, 68, 152], fov: 46 }}><Scene state={state} options={options} /></Canvas></div>
}

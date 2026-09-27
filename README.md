# AI-Based Virtual Camera Tracking System for Coarse Alignment of Mobile FSOC

A software-based FSOC simulation and monitoring platform for **coarse Pointing, Acquisition and Tracking (PAT)** of mobile Free Space Optical Communication terminals.

## Features

- Three.js 3D FSOC simulation
- 2D virtual-camera / boresight view synchronized with the 3D camera
- YOLO-based beacon/target detection
- Kalman-based target prediction
- Pan/Tilt coarse-alignment control
- Primary beacon + moving decoy targets
- Circular, figure-eight and random/waypoint trajectories
- Platform vibration
- Camera motion
- Atmospheric turbulence
- Sensor/camera noise
- FOV and Line-of-Sight (LOS) monitoring
- FSOC link status
- Real-time telemetry and performance analysis
- Session logging
- PDF/CSV performance reports
- Video/replay detection mode
- Interactive 3D target hover labels

## Technology Stack

### Frontend
- React
- TypeScript
- Vite
- Three.js
- React Three Fiber
- Drei
- Recharts / Chart.js

### Backend
- Python
- FastAPI
- WebSocket
- OpenCV
- Ultralytics YOLO
- NumPy

## Architecture

```text
Python Simulation / AI
          |
       FastAPI
          |
      WebSocket
          |
     React + TS
       /     \
      /       \
 Three.js    2D Camera
  World        View
```

Both the 3D world and 2D camera view use the **same simulation state**.

## Project Structure

```text
project/
├── frontend/
├── backend/
├── vision/
├── control/
├── disturbance/
├── sim/
├── logging/
├── models/
├── data/
│   └── videos/
├── docs/
│   └── images/
│       ├── mission-control.png
│       ├── 3d-view.png
│       ├── 2d-camera.png
│       ├── performance.png
│       └── report.png
├── README.md
└── requirements.txt
```


Recommended files:

| File | Image |
|---|---|
| `mission-control.png  , 3d-view.png` | Main Mission Control dashboard,Three.js 3D simulation  |
| `2d-camera.png` | 2D virtual-camera view |
| `performance.png` | Performance Analysis page |
| `report.png` | Generated report |



<img width="1848" height="916" alt="Screenshot 2026-09-28 014202" src="https://github.com/user-attachments/assets/93f408a7-cbe3-4353-a805-4b3b4dcdde8d" />
<img width="1187" height="878" alt="Screenshot 2026-09-28 014737" src="https://github.com/user-attachments/assets/3ff48637-ff2c-428a-9e94-02ad38ce3269" />
<img width="1165" height="868" alt="Screenshot 2026-09-28 014807" src="https://github.com/user-attachments/assets/eec3e4cb-f7cd-4051-a431-167455b828cf" />




## 🎥 Where to Put Videos

For local/sample replay videos, use:

```text
data/videos/
```

For large demonstration videos, preferably use YouTube, GitHub Releases, or another hosted location instead of committing large MP4 files directly to the repository.

## Running the Project

### Backend

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the backend:

```bash
uvicorn backend.main:app --reload --port 8011
```

### Frontend

If the project uses a separate Vite frontend:

```bash
cd frontend
npm install
npm run dev
```

## Local Application

The current local application is available at:

**http://127.0.0.1:8011/**

## Mission Control

The Mission Control area provides:

- **3D World View**
- **2D Camera View**
- Start / Pause / Reset
- Beacon hide/show
- Target selection
- Trajectory selection
- Simulation speed
- Disturbance controls
- Live telemetry
- FOV / LOS / FSOC status

## Performance Analysis

The system records and visualizes:

- Camera angle vs target angle
- Pan/tilt tracking error
- Angular tracking error
- Detection confidence
- Distance
- FSOC link status
- Disturbance intensity
- Acquisition time
- Lock retention
- Target losses
- Mean / maximum / RMS error

## Reports

Each tracking session can produce:

- PDF performance report
- CSV telemetry
- Session statistics
- Tracking graphs
- Disturbance configuration
- FSOC link performance

## Simulation Pipeline

```text
Moving Target
      ↓
Virtual Camera
      ↓
Disturbances
      ↓
Beacon Detection
      ↓
Centroid
      ↓
Kalman Prediction
      ↓
Tracking Error
      ↓
Pan/Tilt Controller
      ↓
Camera Movement
      ↓
Coarse Alignment
      ↓
LOS + FOV Check
      ↓
FSOC Link Status
```

## Disturbances

The main simulated disturbances are:

1. **Platform Vibration** — small high-frequency platform/camera movement.
2. **Camera Motion** — pan/tilt motion, jitter, lag and settling.
3. **Atmospheric Turbulence** — simulated optical/centroid instability.
4. **Sensor/Camera Noise** — measurement and image-detection noise.

These are software simulation models intended for algorithm development and demonstration.

## Objective

The project provides a software-based environment for developing and demonstrating **virtual-camera coarse-alignment algorithms for mobile FSOC terminals**, reducing the need for expensive physical optical hardware during algorithm development and testing.

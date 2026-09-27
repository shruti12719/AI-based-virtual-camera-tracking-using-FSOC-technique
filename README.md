# App Final — FSOC Coarse Alignment Mission Control

This web application wraps the supplied `2d final` simulator modules (`sim`, `vision`, `control`, `disturbance`, and `logging_`) in a FastAPI/WebSocket service. The browser does not generate target motion or tracking state: its 2D optical view and 3D world consume the same Python telemetry message.

## Start

```powershell
& "C:\Users\shrut\OneDrive\Desktop\fsoc-tracker-webapp\web_app\.venv\Scripts\python.exe" -m server
```

Open `http://127.0.0.1:8011`.

## Included behavior

- Actual `VirtualScene`, `VirtualPTZCamera`, `BeaconKalmanTracker`, `DisturbanceManager`, classical detector, optional YOLO detector, and PTZ control code from the supplied 2D project.
- One WebSocket state for the image-forming 2D camera and Three.js world.
- Hide beacon → pure world-frame Kalman prediction → reappear at the prediction position before optical reacquisition.
- Start, pause, reset, trajectory selection, 0–10 decoys, disturbance controls, live analytics, saved scenarios, CSV export and PDF report export.

## Packaging

The web app is served from one FastAPI port. The original PyInstaller specification was not rebuilt in this pass; package `python -m server` with PyInstaller for the final standalone `.exe` once the required Python environment is fixed.

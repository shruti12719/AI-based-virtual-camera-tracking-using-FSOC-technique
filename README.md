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


#previews of the web app 

<img width="1848" height="916" alt="image" src="https://github.com/user-attachments/assets/1a34521b-726c-4e63-bdaa-14a1220e6ec4" />

<img width="1187" height="878" alt="image" src="https://github.com/user-attachments/assets/9d3a4c70-2a43-4b76-80c9-c9eb3abe0ddd" />

<img width="1165" height="868" alt="image" src="https://github.com/user-attachments/assets/a2f6ac48-5ca6-4f3b-9b8c-af44071b6729" />




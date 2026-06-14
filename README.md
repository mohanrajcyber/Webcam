# Webcam CCTV Command Center

A lightweight browser prototype for monitoring wired Ethernet/IP cameras from a
single screen. The dashboard starts with **edit mode on** so cameras can be
added, removed, and marked online/warning/offline during setup.

## Features

- Camera health summary: total, online, needs attention, and active alerts.
- Editable camera cards for RTSP stream URL, location, zone, and monitoring
  rule setup.
- One-click status changes for online, warning, and offline states.
- Irregularity alert timeline with simulated examples.
- Local browser persistence with a reset button for demos.
- No build step and no dependencies.

## Run locally

Open `index.html` directly in a browser, or serve the folder with any static
server:

```bash
python3 -m http.server 8080
```

Then visit:

```text
http://localhost:8080
```

## Next integration steps

This prototype can be connected to real cameras by replacing the demo state in
`app.js` with camera records from an API and streaming snapshots/video from
RTSP/ONVIF/NVR services.

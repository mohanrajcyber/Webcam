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
- LAN server mode for sharing one central dashboard from the main camera system
  to phones, laptops, and Macs on the same Wi-Fi.
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

## Wireless monitoring from the main camera system

Run the included LAN monitor program on the system that can already reach all
wired Ethernet/IP cameras:

```bash
python3 lan_monitor_server.py --host 0.0.0.0 --port 8080
```

The program prints URLs like:

```text
http://192.168.1.50:8080
```

Open that URL from any phone, laptop, or Mac connected to the same Wi-Fi/LAN.
All devices use the same camera list and alert state from `camera_data.json` on
the main system.

### LAN server APIs

- `GET /api/system` - shows LAN access URLs.
- `GET /api/cameras` - lists configured cameras.
- `POST /api/cameras` - adds a camera.
- `PATCH /api/cameras/<id>` - updates camera status/details.
- `DELETE /api/cameras/<id>` - removes a camera.
- `GET /api/alerts` - lists active alerts.
- `POST /api/alerts` - raises an alert for a camera.
- `DELETE /api/alerts` - clears alerts.
- `POST /api/health-check` - checks whether each RTSP/HTTP camera host is
  reachable from the main system.
- `POST /api/reset` - resets demo data.

> Use this only on a trusted internal network. Add authentication before exposing
> it outside the company LAN.

## Next integration steps

This prototype can be connected to real cameras by replacing the demo state in
`app.js` with camera records from an API and streaming snapshots/video from
RTSP/ONVIF/NVR services.

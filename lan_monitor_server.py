#!/usr/bin/env python3
"""LAN server for sharing the CCTV dashboard from the main camera system.

Run this on the computer/NVR workstation that can reach the wired Ethernet
cameras. Phones, laptops, and Macs on the same Wi-Fi can then open the printed
LAN URL in a browser.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import socket
import sys
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "camera_data.json"

DEFAULT_STATE: dict[str, Any] = {
    "editMode": True,
    "cameras": [
        {
            "id": "cam-warehouse-gate",
            "name": "Warehouse Gate 01",
            "location": "Warehouse / Main gate",
            "streamUrl": "rtsp://user:password@192.168.1.10:554/stream1",
            "zone": "Warehouse",
            "rule": "After-hours motion",
            "status": "online",
        },
        {
            "id": "cam-restricted-room",
            "name": "Restricted Room 02",
            "location": "Admin block / Server room",
            "streamUrl": "rtsp://user:password@192.168.1.11:554/stream1",
            "zone": "Restricted Area",
            "rule": "Person in restricted area",
            "status": "warning",
        },
        {
            "id": "cam-parking",
            "name": "Parking Exit 03",
            "location": "Parking / Exit lane",
            "streamUrl": "rtsp://user:password@192.168.1.12:554/stream1",
            "zone": "Parking",
            "rule": "Vehicle wrong parking",
            "status": "online",
        },
        {
            "id": "cam-perimeter",
            "name": "Perimeter Wall 04",
            "location": "North boundary",
            "streamUrl": "rtsp://user:password@192.168.1.13:554/stream1",
            "zone": "Perimeter",
            "rule": "Camera tamper / covered",
            "status": "offline",
        },
    ],
    "alerts": [],
}


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def default_state() -> dict[str, Any]:
    state = json.loads(json.dumps(DEFAULT_STATE))
    state["alerts"] = [
        {
            "id": "alert-restricted-room",
            "cameraId": "cam-restricted-room",
            "cameraName": "Restricted Room 02",
            "rule": "Person in restricted area",
            "message": "Motion detected inside restricted room.",
            "createdAt": now_iso(),
        },
        {
            "id": "alert-perimeter",
            "cameraId": "cam-perimeter",
            "cameraName": "Perimeter Wall 04",
            "rule": "Camera tamper / covered",
            "message": "Camera feed is offline. Check PoE switch or Ethernet cable.",
            "createdAt": now_iso(),
        },
    ]
    return state


def load_state() -> dict[str, Any]:
    if not DATA_FILE.exists():
        return default_state()

    try:
        with DATA_FILE.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return default_state()

    if not isinstance(state.get("cameras"), list):
        state["cameras"] = []
    if not isinstance(state.get("alerts"), list):
        state["alerts"] = []
    state["editMode"] = bool(state.get("editMode", True))
    return state


def save_state(state: dict[str, Any]) -> None:
    with DATA_FILE.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")


def get_lan_addresses() -> list[str]:
    addresses: set[str] = set()
    hostname = socket.gethostname()

    try:
        for result in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            address = result[4][0]
            if not address.startswith("127."):
                addresses.add(address)
    except socket.gaierror:
        pass

    # UDP connect does not send packets, but it reveals the preferred LAN IP.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            address = probe.getsockname()[0]
            if not address.startswith("127."):
                addresses.add(address)
    except OSError:
        pass

    return sorted(addresses)


def parse_stream_host(stream_url: str) -> tuple[str, int] | None:
    if not stream_url:
        return None

    parsed = urllib.parse.urlparse(stream_url)
    if not parsed.hostname:
        return None

    default_ports = {
        "rtsp": 554,
        "http": 80,
        "https": 443,
    }
    return parsed.hostname, parsed.port or default_ports.get(parsed.scheme, 554)


def can_reach_stream(stream_url: str, timeout: float) -> bool:
    endpoint = parse_stream_host(stream_url)
    if endpoint is None:
        return False

    host, port = endpoint
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def build_alert_message(camera: dict[str, Any], rule: str) -> str:
    messages = {
        "Camera offline": "Camera feed is not reachable. Check Ethernet, PoE, NVR, or RTSP credentials.",
        "After-hours motion": "Movement detected outside configured working hours.",
        "Camera tamper / covered": "Feed appears blocked, covered, or pointed away from the scene.",
        "Person in restricted area": "Person detected in a restricted zone.",
        "Fire or smoke": "Possible fire or smoke pattern detected.",
        "Vehicle wrong parking": "Vehicle stopped in an unauthorized area.",
        "PPE / helmet missing": "Person detected without required PPE or helmet.",
    }
    return messages.get(rule, f"Irregularity detected at {camera.get('location', 'camera')}.")


def upsert_alert(state: dict[str, Any], camera: dict[str, Any], rule: str) -> dict[str, Any]:
    for alert in state["alerts"]:
        if alert.get("cameraId") == camera["id"] and alert.get("rule") == rule:
            alert["createdAt"] = now_iso()
            alert["message"] = build_alert_message(camera, rule)
            return alert

    alert = {
        "id": f"alert-{int(time.time() * 1000)}",
        "cameraId": camera["id"],
        "cameraName": camera.get("name", "Camera"),
        "rule": rule,
        "message": build_alert_message(camera, rule),
        "createdAt": now_iso(),
    }
    state["alerts"].insert(0, alert)
    return alert


def sanitize_camera(payload: dict[str, Any], existing_id: str | None = None) -> dict[str, Any]:
    camera_id = existing_id or str(payload.get("id") or f"cam-{int(time.time() * 1000)}")
    return {
        "id": camera_id,
        "name": str(payload.get("name") or "Unnamed Camera").strip(),
        "location": str(payload.get("location") or "Unknown location").strip(),
        "streamUrl": str(payload.get("streamUrl") or "").strip(),
        "zone": str(payload.get("zone") or "Office").strip(),
        "rule": str(payload.get("rule") or "After-hours motion").strip(),
        "status": str(payload.get("status") or "online").strip(),
    }


class MonitorHandler(BaseHTTPRequestHandler):
    server_version = "CCTVLANMonitor/1.0"

    def do_GET(self) -> None:
        if self.path == "/api/system":
            self.send_json(self.system_payload())
            return
        if self.path == "/api/cameras":
            self.send_json({"cameras": load_state()["cameras"]})
            return
        if self.path == "/api/alerts":
            self.send_json({"alerts": load_state()["alerts"]})
            return

        self.serve_static_file()

    def do_POST(self) -> None:
        if self.path == "/api/cameras":
            state = load_state()
            camera = sanitize_camera(self.read_json())
            state["cameras"].insert(0, camera)
            save_state(state)
            self.send_json({"camera": camera}, HTTPStatus.CREATED)
            return

        if self.path == "/api/alerts":
            state = load_state()
            payload = self.read_json()
            camera = find_camera(state, str(payload.get("cameraId") or ""))
            if camera is None:
                self.send_error_json("Camera not found", HTTPStatus.NOT_FOUND)
                return
            camera["status"] = "warning" if camera.get("status") == "online" else camera.get("status")
            alert = upsert_alert(state, camera, str(payload.get("rule") or camera.get("rule")))
            save_state(state)
            self.send_json({"alert": alert})
            return

        if self.path == "/api/health-check":
            state = load_state()
            results = []
            timeout = float(os.environ.get("CAMERA_CHECK_TIMEOUT", "0.8"))
            for camera in state["cameras"]:
                is_reachable = can_reach_stream(camera.get("streamUrl", ""), timeout)
                camera["status"] = "online" if is_reachable else "offline"
                if not is_reachable:
                    upsert_alert(state, camera, "Camera offline")
                results.append(
                    {
                        "cameraId": camera["id"],
                        "name": camera.get("name"),
                        "reachable": is_reachable,
                        "status": camera["status"],
                    }
                )
            save_state(state)
            self.send_json({"results": results, "state": state})
            return

        if self.path == "/api/reset":
            state = default_state()
            save_state(state)
            self.send_json({"state": state})
            return

        self.send_error_json("Not found", HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:
        if not self.path.startswith("/api/cameras/"):
            self.send_error_json("Not found", HTTPStatus.NOT_FOUND)
            return

        camera_id = urllib.parse.unquote(self.path.removeprefix("/api/cameras/"))
        state = load_state()
        camera = find_camera(state, camera_id)
        if camera is None:
            self.send_error_json("Camera not found", HTTPStatus.NOT_FOUND)
            return

        payload = self.read_json()
        camera.update(sanitize_camera({**camera, **payload}, existing_id=camera_id))
        if camera["status"] != "online":
            upsert_alert(state, camera, "Camera offline" if camera["status"] == "offline" else camera["rule"])
        save_state(state)
        self.send_json({"camera": camera})

    def do_DELETE(self) -> None:
        if self.path == "/api/alerts":
            state = load_state()
            state["alerts"] = []
            save_state(state)
            self.send_json({"alerts": []})
            return

        if self.path.startswith("/api/cameras/"):
            camera_id = urllib.parse.unquote(self.path.removeprefix("/api/cameras/"))
            state = load_state()
            state["cameras"] = [camera for camera in state["cameras"] if camera.get("id") != camera_id]
            state["alerts"] = [alert for alert in state["alerts"] if alert.get("cameraId") != camera_id]
            save_state(state)
            self.send_json({"ok": True})
            return

        self.send_error_json("Not found", HTTPStatus.NOT_FOUND)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message: str, status: HTTPStatus) -> None:
        self.send_json({"error": message}, status)

    def serve_static_file(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        relative_path = urllib.parse.unquote(parsed.path.lstrip("/")) or "index.html"
        candidate = (ROOT / relative_path).resolve()

        if ROOT not in candidate.parents and candidate != ROOT:
            self.send_error(HTTPStatus.FORBIDDEN)
            return

        if candidate.is_dir():
            candidate = candidate / "index.html"

        if not candidate.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        body = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def system_payload(self) -> dict[str, Any]:
        port = self.server.server_address[1]
        addresses = get_lan_addresses()
        return {
            "name": socket.gethostname(),
            "port": port,
            "addresses": addresses,
            "accessUrls": [f"http://{address}:{port}" for address in addresses],
            "message": "Open one of these URLs on phone, laptop, or Mac connected to the same Wi-Fi.",
        }

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))


def find_camera(state: dict[str, Any], camera_id: str) -> dict[str, Any] | None:
    return next((camera for camera in state["cameras"] if camera.get("id") == camera_id), None)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the CCTV dashboard on the local network.")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address. Use 0.0.0.0 for LAN access.")
    parser.add_argument("--port", default=8080, type=int, help="HTTP port for phone/laptop access.")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), MonitorHandler)
    addresses = get_lan_addresses()

    print("CCTV LAN monitor is running.")
    print(f"Local URL: http://127.0.0.1:{args.port}")
    if addresses:
        print("Wireless device URLs:")
        for address in addresses:
            print(f"  http://{address}:{args.port}")
    else:
        print("No LAN IP detected yet. Check Wi-Fi/network connection.")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping CCTV LAN monitor.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

const STORAGE_KEY = "webcam-command-center";

const defaultState = {
  editMode: true,
  cameras: [
    {
      id: "cam-warehouse-gate",
      name: "Warehouse Gate 01",
      location: "Warehouse / Main gate",
      streamUrl: "rtsp://user:password@192.168.1.10:554/stream1",
      zone: "Warehouse",
      rule: "After-hours motion",
      status: "online",
    },
    {
      id: "cam-restricted-room",
      name: "Restricted Room 02",
      location: "Admin block / Server room",
      streamUrl: "rtsp://user:password@192.168.1.11:554/stream1",
      zone: "Restricted Area",
      rule: "Person in restricted area",
      status: "warning",
    },
    {
      id: "cam-parking",
      name: "Parking Exit 03",
      location: "Parking / Exit lane",
      streamUrl: "rtsp://user:password@192.168.1.12:554/stream1",
      zone: "Parking",
      rule: "Vehicle wrong parking",
      status: "online",
    },
    {
      id: "cam-perimeter",
      name: "Perimeter Wall 04",
      location: "North boundary",
      streamUrl: "rtsp://user:password@192.168.1.13:554/stream1",
      zone: "Perimeter",
      rule: "Camera tamper / covered",
      status: "offline",
    },
  ],
  alerts: [
    {
      id: "alert-restricted-room",
      cameraId: "cam-restricted-room",
      cameraName: "Restricted Room 02",
      rule: "Person in restricted area",
      message: "Motion detected inside restricted room.",
      createdAt: new Date().toISOString(),
    },
    {
      id: "alert-perimeter",
      cameraId: "cam-perimeter",
      cameraName: "Perimeter Wall 04",
      rule: "Camera tamper / covered",
      message: "Camera feed is offline. Check PoE switch or Ethernet cable.",
      createdAt: new Date().toISOString(),
    },
  ],
};

const state = loadState();

const elements = {
  body: document.body,
  editModeToggle: document.querySelector("#editModeToggle"),
  editHint: document.querySelector("#editHint"),
  cameraForm: document.querySelector("#cameraForm"),
  cameraGrid: document.querySelector("#cameraGrid"),
  cameraTemplate: document.querySelector("#cameraCardTemplate"),
  totalCameras: document.querySelector("#totalCameras"),
  onlineCameras: document.querySelector("#onlineCameras"),
  issueCameras: document.querySelector("#issueCameras"),
  activeAlerts: document.querySelector("#activeAlerts"),
  alertList: document.querySelector("#alertList"),
  clearAlertsButton: document.querySelector("#clearAlertsButton"),
  resetButton: document.querySelector("#resetButton"),
  simulateAlertButton: document.querySelector("#simulateAlertButton"),
};

function loadState() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));

    if (saved && Array.isArray(saved.cameras) && Array.isArray(saved.alerts)) {
      return {
        ...defaultState,
        ...saved,
        editMode: saved.editMode ?? true,
      };
    }
  } catch (error) {
    console.warn("Could not load saved dashboard state", error);
  }

  return structuredClone(defaultState);
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function render() {
  elements.body.classList.toggle("edit-mode", state.editMode);
  elements.editModeToggle.checked = state.editMode;
  elements.editHint.textContent = state.editMode
    ? "Edit mode is on: cards are editable."
    : "View mode: camera controls are hidden.";

  renderMetrics();
  renderCameras();
  renderAlerts();
  saveState();
}

function renderMetrics() {
  const onlineCount = state.cameras.filter(
    (camera) => camera.status === "online",
  ).length;
  const issueCount = state.cameras.length - onlineCount;

  elements.totalCameras.textContent = state.cameras.length;
  elements.onlineCameras.textContent = onlineCount;
  elements.issueCameras.textContent = issueCount;
  elements.activeAlerts.textContent = state.alerts.length;
}

function renderCameras() {
  elements.cameraGrid.innerHTML = "";

  if (state.cameras.length === 0) {
    elements.cameraGrid.innerHTML =
      '<p class="empty-state">No cameras yet. Turn edit mode on and add your first RTSP camera.</p>';
    return;
  }

  state.cameras.forEach((camera) => {
    const card = elements.cameraTemplate.content
      .firstElementChild.cloneNode(true);

    card.dataset.cameraId = camera.id;
    card.classList.add(camera.status);
    card.querySelector(".feed-label").textContent = camera.name;
    card.querySelector(".camera-name").textContent = camera.name;
    card.querySelector(".camera-location").textContent = camera.location;
    card.querySelector(".camera-zone").textContent = camera.zone;
    card.querySelector(".camera-rule").textContent = camera.rule;
    card.querySelector(".camera-stream").textContent =
      camera.streamUrl || "Stream URL not set";
    card.querySelector(".status-pill").textContent = camera.status;

    elements.cameraGrid.append(card);
  });
}

function renderAlerts() {
  elements.alertList.innerHTML = "";
  elements.clearAlertsButton.disabled = state.alerts.length === 0;

  if (state.alerts.length === 0) {
    elements.alertList.innerHTML =
      '<li class="empty-state">No active irregularities right now.</li>';
    return;
  }

  state.alerts
    .slice()
    .sort((left, right) => new Date(right.createdAt) - new Date(left.createdAt))
    .forEach((alert) => {
      const item = document.createElement("li");
      item.className = "alert-item";
      item.innerHTML = `
        <span class="alert-icon">!</span>
        <div>
          <p class="alert-title">${escapeHtml(alert.cameraName)} - ${escapeHtml(alert.rule)}</p>
          <p class="alert-meta">${escapeHtml(alert.message)}</p>
        </div>
        <time class="alert-meta" datetime="${alert.createdAt}">
          ${formatTime(alert.createdAt)}
        </time>
      `;
      elements.alertList.append(item);
    });
}

function addCamera(formData) {
  const camera = {
    id: `cam-${crypto.randomUUID()}`,
    name: formData.get("name").trim(),
    location: formData.get("location").trim(),
    streamUrl: formData.get("streamUrl").trim(),
    zone: formData.get("zone"),
    rule: formData.get("rule"),
    status: "online",
  };

  state.cameras.unshift(camera);
  render();
}

function updateCameraStatus(cameraId, status) {
  const camera = state.cameras.find((item) => item.id === cameraId);

  if (!camera) {
    return;
  }

  camera.status = status;

  if (status !== "online") {
    addAlert(camera, status === "offline" ? "Camera offline" : camera.rule);
  }

  render();
}

function addAlert(camera, rule = camera.rule) {
  const existingSimilarAlert = state.alerts.find(
    (alert) => alert.cameraId === camera.id && alert.rule === rule,
  );

  if (existingSimilarAlert) {
    existingSimilarAlert.createdAt = new Date().toISOString();
    existingSimilarAlert.message = buildAlertMessage(camera, rule);
    return;
  }

  state.alerts.unshift({
    id: `alert-${crypto.randomUUID()}`,
    cameraId: camera.id,
    cameraName: camera.name,
    rule,
    message: buildAlertMessage(camera, rule),
    createdAt: new Date().toISOString(),
  });
}

function buildAlertMessage(camera, rule) {
  const messages = {
    "Camera offline": "Camera feed is not reachable. Check Ethernet, PoE, NVR, or RTSP credentials.",
    "After-hours motion": "Movement detected outside configured working hours.",
    "Camera tamper / covered": "Feed appears blocked, covered, or pointed away from the scene.",
    "Person in restricted area": "Person detected in a restricted zone.",
    "Fire or smoke": "Possible fire or smoke pattern detected.",
    "Vehicle wrong parking": "Vehicle stopped in an unauthorized area.",
    "PPE / helmet missing": "Person detected without required PPE or helmet.",
  };

  return messages[rule] || `Irregularity detected at ${camera.location}.`;
}

function deleteCamera(cameraId) {
  state.cameras = state.cameras.filter((camera) => camera.id !== cameraId);
  state.alerts = state.alerts.filter((alert) => alert.cameraId !== cameraId);
  render();
}

function simulateAlert() {
  if (state.cameras.length === 0) {
    return;
  }

  const camera = state.cameras[Math.floor(Math.random() * state.cameras.length)];
  camera.status = camera.status === "offline" ? "warning" : camera.status;
  addAlert(camera);
  render();
}

function formatTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

elements.editModeToggle.addEventListener("change", (event) => {
  state.editMode = event.target.checked;
  render();
});

elements.cameraForm.addEventListener("submit", (event) => {
  event.preventDefault();
  addCamera(new FormData(event.currentTarget));
  event.currentTarget.reset();
});

elements.cameraGrid.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  const card = event.target.closest(".camera-card");

  if (!button || !card) {
    return;
  }

  const { cameraId } = card.dataset;

  if (button.classList.contains("mark-online")) {
    updateCameraStatus(cameraId, "online");
  }

  if (button.classList.contains("mark-warning")) {
    updateCameraStatus(cameraId, "warning");
  }

  if (button.classList.contains("mark-offline")) {
    updateCameraStatus(cameraId, "offline");
  }

  if (button.classList.contains("raise-alert")) {
    const camera = state.cameras.find((item) => item.id === cameraId);
    if (camera) {
      camera.status = camera.status === "online" ? "warning" : camera.status;
      addAlert(camera);
      render();
    }
  }

  if (button.classList.contains("delete-camera")) {
    deleteCamera(cameraId);
  }
});

elements.clearAlertsButton.addEventListener("click", () => {
  state.alerts = [];
  render();
});

elements.resetButton.addEventListener("click", () => {
  localStorage.removeItem(STORAGE_KEY);
  Object.assign(state, structuredClone(defaultState));
  render();
});

elements.simulateAlertButton.addEventListener("click", simulateAlert);

render();

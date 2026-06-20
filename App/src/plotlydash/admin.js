// admin.js - EV Status Monitor frontend logic
// Connects to the admin_server.py backend on the same origin

// --- CONFIG ---
const API_BASE = ""; // Same origin, no prefix needed

// --- STATE ---
let selectedCarId = null;
let evtSource = null;
let logLevel = "INFO";
let logCacheInfo = {}; // carId -> string[]
let logCacheDebug = {}; // carId -> string[]
const MAX_LOG_LINES = 50;

// --- HELPERS ---
async function fetchJson(url, options = {}) {
  try {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return await res.json();
  } catch (e) {
    console.error(`Fetch error ${url}:`, e);
    return null;
  }
}

function formatNum(n, decimals = 1) {
  if (n === null || n === undefined || isNaN(n)) return "N/A";
  return Number(n).toFixed(decimals);
}

// --- VEHICLE LIST ---
async function loadVehicleList() {
  const vehicles = await fetchJson(`${API_BASE}/api/ev`);
  const container = document.getElementById("vehicleList");
  if (!vehicles || vehicles.length === 0) {
    container.innerHTML = `<div class="p-3 text-muted text-center" style="font-size:12px; font-style:italic;">No vehicles registered in this session.</div>`;
    return;
  }
  container.innerHTML = "";
  for (const v of vehicles) {
    const btn = document.createElement("button");
    btn.className = `vehicle-btn${String(v.car_id) === String(selectedCarId) ? " active" : ""}`;
    btn.innerHTML = `<div><i class="fa fa-car me-2" style="opacity:0.5"></i><span style="font-weight:bold; font-size:15px;">${v.car_id}</span></div>`;
    btn.addEventListener("click", () => selectVehicle(v.car_id));
    container.appendChild(btn);
  }
}

// --- VEHICLE SELECTION ---
async function selectVehicle(carId) {
  // 1. NGẮT LUỒNG DỮ LIỆU CŨ NGAY LẬP TỨC (Không được để sau lệnh await)
  if (evtSource) {
    evtSource.close();
    evtSource = null;
  }

  // 2. Chốt ID xe mới
  selectedCarId = carId;

  // 3. Reset giao diện về số 0 để dọn sạch "bóng ma" dữ liệu cũ
  resetDashboard();

  // 4. Update sidebar (tải danh sách xe). Không cần await để tránh block luồng.
  loadVehicleList();

  // 5. Lấy thông tin tĩnh của xe (Vehicle Information)
  await fetchVehicleDetails(carId);

  // 6. Chủ động lấy trạng thái cuối cùng của xe từ DB
  const latestStatus = await fetchJson(`${API_BASE}/api/status/latest/${encodeURIComponent(carId)}`);
  
  if (latestStatus && Object.keys(latestStatus).length > 0) {
    updateDashboard(latestStatus);
  } else {
    // Nếu xe hoàn toàn mới và chưa từng có telemetry
    document.getElementById("logContent").textContent = `No historical telemetry data found for ${carId}.`;
  }

  // 7. Mở luồng lắng nghe dữ liệu thời gian thực (SSE) cho xe mới
  startSSE(carId);
}

// --- RESET DASHBOARD HELPER ---
function resetDashboard() {
  // Trả Top Status về trạng thái chờ
  const topStatus = document.getElementById("topStatusText");
  topStatus.textContent = "WAITING...";
  topStatus.className = "fw-bold text-secondary";

  // Reset KPI Cards
  document.getElementById("statusVal").textContent = "--";
  document.getElementById("socVal").textContent = "0";
  document.getElementById("capacityVal").textContent = "0";
  document.getElementById("mileageVal").textContent = "0";

  // Reset Cells & Thermal
  document.getElementById("maxCellVal").textContent = "0.000";
  document.getElementById("minCellVal").textContent = "0.000";
  document.getElementById("diffCellVal").textContent = "0.000";
  document.getElementById("tempRangeVal").textContent = "0 - 0°C";
  document.getElementById("powerVal").textContent = "0.0 kW";

  // Reset Gauge
  updateGauge(0);

  // Xóa trắng Logs & Timestamp
  document.getElementById("logTimestamp").textContent = "";
  renderLogs(); 
}

// --- VEHICLE DETAILS ---
async function fetchVehicleDetails(carId) {
  const details = await fetchJson(`${API_BASE}/api/ev/${encodeURIComponent(carId)}/details`);
  const container = document.getElementById("vehicleInfoContent");
  if (!details) {
    container.innerHTML = `<div class="mt-4 text-muted">No vehicle selected.</div>`;
    return;
  }
  const g = (key) => details[key] || "N/A";
  container.innerHTML = `
    <div class="info-row"><div class="info-label">Car ID</div><div class="info-value">${carId}</div></div>
    <div class="info-row"><div class="info-label">Vehicle Name</div><div class="info-value">${g("car_name")}</div></div>
    <div class="info-row"><div class="info-label">User ID</div><div class="info-value text-primary fw-bold">${g("user_id")}</div></div> <div class="info-row"><div class="info-label">VIN Number</div><div class="info-value">${g("vin_number")}</div></div>
    <div class="info-row"><div class="info-label">License Plate</div><div class="info-value">${g("license_plate")}</div></div>
    <div class="info-row"><div class="info-label">Battery Serial</div><div class="info-value">${g("battery_serial")}</div></div>
    <div class="info-row"><div class="info-label">Motor Serial</div><div class="info-value">${g("motor_serial")}</div></div>
  `;
}

// --- SSE ---
function startSSE(carId) {
  evtSource = new EventSource(`${API_BASE}/api/status/stream/${encodeURIComponent(carId)}`);

  evtSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (String(data.car_id) !== String(carId)) return;
      updateDashboard(data);
    } catch (e) {
      appendLog(carId, "DEBUG", `JSON decode error: ${e.message}`, Date.now());
    }
  };

  evtSource.onerror = (err) => {
    console.error("SSE connection error, closing...");
    evtSource.close();
  };
}

// --- DASHBOARD UPDATE ---
function updateDashboard(data) {
  const volt = data.volt_V || 0;
  const currentVal = data.current_A || 0;
  const speed = data.avg_speed_kmh || 0;
  const soc = data.soc_pct || 0;
  const capacity = data.actual_max_capacity_Ah || 0;
  const mileage = data.mileage_km || 0;
  const maxSingleVolt = data.max_single_volt_V || 0;
  const minSingleVolt = data.min_single_volt_V || 0;
  const minTemp = data.min_temp_C || 0;
  const maxTemp = data.max_temp_C || 0;
  const timestamp = data.timestamp_s || 0;

  // Status logic
  let status, statusClass, uiStat;
  if (speed > 0) {
    status = "RUNNING";
    statusClass = "text-success fw-bold me-4";
    uiStat = "NORMAL";
  } else if (currentVal < -1) {
    status = "CHARGING";
    statusClass = "text-warning fw-bold me-4";
    uiStat = "CHARGING";
  } else {
    status = "STOPPED";
    statusClass = "text-danger fw-bold me-4";
    uiStat = "IDLE";
  }

  // KPI cards
  document.getElementById("statusVal").textContent = uiStat;
  document.getElementById("socVal").textContent = soc;
  document.getElementById("capacityVal").textContent = capacity;
  document.getElementById("mileageVal").textContent = Number(mileage).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  // Cell voltage
  document.getElementById("maxCellVal").textContent = formatNum(maxSingleVolt, 3);
  document.getElementById("minCellVal").textContent = formatNum(minSingleVolt, 3);
  document.getElementById("diffCellVal").textContent = formatNum(maxSingleVolt - minSingleVolt, 3);

  // Thermal & power
  document.getElementById("tempRangeVal").textContent = `${minTemp} - ${maxTemp}°C`;
  document.getElementById("powerVal").textContent = `${formatNum(volt * currentVal / 1000, 1)} kW`;

  // Speed gauge
  updateGauge(speed);

  // Top status bar
  const topStatus = document.getElementById("topStatusText");
  topStatus.textContent = status;
  topStatus.className = `fw-bold ${status === "RUNNING" ? "text-success" : status === "CHARGING" ? "text-warning" : "text-danger"}`;

  // Logs
  const currentCar = data.car_id || selectedCarId;
  const logMsg = `EV-${currentCar} status: ${status}, data received`;
  appendLog(selectedCarId, "INFO", logMsg, timestamp);
  renderLogs();
  document.getElementById("logTimestamp").textContent = `Last update: ${timestamp}`;
}

// --- GAUGE ---
function updateGauge(speed) {
  const maxSpeed = 240;
  // Đảm bảo phần trăm tốc độ không bị âm
  const pct = Math.max(0, Math.min(speed / maxSpeed, 1));

  // Tính toán chiều dài dải màu
  const maxArcLength = 235.6;
  const currentArcLength = pct * maxArcLength;
  
  const gaugeArc = document.getElementById("gaugeArc");
  if(gaugeArc) {
      // Cập nhật độ dài dải màu trực tiếp
      gaugeArc.setAttribute("stroke-dasharray", `${currentArcLength} 314.16`);
      
      // Đổi màu cảnh báo
      let color = "#56a64b"; // green
      if (speed >= 140) color = "#e02f44"; // red
      else if (speed >= 80) color = "#f2994a"; // orange
      gaugeArc.setAttribute("stroke", color);
  }

  document.getElementById("gaugeValue").textContent = Math.round(speed);
}

// --- LOGS ---
function appendLog(carId, level, message, timestamp) {
  const cache = level === "INFO" ? logCacheInfo : logCacheDebug;
  if (!cache[carId]) cache[carId] = [];
  const ts = typeof timestamp === "number" && timestamp > 1e12
    ? new Date(timestamp).toISOString().slice(11, 19)
    : timestamp;
  cache[carId].push(`[${ts}] [${level}] ${message}`);
  if (cache[carId].length > MAX_LOG_LINES) {
    cache[carId] = cache[carId].slice(-MAX_LOG_LINES);
  }
}

function renderLogs() {
  const carId = selectedCarId;
  if (!carId) return;
  const cache = logLevel === "INFO" ? logCacheInfo : logCacheDebug;
  const logs = cache[carId] || [];
  const el = document.getElementById("logContent");
  el.textContent = logs.join("\n");
  el.scrollTop = el.scrollHeight;

  // Toggle button styles
  document.getElementById("btnLogInfo").classList.toggle("active", logLevel === "INFO");
  document.getElementById("btnLogDebug").classList.toggle("active", logLevel === "DEBUG");
}

// --- REGISTRATION MODAL ---
async function registerVehicle() {
  const carId = document.getElementById("regCarId").value.trim();
  const userId = document.getElementById("regUserId").value.trim(); // Lấy giá trị User ID

  // Validate bắt buộc nhập Car ID và User ID
  if (!carId || !userId) {
    document.getElementById("regFeedback").textContent = "Error: Car ID and User ID are required.";
    return;
  }

  const payload = {
    car_id: carId,
    car_name: document.getElementById("regCarName").value.trim(),
    vin_number: document.getElementById("regVin").value.trim(),
    license_plate: document.getElementById("regLicense").value.trim(),
    battery_serial: document.getElementById("regBattery").value.trim(),
    motor_serial: document.getElementById("regMotor").value.trim(),
    user_id: userId, // Bỏ chuỗi rỗng "", gán giá trị người dùng nhập vào
  };

  const res = await fetch(`${API_BASE}/api/ev`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (res.ok || res.status === 201) {
    // Close modal
    const modal = bootstrap.Modal.getInstance(document.getElementById("modalRegister"));
    if (modal) modal.hide();

    // Clear form (nhớ thêm regUserId vào mảng này để reset sau khi lưu thành công)
    ["regCarId", "regCarName", "regVin", "regLicense", "regBattery", "regMotor", "regUserId"].forEach(id => {
      document.getElementById(id).value = "";
    });
    document.getElementById("regFeedback").textContent = "";

    // Reload list & select new vehicle
    await loadVehicleList();
    await selectVehicle(carId);
  } else {
    document.getElementById("regFeedback").textContent = `Error: ${res.statusText}`;
  }
}

// --- INIT ---
document.addEventListener("DOMContentLoaded", () => {
  loadVehicleList();

  // Log toggle buttons
  document.getElementById("btnLogInfo").addEventListener("click", () => {
    logLevel = "INFO";
    renderLogs();
  });
  document.getElementById("btnLogDebug").addEventListener("click", () => {
    logLevel = "DEBUG";
    renderLogs();
  });

  // Registration submit
  document.getElementById("btnSubmitReg").addEventListener("click", registerVehicle);
});

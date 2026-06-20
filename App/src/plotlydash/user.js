// user.js - EV dashboard frontend logic
// Connects to user_server.py backend via SSE

// --- CONFIG ---
const API_BASE = "";
let evtSource = null;
let labelState = 0; // 0 or 10

// --- HELPERS ---
function formatNum(n, decimals = 1) {
    if (n === null || n === undefined || isNaN(n)) return "N/A";
    return Number(n).toFixed(decimals);
}

// --- GAUGE ---
function updateGauge(speed) {
    const maxSpeed = 240;
    // Đảm bảo phần trăm luôn nằm trong khoảng 0 đến 1
    const pct = Math.max(0, Math.min(speed / maxSpeed, 1)); 
    
    // Chiều dài tối đa của cung 270 độ là 235.6. Chu vi cả vòng tròn là 314.16
    const maxArcLength = 235.6; 
    const currentArcLength = pct * maxArcLength;
    
    const gaugeArc = document.getElementById("gaugeArc");
    if(gaugeArc) {
        // Cập nhật độ dài dải màu theo tốc độ hiện tại
        gaugeArc.setAttribute("stroke-dasharray", `${currentArcLength} 314.16`);
        
        // Đổi màu cảnh báo
        let color = "#56a64b";
        if (speed >= 140) color = "#e02f44";
        else if (speed >= 80) color = "#f2994a";
        gaugeArc.setAttribute("stroke", color);
    }
}

// --- TREND CHART (Canvas) ---
let trendPoints = [];
const MAX_TREND = 50;

function drawTrendChart() {
    const canvas = document.getElementById("trendChart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    if (trendPoints.length < 2) return;

    let mins = Math.min(...trendPoints);
    let maxs = Math.max(...trendPoints);

    // --- FIX BIÊN ĐỘ DAO ĐỘNG (THÊM ĐOẠN NÀY) ---
    // Ép khoảng hiển thị tối thiểu trên trục Y là 10V
    let range = maxs - mins;
    if (range < 10) {
        const mid = (maxs + mins) / 2;
        mins = mid - 5; // Mở rộng đáy xuống 5V
        maxs = mid + 5; // Mở rộng đỉnh lên 5V
        range = 10;
    } else {
        // Nếu dao động thực tế > 10V, thêm 15% đệm trên/dưới để biểu đồ không chạm nóc
        mins -= range * 0.15;
        maxs += range * 0.15;
        range = maxs - mins;
    }
    // --------------------------------------------

    const pad = 2;

    // Tính toán tọa độ x, y cho tất cả các điểm
    const points = trendPoints.map((val, i) => {
        const x = (i / (MAX_TREND - 1)) * w;
        const y = h - pad - ((val - mins) / range) * (h - 2 * pad);
        return { x, y };
    });

    ctx.beginPath();
    ctx.strokeStyle = "#00f2ff";
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";

    ctx.moveTo(points[0].x, points[0].y);

    // Thuật toán vẽ đường cong (Spline / Bezier)
    for (let i = 0; i < points.length - 1; i++) {
        const curr = points[i];
        const next = points[i + 1];
        
        const cx = (curr.x + next.x) / 2;
        const cy1 = curr.y;
        const cy2 = next.y;
        
        ctx.bezierCurveTo(cx, cy1, cx, cy2, next.x, next.y);
    }
    ctx.stroke();

    // Fill under line
    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();
    ctx.fillStyle = "rgba(0, 242, 255, 0.1)";
    ctx.fill();
}

// --- DASHBOARD UPDATE ---
function updateDashboard(data) {
    const volt = data.volt_V || 0;
    const current = data.current_A || 0;
    const speed = data.avg_speed_kmh || 0;
    const soc = data.soc_pct || 0;
    const capacity = data.nominal_capacity_Ah || data.actual_max_capacity_Ah || 0;
    const mileage = data.mileage_km || 0;
    const minTemp = data.min_temp_C || 0;
    const maxTemp = data.max_temp_C || 0;
    const timestamp = data.timestamp_s || 0;
    const label = data.label || 0;

    // Sync label state from backend
    labelState = label;

    // Trend data
    if (typeof volt === "number") {
        trendPoints.push(volt);
        if (trendPoints.length > MAX_TREND) trendPoints.shift();
    }
    drawTrendChart();

    // UI Status logic (Matches old Dash logic: NORMAL vs ANOMALY)
    let statusText, statusColor, statusBg, statusBorder, statusShadow;
    if (labelState === 10) {
        statusText = "ANOMALY";
        statusColor = "#ff3b3b";
        statusBg = "rgba(255, 59, 59, 0.2)";
        statusBorder = `2px solid #ff3b3b`;
        statusShadow = `0 0 15px #ff3b3b`;
    } else {
        statusText = "NORMAL";
        statusColor = "#76c65e";
        statusBg = "rgba(118, 198, 94, 0.2)";
        statusBorder = `2px solid #76c65e`;
        statusShadow = `0 0 10px #76c65e`;
    }

    // Update Label Btn View
    const btn = document.getElementById("labelBtn");
    btn.textContent = labelState === 10 ? "10" : "00";
    btn.style.backgroundColor = labelState === 10 ? "#ff3b3b" : "#76c65e";
    btn.style.color = labelState === 10 ? "#fff" : "#000";

    // Update status box
    const statusBox = document.getElementById("statusBox");
    statusBox.style.background = statusBg;
    statusBox.style.border = statusBorder;
    statusBox.style.boxShadow = statusShadow;
    statusBox.innerHTML = `<span style="color: ${statusColor}; font-weight: bold; font-size: 16px; letter-spacing: 1px;">${statusText}</span>`;

    // KPIs
    document.getElementById("speedDisplay").textContent = Math.round(speed);
    document.getElementById("socVal").textContent = Math.round(soc) + "%";
    document.getElementById("capacityVal").textContent = formatNum(capacity, 1);
    document.getElementById("mileageVal").textContent = Number(mileage).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 });

    // Cells
    document.getElementById("voltVal").textContent = formatNum(volt, 2);
    document.getElementById("currentVal").textContent = formatNum(current, 2);
    document.getElementById("maxTempVal").textContent = formatNum(maxTemp, 1);
    document.getElementById("minTempVal").textContent = formatNum(minTemp, 1);

    // Battery fill
    document.getElementById("batteryFill").style.width = soc + "%";

    // Gauge
    updateGauge(speed);

    // Timestamp
    document.getElementById("timestampVal").textContent = "Timestamp: " + timestamp;
}

// --- QUẢN LÝ HÀNG ĐỢI (MESSAGE QUEUE) ---
let messageQueue = [];
let isProcessingQueue = false;

// Hàm xử lý hàng đợi với độ trễ 0.5s
async function processQueue() {
    isProcessingQueue = true;
    while (messageQueue.length > 0) {
        // Lấy bản ghi cũ nhất ra khỏi hàng đợi
        const data = messageQueue.shift();
        
        // Cập nhật giao diện
        updateDashboard(data);
        
        // Tạm dừng 500ms (0.5s) trước khi xử lý bản ghi tiếp theo
        await new Promise(resolve => setTimeout(resolve, 500));
    }
    isProcessingQueue = false;
}

// --- SSE ---
function startSSE() {
    if (evtSource && evtSource.readyState !== 2) {
        evtSource.close();
    }
    evtSource = new EventSource(`${API_BASE}/api/status/stream`);

    evtSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            
            // Thay vì update thẳng, ta đẩy data vào hàng đợi
            messageQueue.push(data);
            
            // Nếu người vận chuyển đang nghỉ ngơi, hãy gọi anh ta dậy làm việc
            if (!isProcessingQueue) {
                processQueue();
            }
        } catch (e) {
            console.error("JSON decode error:", e.message);
        }
    };

    evtSource.onerror = () => {
        console.error("SSE connection error, closing...");
        evtSource.close();
    };
}

// --- LABEL TOGGLE ---
document.getElementById("labelBtn").addEventListener("click", () => {
    // Optimistic UI update
    labelState = labelState === 0 ? 10 : 0;
    
    fetch(`${API_BASE}/api/set_label`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: labelState }),
    }).catch((e) => console.error("Label error:", e));
});

// --- INIT ---
document.addEventListener("DOMContentLoaded", () => {
    // Gọi API để lấy thông tin cấu hình chuẩn từ Backend thay vì đọc URL params trống
    fetch(`${API_BASE}/api/config`)
        .then(res => res.json())
        .then(config => {
            const carId = config.car_id || "EV_101";
            const carName = config.car_name || "Unknown";
            const vin = config.vin || "N/A";

            document.getElementById("displayCarId").textContent = carId;
            document.getElementById("displayCarName").textContent = carName;
            document.getElementById("displayVin").textContent = vin;
        })
        .catch(err => console.error("Error loading vehicle config:", err));

    startSSE();
});
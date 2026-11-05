const REFRESH_INTERVAL = 300000; // 5 menit
const el = id => document.getElementById(id);
let selectedServerId = null;
let refreshTimer = null;
let knownServers = [];
let resourceChart = null;
let serverStatusChart = null;

function safe(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
}
function num(value, digits = 1) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed.toFixed(digits) : "0.0";
}
function setChip(id, status) {
    const node = el(id);
    if (!node) return;
    const value = String(status || "UNKNOWN").toUpperCase();
    node.textContent = value;
    node.className = "status-chip";
    if (["WARNING", "LATE"].includes(value)) node.classList.add("status-warning");
    else if (["CRITICAL", "FAILED", "DOWN", "OFFLINE"].includes(value)) node.classList.add("status-critical");
    else if (["UNKNOWN", "NO_DATA"].includes(value)) node.classList.add("status-unknown");
}
function setConnection(message, isError = false) {
    const node = el("connectionStatus");
    node.innerHTML = `<span class="footer-dot"></span>${safe(message)}`;
    node.classList.toggle("connection-error", isError);
}
function formatTime(value) {
    if (!value || value === "-") return "-";
    return String(value).replace("T", " ").replace(/\.\d+$/, "");
}
function initCharts() {
    const resourceCanvas = el("resourceChart");
    if (resourceCanvas && window.Chart) {
        resourceChart = new Chart(resourceCanvas, {
            type: "line",
            data: { labels: [], datasets: [
                { label: "CPU (%)", data: [], borderColor: "#3985ff", backgroundColor: "rgba(57,133,255,.12)", fill: true, tension: .36, pointRadius: 2, pointHoverRadius: 4, borderWidth: 2 },
                { label: "RAM (%)", data: [], borderColor: "#21c99a", backgroundColor: "rgba(33,201,154,.08)", fill: true, tension: .36, pointRadius: 2, pointHoverRadius: 4, borderWidth: 2 }
            ]},
            options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                interaction: { intersect: false, mode: "index" },
                plugins: { legend: { position: "top", align: "start", labels: { usePointStyle: true, boxWidth: 7, boxHeight: 7, padding: 18, color: "#7f8ba3", font: { family: "Inter", size: 10 } } }, tooltip: { backgroundColor: "#14245f", padding: 10, cornerRadius: 8 } },
                scales: {
                    x: { grid: { display: false }, ticks: { color: "#9aa4b7", maxTicksLimit: 7, maxRotation: 0, font: { family: "Inter", size: 9 }, callback: function(value) { const label = this.getLabelForValue(value); return String(label).slice(11, 16) || String(label).slice(0, 10); } }, border: { display: false } },
                    y: { min: 0, max: 100, grid: { color: "#edf0f6", drawTicks: false }, ticks: { stepSize: 25, color: "#9aa4b7", padding: 9, callback: value => value + "%", font: { family: "Inter", size: 9 } }, border: { display: false } }
                }
            }
        });
    }
    const statusCanvas = el("serverStatusChart");
    if (statusCanvas && window.Chart) {
        serverStatusChart = new Chart(statusCanvas, {
            type: "doughnut",
            data: { labels: ["Online", "Offline"], datasets: [{ data: [0, 0], backgroundColor: ["#25c99a", "#f06e9f"], borderWidth: 0, hoverOffset: 4 }] },
            options: { responsive: true, maintainAspectRatio: false, cutout: "76%", plugins: { legend: { display: false }, tooltip: { backgroundColor: "#14245f", padding: 10, cornerRadius: 8 } } }
        });
    }
}
function updateServerSummary(servers) {
    knownServers = Array.isArray(servers) ? servers : [];
    const online = knownServers.filter(server => String(server.device_status).toUpperCase() === "UP").length;
    const offline = Math.max(0, knownServers.length - online);
    el("totalServers").textContent = knownServers.length;
    el("onlineServers").textContent = online;
    el("onlineCaption").textContent = `${offline} server offline`;
    el("donutOnline").textContent = online;
    el("legendOnline").textContent = online;
    el("legendOffline").textContent = offline;
    if (serverStatusChart) {
        serverStatusChart.data.datasets[0].data = [online, offline];
        serverStatusChart.update("none");
    }
    const tbody = el("serverTable");
    if (!knownServers.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="table-empty">Belum ada server terdaftar. Tambahkan server melalui menu Kelola Server.</td></tr>';
        return;
    }
    tbody.innerHTML = knownServers.map(server => {
        const status = String(server.device_status || "UNKNOWN").toUpperCase();
        const chipClass = status === "UP" ? "" : status === "DOWN" ? "status-critical" : "status-unknown";
        return `<tr>
            <td class="server-name-cell" title="${safe(server.hostname)}">${safe(server.hostname)}</td>
            <td>${safe(server.ip_address || "-")}</td>
            <td><span class="status-chip ${chipClass}">${safe(status)}</span></td>
            <td><button type="button" class="table-action choose-server" data-server-id="${safe(server.id)}">Lihat</button></td>
        </tr>`;
    }).join("");
    tbody.querySelectorAll(".choose-server").forEach(button => button.addEventListener("click", () => {
        const select = el("serverSelect");
        select.value = button.dataset.serverId;
        select.dispatchEvent(new Event("change"));
        window.scrollTo({ top: 0, behavior: "smooth" });
    }));
}
async function loadServers() {
    try {
        const response = await fetch("/api/servers", { cache: "no-store" });
        if (response.status === 401 || response.redirected) { location.href = "/login"; return; }
        if (!response.ok) throw new Error("HTTP " + response.status);
        const servers = await response.json();
        updateServerSummary(servers);
        const select = el("serverSelect");
        if (!servers.length) {
            select.innerHTML = '<option value="">Belum ada server</option>';
            setConnection("Belum ada server terdaftar. Tambahkan server melalui Kelola Server.", true);
            return;
        }
        const requestedId = new URLSearchParams(location.search).get("server_id");
        const currentIdExists = servers.some(server => String(server.id) === String(selectedServerId));
        const initialId = servers.some(server => String(server.id) === requestedId) ? requestedId : currentIdExists ? String(selectedServerId) : String(servers[0].id);
        select.innerHTML = servers.map(server => `<option value="${safe(server.id)}">${safe(server.hostname)} (${safe(server.ip_address)}) · ${safe(server.device_status)}</option>`).join("");
        select.value = initialId;
        selectedServerId = initialId;
        if (!select.dataset.bound) {
            select.addEventListener("change", () => {
                selectedServerId = select.value;
                const params = new URLSearchParams(location.search);
                params.set("server_id", selectedServerId);
                history.replaceState(null, "", "?" + params.toString());
                loadDashboard();
            });
            select.dataset.bound = "1";
        }
        await loadDashboard();
        if (refreshTimer) clearInterval(refreshTimer);
        refreshTimer = setInterval(async () => { await loadServers(); }, REFRESH_INTERVAL);
    } catch (error) {
        console.error("Gagal memuat daftar server:", error);
        setConnection("Gagal memuat daftar server. Periksa Flask dan koneksi database.", true);
    }
}
async function loadDashboard() {
    if (!selectedServerId) return;
    try {
        const response = await fetch(`/api/monitoring?server_id=${encodeURIComponent(selectedServerId)}`, { cache: "no-store" });
        if (response.status === 401 || response.redirected) { location.href = "/login"; return; }
        if (!response.ok) {
            const detail = await response.json().catch(() => ({}));
            throw new Error(detail.error || "HTTP " + response.status);
        }
        const data = await response.json();
        el("cpuValue").innerHTML = `${num(data.cpu?.usage)}<small>%</small>`;
        el("ramValue").innerHTML = `${num(data.ram?.usage)}<small>%</small>`;
        setChip("cpuStatus", data.cpu?.status || "NO_DATA");
        setChip("ramStatus", data.ram?.status || "NO_DATA");
        const hostname = data.server?.hostname || "-";
        const ip = data.server?.ip_address || "-";
        el("serverName").textContent = hostname;
        el("ipAddress").textContent = ip;
        el("hostname").textContent = hostname;
        el("serverIpInfo").textContent = ip;
        el("lastUpdate").textContent = formatTime(data.updated_at);
        setChip("deviceBadge", data.server?.device_status || "UNKNOWN");
        const toGb = value => `${num(Number(value || 0) / 1024, 1)} GB`;
        el("ramUsed").textContent = toGb(data.ram?.used_mb);
        el("ramAvailable").textContent = toGb(data.ram?.available_mb);
        const backup = data.backup || {};
        setChip("backupValue", backup.status || "UNKNOWN");
        el("backupDetail").textContent = `${backup.name || "-"} · ${formatTime(backup.checked_at)} · ${backup.message || "Belum ada data backup."}`;
        const disks = Array.isArray(data.disks) ? data.disks : [];
        const diskBody = el("diskTable");
        if (!disks.length) {
            diskBody.innerHTML = '<tr><td colspan="6" class="table-empty">Belum ada data disk untuk server ini.</td></tr>';
        } else {
            diskBody.innerHTML = disks.map(disk => {
                const usage = Math.min(100, Math.max(0, Number(disk.usage || 0)));
                const fillClass = usage >= 85 ? "critical" : usage >= 70 ? "warning" : "";
                const status = String(disk.status || "UNKNOWN").toUpperCase();
                const statusClass = ["CRITICAL", "FAILED", "DOWN"].includes(status) ? "status-critical" : ["WARNING", "LATE"].includes(status) ? "status-warning" : ["UNKNOWN", "NO_DATA"].includes(status) ? "status-unknown" : "";
                return `<tr><td><strong>${safe(disk.drive || "-")}</strong></td><td>${num(disk.total_gb)} GB</td><td>${num(disk.used_gb)} GB</td><td>${num(disk.free_gb)} GB</td><td><div class="usage-cell"><span>${num(usage)}%</span><div class="usage-track"><div class="usage-fill ${fillClass}" style="width:${usage}%"></div></div></div></td><td><span class="status-chip ${statusClass}">${safe(status)}</span></td></tr>`;
            }).join("");
        }
        const history = Array.isArray(data.history) ? data.history : [];
        if (resourceChart) {
            resourceChart.data.labels = history.map(item => String(item.time || "").replace("T", " "));
            resourceChart.data.datasets[0].data = history.map(item => Number(item.cpu || 0));
            resourceChart.data.datasets[1].data = history.map(item => Number(item.ram || 0));
            resourceChart.update("none");
        }
        setConnection(`Terhubung · Data terakhir ${formatTime(data.updated_at)}`);
    } catch (error) {
        console.error("Gagal memuat monitoring:", error);
        setConnection("Gagal mengambil data monitoring. Periksa server dan database.", true);
    }
}
const mobileMenu = el("mobileMenu");
if (mobileMenu) mobileMenu.addEventListener("click", () => el("sidebar").classList.toggle("open"));
document.querySelectorAll(".side-link").forEach(link => link.addEventListener("click", () => {
    if (window.innerWidth <= 680) el("sidebar").classList.remove("open");
}));
initCharts();
loadServers();

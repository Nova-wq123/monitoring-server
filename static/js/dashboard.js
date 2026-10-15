const REFRESH_INTERVAL = 10000;

const el = id => document.getElementById(id);

let selectedServerId = null;
let refreshTimer = null;

function fmt(value) {
    return Number(value).toFixed(1);
}

function safe(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[c]);
}

function setStatus(id, status) {
    const node = el(id);
    node.textContent = status;
    node.className = "status";

    if (["WARNING", "LATE"].includes(status)) {
        node.classList.add("status-warning");
    } else if (
        ["CRITICAL", "FAILED", "DOWN"].includes(status)
    ) {
        node.classList.add("status-critical");
    } else if (
        ["UNKNOWN", "NO_DATA"].includes(status)
    ) {
        node.classList.add("status-unknown");
    }
}

const chart = new Chart(el("resourceChart"), {
    type: "line",
    data: {
        labels: [],
        datasets: [
            {
                label: "CPU (%)",
                data: [],
                borderColor: "#1769c2",
                backgroundColor: "#1769c220",
                fill: true,
                tension: 0.3
            },
            {
                label: "RAM (%)",
                data: [],
                borderColor: "#138957",
                backgroundColor: "#13895718",
                fill: true,
                tension: 0.3
            }
        ]
    },
    options: {
        responsive: true,
        animation: false,
        scales: {
            y: {
                min: 0,
                max: 100,
                ticks: {
                    callback: value => value + "%"
                }
            }
        }
    }
});

// ==========================================
// DAFTAR SERVER (DROPDOWN)
// ==========================================
async function loadServers() {
    const select = el("serverSelect");

    try {
        const response = await fetch("/api/servers", { cache: "no-store" });

        if (response.status === 401 || response.redirected) {
            location.href = "/login";
            return;
        }

        const servers = await response.json();

        if (!servers.length) {
            select.innerHTML = '<option value="">Belum ada server</option>';
            el("connectionStatus").textContent =
                "Belum ada server terdaftar. Tambahkan di menu Servers.";
            el("connectionStatus").style.color = "#c93434";
            return;
        }

        const urlParams = new URLSearchParams(location.search);
        const requestedId = urlParams.get("server_id");
        const initialId = servers.some(s => String(s.id) === requestedId)
            ? requestedId
            : String(servers[0].id);

        select.innerHTML = servers.map(s => `
            <option value="${s.id}">
                ${safe(s.hostname)} (${safe(s.ip_address)})
            </option>
        `).join("");

        select.value = initialId;
        selectedServerId = initialId;

        select.addEventListener("change", () => {
            selectedServerId = select.value;

            const params = new URLSearchParams(location.search);
            params.set("server_id", selectedServerId);
            history.replaceState(null, "", "?" + params.toString());

            // Server baru dipilih: kosongkan grafik lama lalu muat ulang.
            chart.data.labels = [];
            chart.data.datasets[0].data = [];
            chart.data.datasets[1].data = [];
            chart.update("none");

            loadDashboard();
        });

        startAutoRefresh();

    } catch (error) {
        console.error(error);
        el("connectionStatus").textContent =
            "Gagal memuat daftar server. Periksa Flask dan jaringan.";
        el("connectionStatus").style.color = "#c93434";
    }
}

function startAutoRefresh() {
    loadDashboard();

    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
    refreshTimer = setInterval(loadDashboard, REFRESH_INTERVAL);
}

// ==========================================
// DATA MONITORING SERVER TERPILIH
// ==========================================
async function loadDashboard() {
    if (!selectedServerId) {
        return;
    }

    try {
        const response = await fetch(
            `/api/monitoring?server_id=${encodeURIComponent(selectedServerId)}`,
            { cache: "no-store" }
        );

        if (response.status === 401 || response.redirected) {
            location.href = "/login";
            return;
        }

        if (!response.ok) {
            throw new Error("HTTP " + response.status);
        }

        const data = await response.json();

        el("cpuValue").textContent = fmt(data.cpu.usage) + "%";
        setStatus("cpuStatus", data.cpu.status);

        el("ramValue").textContent = fmt(data.ram.usage) + "%";
        setStatus("ramStatus", data.ram.status);

        el("deviceValue").textContent = data.server.device_status;
        setStatus("serverName", data.server.hostname);

        el("hostname").textContent = data.server.hostname;
        el("ipAddress").textContent = data.server.ip_address;
        el("lastUpdate").textContent = data.updated_at;

        const disks = data.disks || [];
        const tbody = el("diskTable");

        if (disks.length) {
            const maxDisk = disks.reduce(
                (a, b) => Number(b.usage) > Number(a.usage) ? b : a
            );

            el("diskValue").textContent = fmt(maxDisk.usage) + "%";
            setStatus("diskStatus", maxDisk.status);

            tbody.innerHTML = disks.map(d => `
                <tr>
                    <td>${safe(d.drive)}</td>
                    <td>${fmt(d.total_gb)}</td>
                    <td>${fmt(d.used_gb)}</td>
                    <td>${fmt(d.free_gb)}</td>
                    <td>${fmt(d.usage)}%</td>
                    <td><span class="status ${statusClass(d.status)}">
                        ${safe(d.status)}
                    </span></td>
                </tr>
            `).join("");
        } else {
            el("diskValue").textContent = "--";
            el("diskStatus").textContent = "Tidak ada data";
            el("diskStatus").className = "status status-unknown";
            tbody.innerHTML =
                '<tr><td colspan="6">Tidak ada data disk.</td></tr>';
        }

        const backup = data.backup;
        el("backupValue").textContent = backup.status;
        el("backupDetail").textContent =
            `${backup.name} · ${backup.checked_at} · ${backup.message}`;

        // Gunakan warna status untuk backup.
        el("backupValue").style.color =
            backup.status === "SUCCESS" ? "#138957" :
            backup.status === "FAILED" ? "#c93434" :
            backup.status === "LATE" ? "#bd790e" : "#71839a";

        chart.data.labels = data.history.map(item => item.time);
        chart.data.datasets[0].data =
            data.history.map(item => item.cpu);
        chart.data.datasets[1].data =
            data.history.map(item => item.ram);
        chart.update("none");

        el("connectionStatus").textContent =
            "Terhubung · Pembaruan terakhir " + data.updated_at;
        el("connectionStatus").style.color = "#138957";

    } catch (error) {
        console.error(error);
        el("connectionStatus").textContent =
            "Koneksi gagal. Periksa Flask, MySQL, dan jaringan.";
        el("connectionStatus").style.color = "#c93434";
    }
}

function statusClass(status) {
    if (status === "WARNING" || status === "LATE") {
        return "status-warning";
    }
    if (["CRITICAL", "FAILED", "DOWN"].includes(status)) {
        return "status-critical";
    }
    if (["UNKNOWN", "NO_DATA"].includes(status)) {
        return "status-unknown";
    }
    return "";
}

loadServers();

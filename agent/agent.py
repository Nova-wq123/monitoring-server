"""
Monitoring Agent - ENKEI Monitoring

Jalankan script ini di SETIAP server yang mau dipantau.
Script ambil data CPU/RAM/Disk lewat psutil, lalu kirim (push) ke
dashboard Flask tiap beberapa detik.

Cara pakai:
1. Daftarkan dulu hostname server ini di menu Servers pada dashboard
   (hostname di dashboard HARUS sama persis dengan hostname Windows server ini).
2. Set DASHBOARD_URL dan API_KEY di bawah sesuai config.py milik dashboard.
3. Jalankan: python agent.py
   (butuh psutil: pip install psutil)
"""

import json
import socket
import time
import urllib.error
import urllib.request

import psutil

# ==========================================
# KONFIGURASI AGENT
# ==========================================
DASHBOARD_URL = "http://127.0.0.1:5000"   # ganti dengan alamat server dashboard
API_KEY = "ganti-dengan-api-key-agent-yang-unik"  # samakan dengan config.py -> AGENT_API_KEY
INTERVAL_SECONDS = 10


def get_local_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
        finally:
            sock.close()
    except OSError:
        return "127.0.0.1"


def get_disk_usage():
    disks = []
    for partition in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(partition.mountpoint)
            disks.append({
                "drive_name": partition.mountpoint,
                "total_gb": round(usage.total / (1024 ** 3), 2),
                "used_gb": round(usage.used / (1024 ** 3), 2),
                "free_gb": round(usage.free / (1024 ** 3), 2),
                "usage_percentage": usage.percent
            })
        except (PermissionError, OSError):
            continue
    return disks


def collect_metrics():
    memory = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.3)

    return {
        "hostname": socket.gethostname(),
        "ip_address": get_local_ip(),
        "cpu_usage": cpu,
        "ram_usage": memory.percent,
        "ram_total_mb": round(memory.total / (1024 ** 2), 2),
        "ram_used_mb": round(memory.used / (1024 ** 2), 2),
        "ram_available_mb": round(memory.available / (1024 ** 2), 2),
        "disks": get_disk_usage()
    }


def send_report(metrics):
    data = json.dumps(metrics).encode("utf-8")
    request = urllib.request.Request(
        url=f"{DASHBOARD_URL.rstrip('/')}/api/agent/report",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
    )

    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, response.read().decode("utf-8")


def main():
    print(f"Agent monitoring jalan. Target dashboard: {DASHBOARD_URL}")
    print(f"Interval kirim data: {INTERVAL_SECONDS} detik. Tekan CTRL+C untuk berhenti.")

    while True:
        try:
            metrics = collect_metrics()
            status, body = send_report(metrics)
            print(f"[OK] {metrics['hostname']} terkirim, HTTP {status}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            print(f"[GAGAL] HTTP {exc.code}: {detail}")
        except urllib.error.URLError as exc:
            print(f"[GAGAL] Tidak bisa menghubungi dashboard: {exc.reason}")
        except Exception as exc:  # noqa: BLE001 - agent harus tetap jalan walau 1 siklus gagal
            print(f"[GAGAL] Error tidak terduga: {exc}")

        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

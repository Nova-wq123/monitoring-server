
import os
import csv
import io
import socket
import ipaddress
from datetime import datetime
from functools import wraps

import psutil
import mysql.connector
from mysql.connector import IntegrityError
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, flash, Response
)
from werkzeug.security import check_password_hash

from config import DB_CONFIG


# ==========================================
# KONFIGURASI APLIKASI
# ==========================================
app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "ganti-dengan-secret-key-yang-unik"
)


# ==========================================
# KONEKSI DATABASE
# ==========================================
def get_db():
    return mysql.connector.connect(**DB_CONFIG)


# ==========================================
# LOGIN WAJIB
# ==========================================
def login_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return function(*args, **kwargs)
    return wrapper


# ==========================================
# UTILITAS DATABASE
# ==========================================
def query_one(sql, params=()):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


def query_all(sql, params=()):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


# ==========================================
# LOGIN
# ==========================================
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            error = "Username dan password wajib diisi."
        else:
            try:
                user = query_one(
                    """
                    SELECT id, username, password, fullname
                    FROM users
                    WHERE username = %s
                    LIMIT 1
                    """,
                    (username,)
                )

                if user and check_password_hash(
                    user["password"], password
                ):
                    session.clear()
                    session["user_id"] = user["id"]
                    session["username"] = user["username"]
                    session["fullname"] = (
                        user.get("fullname") or user["username"]
                    )

                    # Simpan log login jika tabel tersedia.
                    try:
                        conn = get_db()
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                        login_logs (user_id, login_time)
                            VALUES (%s, NOW())
                            """,
                            (user["id"],)
                        )
                        conn.commit()
                        cursor.close()
                        conn.close()
                    except mysql.connector.Error:
                        pass

                    return redirect(url_for("dashboard"))

                error = "Username atau password salah."

            except mysql.connector.Error:
                error = "Database tidak dapat diakses. Periksa XAMPP dan config.py."

    return render_template("login.html", error=error)


# ==========================================
# LOGOUT
# ==========================================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ==========================================
# DASHBOARD
# ==========================================
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        fullname=session.get("fullname", "Administrator")
    )


# ==========================================
# STATUS SERVER LOKAL
# ==========================================
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
                "drive": partition.mountpoint,
                "total_gb": round(usage.total / (1024 ** 3), 2),
                "used_gb": round(usage.used / (1024 ** 3), 2),
                "free_gb": round(usage.free / (1024 ** 3), 2),
                "usage_percent": usage.percent,
                "status": "WARNING" if usage.percent >= 90 else "NORMAL"
            })
        except (PermissionError, OSError):
            continue

    return disks


def get_local_metrics():
    memory = psutil.virtual_memory()
    disks = get_disk_usage()

    cpu = psutil.cpu_percent(interval=0.3)
    disk_max = max(
        [item["usage_percent"] for item in disks],
        default=0
    )

    return {
        "hostname": socket.gethostname(),
        "ip_address": get_local_ip(),
        "cpu_usage": cpu,
        "ram_usage": memory.percent,
        "ram_total_mb": round(memory.total / (1024 ** 2), 2),
        "ram_used_mb": round(memory.used / (1024 ** 2), 2),
        "ram_available_mb": round(memory.available / (1024 ** 2), 2),
        "disk_usage": disk_max,
        "device_status": "UP",
        "disks": disks,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


# ==========================================
# API MONITORING
# Mengukur komputer tempat Flask berjalan.
# ==========================================
@app.route("/api/monitoring")
@login_required
def api_monitoring():
    try:
        metrics = get_local_metrics()

        cpu_status = (
            "WARNING" if metrics["cpu_usage"] >= 80 else "NORMAL"
        )
        ram_status = (
            "WARNING" if metrics["ram_usage"] >= 80 else "NORMAL"
        )

        # Ambil server pertama sebagai tujuan penyimpanan histori.
        server = query_one(
            "SELECT id FROM servers ORDER BY id LIMIT 1"
        )

        if server:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO monitoring
                (
                    server_id, cpu_usage, ram_usage,
                    ram_total_mb, ram_used_mb, ram_available_mb,
                    cpu_status, ram_status, collected_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    server["id"],
                    metrics["cpu_usage"],
                    metrics["ram_usage"],
                    metrics["ram_total_mb"],
                    metrics["ram_used_mb"],
                    metrics["ram_available_mb"],
                    cpu_status,
                    ram_status
                )
            )
            conn.commit()
            cursor.close()
            conn.close()

        history = query_all(
            """
            SELECT cpu_usage, ram_usage, collected_at
            FROM monitoring
            ORDER BY collected_at DESC
            LIMIT 20
            """
        )

        history.reverse()

        metrics["history"] = [
            {
                "cpu": float(row["cpu_usage"] or 0),
                "ram": float(row["ram_usage"] or 0),
                "time": str(row["collected_at"])
            }
            for row in history
        ]

        return jsonify(metrics)

    except mysql.connector.Error as exc:
        app.logger.exception("Monitoring database error")
        return jsonify({
            "error": "Gagal membaca atau menyimpan data monitoring.",
            "detail": str(exc)
        }), 500

    except Exception:
        app.logger.exception("Monitoring error")
        return jsonify({
            "error": "Gagal mengambil data komputer."
        }), 500


# ==========================================
# API STATUS BACKUP
# ==========================================
@app.route("/api/backup")
@login_required
def api_backup():
    try:
        row = query_one(
            """
            SELECT status, backup_time, details
            FROM backup_monitoring
            ORDER BY backup_time DESC
            LIMIT 1
            """
        )

        if not row:
            return jsonify({
                "status": "UNKNOWN",
                "backup_time": None,
                "details": "Belum ada data backup."
            })

        return jsonify({
            "status": row.get("status") or "UNKNOWN",
            "backup_time": str(row.get("backup_time") or ""),
            "details": row.get("details") or ""
        })

    except mysql.connector.Error:
        return jsonify({
            "status": "UNKNOWN",
            "backup_time": None,
            "details": "Data backup belum tersedia."
        })


# ==========================================
# DAFTAR SERVER
# ==========================================
@app.route("/servers")
@login_required
def servers():
    data = query_all(
        """
        SELECT id, hostname, ip_address, os_name,
               location, description, device_status
        FROM servers
        ORDER BY hostname
        """
    )

    return render_template(
        "servers.html",
        servers=data,
        fullname=session.get("fullname", "Administrator")
    )


# ==========================================
# TAMBAH SERVER
# ==========================================
@app.route("/servers/add", methods=["GET", "POST"])
@login_required
def server_add():
    if request.method == "POST":
        hostname = request.form.get("hostname", "").strip()
        ip_address = request.form.get("ip_address", "").strip()
        os_name = request.form.get("os_name", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        status = request.form.get("device_status", "DOWN").upper()

        if not hostname or not ip_address:
            flash("Hostname dan IP address wajib diisi.", "error")
            return redirect(url_for("server_add"))

        try:
            ipaddress.ip_address(ip_address)

            if status not in ("UP", "DOWN"):
                raise ValueError("Status tidak valid.")

            conn = get_db()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO servers
                    (hostname, ip_address, os_name, location,
                     description, device_status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        hostname, ip_address, os_name or None,
                        location or None, description or None, status
                    )
                )
                conn.commit()
            finally:
                cursor.close()
                conn.close()

            flash("Server berhasil ditambahkan.", "success")
            return redirect(url_for("servers"))

        except ValueError:
            flash("Format IP address atau status tidak valid.", "error")
        except IntegrityError:
            flash("Hostname atau IP mungkin sudah terdaftar.", "error")
        except mysql.connector.Error:
            app.logger.exception("Gagal menambah server")
            flash("Gagal menyimpan server. Periksa struktur database.", "error")

    return render_template(
        "server_form.html",
        server=None,
        fullname=session.get("fullname", "Administrator")
    )


# ==========================================
# EDIT SERVER
# ==========================================
@app.route("/servers/<int:server_id>/edit", methods=["GET", "POST"])
@login_required
def server_edit(server_id):
    server = query_one(
        """
        SELECT id, hostname, ip_address, os_name,
               location, description, device_status
        FROM servers
        WHERE id = %s
        """,
        (server_id,)
    )

    if not server:
        flash("Server tidak ditemukan.", "error")
        return redirect(url_for("servers"))

    if request.method == "POST":
        hostname = request.form.get("hostname", "").strip()
        ip_address = request.form.get("ip_address", "").strip()
        os_name = request.form.get("os_name", "").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        status = request.form.get("device_status", "DOWN").upper()

        if not hostname or not ip_address:
            flash("Hostname dan IP address wajib diisi.", "error")
            return redirect(url_for("server_edit", server_id=server_id))

        try:
            ipaddress.ip_address(ip_address)

            if status not in ("UP", "DOWN"):
                raise ValueError("Status tidak valid.")

            conn = get_db()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    UPDATE servers
                    SET hostname=%s, ip_address=%s, os_name=%s,
                        location=%s, description=%s, device_status=%s
                    WHERE id=%s
                    """,
                    (
                        hostname, ip_address, os_name or None,
                        location or None, description or None,
                        status, server_id
                    )
                )
                conn.commit()
            finally:
                cursor.close()
                conn.close()

            flash("Data server berhasil diperbarui.", "success")
            return redirect(url_for("servers"))

        except ValueError:
            flash("Format IP address atau status tidak valid.", "error")
        except IntegrityError:
            flash("Hostname atau IP mungkin sudah digunakan.", "error")
        except mysql.connector.Error:
            app.logger.exception("Gagal mengedit server")
            flash("Gagal memperbarui data server.", "error")

    return render_template(
        "server_form.html",
        server=server,
        fullname=session.get("fullname", "Administrator")
    )


# ==========================================
# HAPUS SERVER
# ==========================================
@app.route("/servers/<int:server_id>/delete", methods=["POST"])
@login_required
def server_delete(server_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM servers WHERE id=%s",
            (server_id,)
        )
        conn.commit()

        if cursor.rowcount:
            flash("Server berhasil dihapus.", "success")
        else:
            flash("Server tidak ditemukan.", "error")

    except mysql.connector.Error:
        conn.rollback()
        app.logger.exception("Gagal menghapus server")
        flash(
            "Server tidak dapat dihapus. Periksa relasi data monitoring.",
            "error"
        )

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("servers"))


# ==========================================
# EXPORT RIWAYAT MONITORING KE CSV / EXCEL
# ==========================================
@app.route("/export/monitoring.csv")
@login_required
def export_monitoring():
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT s.hostname, s.ip_address,
                   m.cpu_usage, m.ram_usage,
                   m.ram_total_mb, m.ram_used_mb,
                   m.ram_available_mb, m.cpu_status,
                   m.ram_status, m.collected_at
            FROM monitoring m
            JOIN servers s ON s.id = m.server_id
            ORDER BY m.collected_at DESC
            """
        )

        output = io.StringIO(newline="")
        writer = csv.writer(output, delimiter=";")

        writer.writerow([
            "Hostname", "IP Address", "CPU Usage (%)",
            "RAM Usage (%)", "RAM Total (MB)",
            "RAM Terpakai (MB)", "RAM Tersedia (MB)",
            "Status CPU", "Status RAM", "Waktu Monitoring"
        ])

        writer.writerows(cursor.fetchall())

        response = Response(
            "\ufeff" + output.getvalue(),
            mimetype="text/csv; charset=utf-8"
        )
        response.headers["Content-Disposition"] = (
            "attachment; filename=riwayat_monitoring_enkei.csv"
        )
        return response

    finally:
        cursor.close()
        conn.close()


# ==========================================
# JALANKAN APLIKASI
# ==========================================
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
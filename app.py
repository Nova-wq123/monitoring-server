import os
import csv
import io
import ipaddress
from datetime import datetime
from functools import wraps

import mysql.connector
from mysql.connector import IntegrityError
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, flash, Response
)
from werkzeug.security import check_password_hash

from config import DB_CONFIG, AGENT_API_KEY

# Server dianggap OFFLINE jika tidak kirim data lebih dari sekian detik.
OFFLINE_AFTER_SECONDS = 60

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
                    SELECT id, username, password_hash, fullname, role
                    FROM users
                    WHERE username = %s
                    LIMIT 1
                    """,
                    (username,)
                )

                if user and check_password_hash(
                    user["password_hash"], password
                ):
                    session.clear()
                    session["user_id"] = user["id"]
                    session["username"] = user["username"]
                    session["fullname"] = (
                        user.get("fullname") or user["username"]
                    )
                    session["role"] = user.get("role") or "MANAGER"

                    try:
                        conn = get_db()
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            INSERT INTO login_logs (user_id, login_time)
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

            except mysql.connector.Error as exc:
                print("LOGIN DATABASE ERROR:", exc)
                error = "Terjadi kesalahan saat membaca database."

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
# UTILITAS STATUS SERVER
# ==========================================
def compute_device_status(last_seen):
    """UP jika agent masih kirim data dalam OFFLINE_AFTER_SECONDS, selain itu DOWN."""
    if not last_seen:
        return "DOWN"

    age = (datetime.now() - last_seen).total_seconds()
    return "UP" if age <= OFFLINE_AFTER_SECONDS else "DOWN"


def status_by_threshold(value, warning_at, critical_at):
    if value >= critical_at:
        return "CRITICAL"
    if value >= warning_at:
        return "WARNING"
    return "NORMAL"


# ==========================================
# DAFTAR SERVER UNTUK DROPDOWN DASHBOARD
# ==========================================
@app.route("/api/servers")
@login_required
def api_servers():
    rows = query_all(
        """
        SELECT id, hostname, ip_address, last_seen
        FROM servers
        ORDER BY hostname
        """
    )

    return jsonify([
        {
            "id": row["id"],
            "hostname": row["hostname"],
            "ip_address": row["ip_address"],
            "device_status": compute_device_status(row["last_seen"])
        }
        for row in rows
    ])


# ==========================================
# API MONITORING (dibaca dashboard)
# Menampilkan data terakhir yang dikirim agent untuk satu server.
# ==========================================
@app.route("/api/monitoring")
@login_required
def api_monitoring():
    try:
        server_id = request.args.get("server_id", type=int)

        server = query_one(
            """
            SELECT id, hostname, ip_address, last_seen
            FROM servers
            WHERE id = %s
            """,
            (server_id,)
        ) if server_id else query_one(
            "SELECT id, hostname, ip_address, last_seen FROM servers ORDER BY hostname LIMIT 1"
        )

        if not server:
            return jsonify({
                "error": "Belum ada server terdaftar. Tambahkan server terlebih dahulu."
            }), 404

        device_status = compute_device_status(server["last_seen"])

        latest = query_one(
            """
            SELECT cpu_usage, ram_usage, ram_total_mb, ram_used_mb,
                   ram_available_mb, cpu_status, ram_status, collected_at
            FROM monitoring
            WHERE server_id = %s
            ORDER BY collected_at DESC
            LIMIT 1
            """,
            (server["id"],)
        )

        disk_rows = query_all(
            """
            SELECT dm.drive_name, dm.total_gb, dm.used_gb, dm.free_gb,
                   dm.usage_percentage, dm.disk_status
            FROM disk_monitoring dm
            INNER JOIN (
                SELECT drive_name, MAX(collected_at) AS max_time
                FROM disk_monitoring
                WHERE server_id = %s
                GROUP BY drive_name
            ) latest_disk
              ON latest_disk.drive_name = dm.drive_name
             AND latest_disk.max_time = dm.collected_at
            WHERE dm.server_id = %s
            ORDER BY dm.drive_name
            """,
            (server["id"], server["id"])
        )

        backup_row = query_one(
            """
            SELECT backup_name, backup_status, message, checked_at
            FROM backup_monitoring
            WHERE server_id = %s
            ORDER BY checked_at DESC
            LIMIT 1
            """,
            (server["id"],)
        )

        history = query_all(
            """
            SELECT cpu_usage, ram_usage, collected_at
            FROM monitoring
            WHERE server_id = %s
            ORDER BY collected_at DESC
            LIMIT 20
            """,
            (server["id"],)
        )

        history.reverse()

        response = {
            "cpu": {
                "usage": float((latest or {}).get("cpu_usage") or 0),
                "status": (latest or {}).get("cpu_status") or "NO_DATA"
            },
            "ram": {
                "usage": float((latest or {}).get("ram_usage") or 0),
                "status": (latest or {}).get("ram_status") or "NO_DATA",
                "total_mb": float((latest or {}).get("ram_total_mb") or 0),
                "used_mb": float((latest or {}).get("ram_used_mb") or 0),
                "available_mb": float((latest or {}).get("ram_available_mb") or 0)
            },
            "server": {
                "hostname": server["hostname"],
                "ip_address": server["ip_address"],
                "device_status": device_status
            },
            "disks": [
                {
                    "drive": row["drive_name"],
                    "total_gb": float(row["total_gb"] or 0),
                    "used_gb": float(row["used_gb"] or 0),
                    "free_gb": float(row["free_gb"] or 0),
                    "usage": float(row["usage_percentage"] or 0),
                    "status": row["disk_status"]
                }
                for row in disk_rows
            ],
            "backup": {
                "status": (backup_row or {}).get("backup_status") or "UNKNOWN",
                "name": (backup_row or {}).get("backup_name") or "-",
                "checked_at": str((backup_row or {}).get("checked_at") or "-"),
                "message": (backup_row or {}).get("message") or "Belum ada data backup."
            },
            "updated_at": str(
                (latest or {}).get("collected_at")
                or server["last_seen"]
                or "-"
            ),
            "history": [
                {
                    "cpu": float(row["cpu_usage"] or 0),
                    "ram": float(row["ram_usage"] or 0),
                    "time": str(row["collected_at"])
                }
                for row in history
            ]
        }
        return jsonify(response)

    except mysql.connector.Error as exc:
        app.logger.exception("Monitoring database error")
        return jsonify({
            "error": "Gagal membaca data monitoring.",
            "detail": str(exc)
        }), 500


# ==========================================
# API INGEST (dipanggil agent.py di tiap server)
# ==========================================

@app.route("/api/agent/report", methods=["POST"])
def api_agent_report():
    if request.headers.get("X-API-Key") != AGENT_API_KEY:
        return jsonify({"error": "API key tidak valid."}), 401

    payload = request.get_json(silent=True) or {}

    hostname = (payload.get("hostname") or "").strip()
    ip_address = (payload.get("ip_address") or "").strip()

    if not hostname:
        return jsonify({"error": "Hostname wajib diisi."}), 400

    try:
        cpu_usage = float(payload.get("cpu_usage", 0))
        ram_usage = float(payload.get("ram_usage", 0))
        ram_total_mb = float(payload.get("ram_total_mb", 0))
        ram_used_mb = float(payload.get("ram_used_mb", 0))
        ram_available_mb = float(payload.get("ram_available_mb", 0))
        disks = payload.get("disks") or []
        backup = payload.get("backup")

        if not 0 <= cpu_usage <= 100 or not 0 <= ram_usage <= 100:
            raise ValueError("Persentase CPU/RAM tidak valid.")

    except (TypeError, ValueError):
        return jsonify({
            "error": "Format data monitoring tidak valid."
        }), 400

    server = query_one(
        "SELECT id FROM servers WHERE hostname = %s",
        (hostname,)
    )

    if not server:
        return jsonify({
            "error": f"Server '{hostname}' belum terdaftar."
        }), 404

    conn = get_db()
    cursor = conn.cursor()

    try:
        # Perbarui status server (kolom device_status, enum UP/DOWN).
        cursor.execute(
            """
            UPDATE servers
            SET last_seen = NOW(),
                device_status = 'UP',
                ip_address = COALESCE(NULLIF(%s, ''), ip_address)
            WHERE id = %s
            """,
            (ip_address, server["id"])
        )

        cpu_status = status_by_threshold(cpu_usage, 70, 85)
        ram_status = status_by_threshold(ram_usage, 75, 90)

        # Simpan data CPU dan RAM sesuai tabel monitoring.
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
                server["id"], cpu_usage, ram_usage,
                ram_total_mb, ram_used_mb, ram_available_mb,
                cpu_status, ram_status
            )
        )

        # Simpan data disk sesuai tabel disk_monitoring.
        # agent.py mengirim ukuran disk dengan key total_space/used_space/free_space.
        for disk in disks:
            if not isinstance(disk, dict):
                continue

            try:
                drive_name = str(
                    disk.get("drive_name") or ""
                ).strip()

                if not drive_name:
                    continue

                total_gb = float(
                    disk.get("total_space", disk.get("total_gb", 0))
                )
                used_gb = float(
                    disk.get("used_space", disk.get("used_gb", 0))
                )
                free_gb = float(
                    disk.get("free_space", disk.get("free_gb", 0))
                )
                usage_percentage = float(
                    disk.get("usage_percentage", 0)
                )

                if not 0 <= usage_percentage <= 100:
                    continue

                disk_status = status_by_threshold(usage_percentage, 80, 90)

                cursor.execute(
                    """
                    INSERT INTO disk_monitoring
                    (
                        server_id, drive_name, total_gb, used_gb,
                        free_gb, usage_percentage, disk_status, collected_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        server["id"], drive_name,
                        total_gb, used_gb, free_gb,
                        usage_percentage, disk_status
                    )
                )

            except (TypeError, ValueError):
                continue

        # Simpan hasil pemeriksaan backup yang dikirim agent.
        # Tabel backup_monitoring hanya menerima status
        # SUCCESS/LATE/FAILED/UNKNOWN; status lain (mis. INFO) dipetakan UNKNOWN.
        if isinstance(backup, dict) and backup:
            backup_name = str(
                backup.get("backup_name") or "Windows Backup"
            ).strip()[:150]
            backup_status = str(
                backup.get("backup_status") or "UNKNOWN"
            ).strip().upper()
            allowed_backup_statuses = {
                "SUCCESS", "LATE", "FAILED", "UNKNOWN"
            }
            if backup_status not in allowed_backup_statuses:
                backup_status = "UNKNOWN"

            backup_message = str(
                backup.get("message") or ""
            ).strip()[:1000]

            cursor.execute(
                """
                INSERT INTO backup_monitoring
                    (server_id, backup_name, backup_status, message, checked_at)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (
                    server["id"], backup_name, backup_status,
                    backup_message
                )
            )

        conn.commit()

        return jsonify({
            "status": "ok",
            "message": "Data monitoring berhasil disimpan.",
            "hostname": hostname
        }), 200

    except mysql.connector.Error as exc:
        conn.rollback()
        app.logger.exception("Gagal menyimpan data agent")

        return jsonify({
            "error": "Gagal menyimpan data monitoring.",
            "detail": str(exc)
        }), 500

    finally:
        cursor.close()
        conn.close()

# ==========================================
# API STATUS BACKUP
# ==========================================
@app.route("/api/backup")
@login_required
def api_backup():
    try:
        row = query_one(
            """
            SELECT backup_status, checked_at, message
            FROM backup_monitoring
            ORDER BY checked_at DESC
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
            "status": row.get("backup_status") or "UNKNOWN",
            "backup_time": str(row.get("checked_at") or ""),
            "details": row.get("message") or ""
        })

    except mysql.connector.Error:
        app.logger.exception("Gagal membaca status backup")
        return jsonify({
            "status": "UNKNOWN",
            "backup_time": None,
            "details": "Gagal membaca data backup."
        }), 500
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
            try:
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
                            hostname,
                            ip_address,
                            os_name or None,
                            location or None,
                            description or None,
                            status
                        )
                    )
                    conn.commit()
                finally:
                    cursor.close()
            finally:
                conn.close()

            flash("Server berhasil ditambahkan.", "success")
            return redirect(url_for("servers"))

        except ValueError:
            flash("Format IP address atau status tidak valid.", "error")

        except IntegrityError:
            flash("Hostname atau IP mungkin sudah terdaftar.", "error")

        except mysql.connector.Error:
            app.logger.exception("Gagal menambah server")
            flash(
                "Gagal menyimpan server. Periksa error pada terminal.",
                "error"
            )

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
                   m.ram_total, m.ram_used,
                   m.ram_available, m.status, m.created_at
            FROM monitoring m
            JOIN servers s ON s.id = m.server_id
            ORDER BY m.created_at DESC
            """
        )

        output = io.StringIO(newline="")
        writer = csv.writer(output, delimiter=";")
        writer.writerow([
            "Hostname", "IP Address", "CPU Usage (%)",
            "RAM Usage (%)", "RAM Total (MB)",
            "RAM Terpakai (MB)", "RAM Tersedia (MB)",
            "Status Monitoring", "Waktu Monitoring"
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
    app.run(debug=False, host="0.0.0.0", port=5000)
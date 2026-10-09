# PRD - Windows Server Monitoring System

**Version:** 1.0
**Project:** Windows Server Monitoring Dashboard
**Platform:** Web Application
**Backend:** Python 3.11.9 (Flask)
**Database:** MySQL (XAMPP 3.0.0)
**Frontend:** HTML, CSS, Bootstrap 5, JavaScript, Chart.js

---

# 1. Project Overview

## Background

Tim IT membutuhkan aplikasi monitoring Windows Server yang dapat memantau kondisi server secara real-time melalui dashboard web.

Saat ini proses monitoring dilakukan secara manual sehingga membutuhkan waktu lebih lama untuk mengetahui kondisi server.

Aplikasi ini bertujuan untuk membantu tim IT melakukan monitoring secara terpusat dan menyimpan seluruh data monitoring ke database MySQL.

---

# 2. Objectives

Sistem harus mampu:

- Monitoring CPU Usage
- Monitoring RAM Usage
- Monitoring Disk Usage
- Monitoring Device Status
- Monitoring Backup Status
- Menyimpan histori monitoring
- Menampilkan dashboard real-time
- Menampilkan grafik monitoring
- Menampilkan status warning dan critical

---

# 3. Scope

## In Scope

### Monitoring Resource

- CPU Usage
- RAM Usage
- Disk Usage
- Device Status
- Backup Status

### Dashboard

- Monitoring Real-Time
- Monitoring History
- Detail Server
- Status Server
- Charts

### Database

- Menyimpan seluruh data monitoring
- Menyimpan histori monitoring
- Menyimpan status backup

---

# 4. Technology Stack

## Backend

- Python 3.11.9
- Flask
- Flask-SQLAlchemy
- REST A

## Monitoring Library

- psutil

## Database

- MySQL
- XAMPP 3.0.0

## Frontend

- HTML5
- CSS3
- Bootstrap 5
- JavaScript
- Chart.js

## Development Tools

- Visual Studio Code
- Git

---

# 5. System Architecture

```text
Windows Server
       │
       ▼
Monitoring Agent (Python)
       │
       ▼
REST API Flask
       │
       ▼
MySQL Database
       │
       ▼
Web Dashboard
```

---

# 6. Functional Requirements

## FR-01 CPU Monitoring

### Description

Sistem harus dapat mengambil data penggunaan CPU server.

### Data

| Field | Type |
|---------|---------|
| cpu_usage | Float |
| timestamp | Datetime |

### Rules

| Value | Status |
|---------|---------|
| 0-69 | Normal |
| 70-84 | Warning |
| 85-100 | Critical |

---

## FR-02 RAM Monitoring

### Description

Sistem harus mengambil informasi RAM server.

### Data

| Field | Type |
|---------|---------|
| ram_total | Float |
| ram_used | Float |
| ram_available | Float |
| ram_percentage | Float |

### Rules

| Value | Status |
|---------|---------|
| 0-69 | Normal |
| 70-84 | Warning |
| 85-100 | Critical |

---

## FR-03 Disk Monitoring

### Description

Sistem harus memonitor seluruh drive server.

### Data

| Field | Type |
|---------|---------|
| drive_name | String |
| total_space | Float |
| used_space | Float |
| free_space | Float |
| percentage | Float |

### Rules

| Value | Status |
|---------|---------|
| 0-79 | Normal |
| 80-89 | Warning |
| 90-100 | Critical |

---

## FR-04 Device Status

### Description

Sistem harus mengetahui kondisi server.

### Status

```text
ONLINE
OFFLINE
WARNING
```

### Logic

ONLINE:
Agent mengirim data monitoring.

OFFLINE:
Tidak ada data lebih dari 60 detik.

WARNING:
Terdapat resource yang melewati threshold.

---

## FR-05 Backup Status

### Description

Sistem harus memonitor status backup server.

### Status

```text
SUCCESS
FAILED
WARNING
NO DATA
```

### Data

| Field | Type |
|---------|---------|
| backup_name | String |
| backup_status | String |
| backup_time | Datetime |
| message | Text |

---

# 7. Dashboard Requirements

## Dashboard Overview

Dashboard menampilkan:

- Total Server
- Online Server
- Offline Server
- Warning Server
- CPU Usage
- RAM Usage
- Disk Usage
- Backup Status

---

## Real-Time Monitoring

Refresh otomatis setiap:

```text
10 detik
```

Tanpa refresh browser.

Menggunakan:

- AJAX
- Fetch API

---

## Charts

Dashboard harus memiliki:

### CPU Usage Chart

Menampilkan histori CPU.

### RAM Usage Chart

Menampilkan histori RAM.

### Disk Usage Chart

Menampilkan histori Disk.

Menggunakan:

```text
Chart.js
```

---

# 8. Database Design

## Database Name

```sql
server_monitoring
```

---

## Table users

```sql
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50),
    password VARCHAR(255),
    name VARCHAR(100),
    role VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Table servers

```sql
CREATE TABLE servers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    hostname VARCHAR(100),
    ip_address VARCHAR(50),
    os_name VARCHAR(100),
    location VARCHAR(100),
    status VARCHAR(20),
    last_seen DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Table monitoring

```sql
CREATE TABLE monitoring (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    server_id INT,
    cpu_usage FLOAT,
    ram_usage FLOAT,
    ram_total FLOAT,
    ram_used FLOAT,
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Table disk_monitoring

```sql
CREATE TABLE disk_monitoring (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    server_id INT,
    drive_name VARCHAR(20),
    disk_total FLOAT,
    disk_used FLOAT,
    disk_free FLOAT,
    disk_percentage FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Table backup_monitoring

```sql
CREATE TABLE backup_monitoring (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    server_id INT,
    backup_name VARCHAR(100),
    backup_status VARCHAR(20),
    backup_time DATETIME,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

# 9. API Specification

## POST Monitoring

```http
POST /api/monitoring
```

### Request

```json
{
  "hostname":"SERVER-01",
  "cpu":35,
  "ram":45,
  "status":"ONLINE"
}
```

---

## GET Servers

```http
GET /api/servers
```

---

## GET Server Detail

```http
GET /api/server/{id}
```

---

## GET Monitoring History

```http
GET /api/history
```

---

## GET Backup Status

```http
GET /api/backup
```

---

# 10. Folder Structure

```text
server_monitoring/
│
├── app.py
├── config.py
├── requirements.txt
│
├── agent/
│   └── agent.py
│
├── routes/
│   ├── api.py
│   ├── dashboard.py
│   └── server.py
│
├── models/
│   ├── server.py
│   ├── monitoring.py
│   └── backup.py
│
├── templates/
│   ├── login.html
│   ├── dashboard.html
│   ├── servers.html
│   ├── detail.html
│   └── history.html
│
├── static/
│   ├── css/
│   ├── js/
│   └── img/
│
└── database/
    └── server_monitoring.sql
```

---

# 11. Future Development

- Email Alert
- Telegram Alert
- WhatsApp Alert
- Multi Server Monitoring
- Active Directory Integration
- PDF Report Export
- Excel Report Export
- Docker Deployment
- SSL Security

---

# 12. Success Criteria

Project dianggap berhasil apabila:

- CPU Monitoring berjalan
- RAM Monitoring berjalan
- Disk Monitoring berjalan
- Device Status berjalan
- Backup Status berjalan
- Dashboard Real-Time berjalan
- Data tersimpan ke MySQL
- Monitoring History tersimpan
- Grafik Monitoring tampil
- Status Online/Offline tampil
- Alert Warning dan Critical berjalan
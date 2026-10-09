-- DATABASE: server_monitoring_v2
-- Windows Server Monitoring Dashboard
-- Threshold awal:
-- CPU: Normal <70%, Warning 70-85%, Critical >85%
-- RAM: Normal <75%, Warning 75-90%, Critical >90%
-- Disk: Normal <80%, Warning 80-90%, Critical >90%
-- Device: UP / DOWN
-- Backup: SUCCESS / LATE / FAILED / UNKNOWN
-- Database baru dipakai agar tabel lama tidak tertimpa.

CREATE DATABASE IF NOT EXISTS server_monitoring_v2
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE server_monitoring_v2;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    fullname VARCHAR(100) NOT NULL,
    role ENUM('ADMIN','MANAGER') NOT NULL DEFAULT 'ADMIN',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS servers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    hostname VARCHAR(100) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    os_name VARCHAR(100),
    location VARCHAR(100),
    description TEXT,
    device_status ENUM('UP','DOWN') NOT NULL DEFAULT 'DOWN',
    last_seen DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_servers_hostname (hostname),
    INDEX idx_servers_status (device_status),
    INDEX idx_servers_last_seen (last_seen)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS monitoring (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    server_id INT NOT NULL,
    cpu_usage DECIMAL(5,2) NOT NULL,
    ram_total_mb DECIMAL(12,2) NOT NULL,
    ram_used_mb DECIMAL(12,2) NOT NULL,
    ram_available_mb DECIMAL(12,2) NOT NULL,
    ram_usage DECIMAL(5,2) NOT NULL,
    cpu_status ENUM('NORMAL','WARNING','CRITICAL') NOT NULL,
    ram_status ENUM('NORMAL','WARNING','CRITICAL') NOT NULL,
    collected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_monitoring_server FOREIGN KEY (server_id)
      REFERENCES servers(id) ON UPDATE CASCADE ON DELETE CASCADE,
    INDEX idx_monitoring_server_time (server_id, collected_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS disk_monitoring (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    server_id INT NOT NULL,
    drive_name VARCHAR(10) NOT NULL,
    total_gb DECIMAL(12,2) NOT NULL,
    used_gb DECIMAL(12,2) NOT NULL,
    free_gb DECIMAL(12,2) NOT NULL,
    usage_percentage DECIMAL(5,2) NOT NULL,
    disk_status ENUM('NORMAL','WARNING','CRITICAL') NOT NULL,
    collected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_disk_server FOREIGN KEY (server_id)
      REFERENCES servers(id) ON UPDATE CASCADE ON DELETE CASCADE,
    INDEX idx_disk_server_drive_time (server_id, drive_name, collected_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS backup_monitoring (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    server_id INT NOT NULL,
    backup_name VARCHAR(150) NOT NULL,
    backup_status ENUM('SUCCESS','LATE','FAILED','UNKNOWN') NOT NULL DEFAULT 'UNKNOWN',
    backup_started_at DATETIME NULL,
    backup_finished_at DATETIME NULL,
    message TEXT,
    checked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_backup_server FOREIGN KEY (server_id)
      REFERENCES servers(id) ON UPDATE CASCADE ON DELETE CASCADE,
    INDEX idx_backup_server_time (server_id, checked_at),
    INDEX idx_backup_status (backup_status)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS monitoring_thresholds (
    id INT AUTO_INCREMENT PRIMARY KEY,
    parameter_name ENUM('CPU','RAM','DISK') NOT NULL UNIQUE,
    normal_below DECIMAL(5,2) NOT NULL,
    warning_from DECIMAL(5,2) NOT NULL,
    warning_to DECIMAL(5,2) NOT NULL,
    critical_above DECIMAL(5,2) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

INSERT INTO monitoring_thresholds
(parameter_name, normal_below, warning_from, warning_to, critical_above)
VALUES
('CPU', 70.00, 70.00, 85.00, 85.00),
('RAM', 75.00, 75.00, 90.00, 90.00),
('DISK', 80.00, 80.00, 90.00, 90.00)
ON DUPLICATE KEY UPDATE
normal_below = VALUES(normal_below),
warning_from = VALUES(warning_from),
warning_to = VALUES(warning_to),
critical_above = VALUES(critical_above);

CREATE TABLE IF NOT EXISTS alert_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    server_id INT NOT NULL,
    alert_type ENUM('CPU','RAM','DISK','DEVICE','BACKUP') NOT NULL,
    severity ENUM('WARNING','CRITICAL') NOT NULL,
    message TEXT NOT NULL,
    is_resolved TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME NULL,
    CONSTRAINT fk_alert_server FOREIGN KEY (server_id)
      REFERENCES servers(id) ON UPDATE CASCADE ON DELETE CASCADE,
    INDEX idx_alert_server_time (server_id, created_at),
    INDEX idx_alert_resolved (is_resolved)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS login_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    login_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    logout_time DATETIME NULL,
    ip_address VARCHAR(45),
    CONSTRAINT fk_login_user FOREIGN KEY (user_id)
      REFERENCES users(id) ON UPDATE CASCADE ON DELETE SET NULL,
    INDEX idx_login_user_time (user_id, login_time)
) ENGINE=InnoDB;

-- Contoh data server. Ganti IP/hostname sesuai server sebenarnya.
INSERT INTO servers (hostname, ip_address, os_name, location, description, device_status)
VALUES ('SERVER-01', '192.168.1.10', 'Windows Server', 'Server Room',
        'Contoh server; sesuaikan dengan server sebenarnya', 'DOWN')
ON DUPLICATE KEY UPDATE hostname = VALUES(hostname);

SHOW TABLES;

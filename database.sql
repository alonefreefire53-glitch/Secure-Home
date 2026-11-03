CREATE DATABASE IF NOT EXISTS face_recognition;
USE face_recognition;

CREATE TABLE IF NOT EXISTS authorized_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(50),
    email VARCHAR(100),
    photo_path VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS unknown_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    image_path VARCHAR(255),
    status VARCHAR(20) DEFAULT 'New',
    capture_time DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS security_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    person_name VARCHAR(100),
    event_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(50),
    details TEXT
);

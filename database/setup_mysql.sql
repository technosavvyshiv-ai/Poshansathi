-- =============================================================================
-- PoshanSathi — MySQL bootstrap helper (Phase 1)
-- =============================================================================
-- Creates the database and the application user expected by the default
-- DATABASE_URL in .env / .env.example:
--
--     mysql+pymysql://poshansathi:poshansathi@localhost:3306/poshansathi
--
-- Run once as a MySQL administrator (e.g. root):
--
--     sudo mysql < database/setup_mysql.sql
--
-- Then create the tables and demo data as the application user:
--
--     flask --app app.py init-db
--     flask --app app.py seed-db
--
-- This file only creates the database and user.  Table DDL lives in
-- schema.sql and is also created from the SQLAlchemy models.
-- =============================================================================

CREATE DATABASE IF NOT EXISTS poshansathi
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'poshansathi'@'localhost' IDENTIFIED BY 'poshansathi';
GRANT ALL PRIVILEGES ON poshansathi.* TO 'poshansathi'@'localhost';

-- Optional: allow TCP connections from the local host as well.
CREATE USER IF NOT EXISTS 'poshansathi'@'127.0.0.1' IDENTIFIED BY 'poshansathi';
GRANT ALL PRIVILEGES ON poshansathi.* TO 'poshansathi'@'127.0.0.1';

FLUSH PRIVILEGES;

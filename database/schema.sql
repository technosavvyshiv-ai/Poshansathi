-- =============================================================================
-- PoshanSathi — MySQL schema (Phase 1)
-- =============================================================================
-- Smart Nutrition & Welfare Tracking System for Anganwadi Centres.
--
-- This file is the canonical raw-SQL schema.  It mirrors the SQLAlchemy models
-- in app/models/ so the database can be created either with:
--
--     mysql -u <user> -p < database/schema.sql
--
-- or with the Flask CLI (preferred, since it stays in sync with the models):
--
--     flask --app app.py init-db
--
-- Engine: InnoDB (required for foreign keys and transactions).
-- Charset: utf8mb4 (full Unicode, including Indic scripts).
-- Demo data only — never store real beneficiary information.
-- =============================================================================

CREATE DATABASE IF NOT EXISTS poshansathi
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE poshansathi;

-- Drop in dependency order (safe even for repeat runs).
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS audit_logs;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS alerts;
DROP TABLE IF EXISTS interventions;
DROP TABLE IF EXISTS home_visits;
DROP TABLE IF EXISTS beneficiary_schemes;
DROP TABLE IF EXISTS welfare_schemes;
DROP TABLE IF EXISTS attendance;
DROP TABLE IF EXISTS nutrition_distributions;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS nutrition_items;
DROP TABLE IF EXISTS maternal_health_records;
DROP TABLE IF EXISTS vaccinations;
DROP TABLE IF EXISTS growth_records;
DROP TABLE IF EXISTS children;
DROP TABLE IF EXISTS mothers;
DROP TABLE IF EXISTS beneficiaries;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS anganwadi_centres;
SET FOREIGN_KEY_CHECKS = 1;

-- -----------------------------------------------------------------------------
-- anganwadi_centres
-- -----------------------------------------------------------------------------
CREATE TABLE anganwadi_centres (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    code        VARCHAR(50)  NOT NULL,
    address     VARCHAR(255),
    village     VARCHAR(120),
    district    VARCHAR(120),
    state       VARCHAR(120),
    pincode     VARCHAR(10),
    phone       VARCHAR(20),
    is_active   TINYINT(1)   NOT NULL DEFAULT 1,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                 ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_centres_name UNIQUE (name),
    CONSTRAINT uq_centres_code UNIQUE (code),
    INDEX ix_centres_district (district),
    INDEX ix_centres_state (state)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- users
-- -----------------------------------------------------------------------------
CREATE TABLE users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    centre_id     INT,
    full_name     VARCHAR(150) NOT NULL,
    username      VARCHAR(80)  NOT NULL,
    email         VARCHAR(150),
    password_hash VARCHAR(255) NOT NULL,
    role          ENUM('ADMIN', 'AWW', 'SUPERVISOR', 'OFFICER') NOT NULL,
    phone         VARCHAR(20),
    is_active     TINYINT(1)   NOT NULL DEFAULT 1,
    last_login_at DATETIME,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                               ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT fk_users_centre FOREIGN KEY (centre_id)
        REFERENCES anganwadi_centres (id) ON DELETE SET NULL,
    INDEX ix_users_centre_id (centre_id),
    INDEX ix_users_role (role)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- beneficiaries (common record for children and mothers)
-- -----------------------------------------------------------------------------
CREATE TABLE beneficiaries (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    centre_id         INT NOT NULL,
    beneficiary_type  ENUM('CHILD', 'PREGNANT_WOMAN', 'LACTATING_MOTHER') NOT NULL,
    full_name         VARCHAR(150) NOT NULL,
    date_of_birth     DATE,
    gender            ENUM('MALE', 'FEMALE', 'OTHER'),
    guardian_name     VARCHAR(150),
    contact           VARCHAR(20),
    address           VARCHAR(255),
    status            ENUM('ACTIVE', 'INACTIVE') NOT NULL DEFAULT 'ACTIVE',
    registration_date DATE NOT NULL DEFAULT (CURRENT_DATE),
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_beneficiaries_centre FOREIGN KEY (centre_id)
        REFERENCES anganwadi_centres (id) ON DELETE RESTRICT,
    INDEX ix_beneficiaries_centre_id (centre_id),
    INDEX ix_beneficiaries_type (beneficiary_type),
    INDEX ix_beneficiaries_name (full_name),
    INDEX ix_beneficiaries_status (status)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- mothers (pregnant / lactating profile)
-- -----------------------------------------------------------------------------
CREATE TABLE mothers (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    beneficiary_id        INT NOT NULL,
    age                   INT,
    husband_name          VARCHAR(150),
    pregnancy_number      INT,
    last_menstrual_period DATE,
    expected_delivery_date DATE,
    delivery_date         DATE,
    blood_group           VARCHAR(5),
    height_cm             DECIMAL(5, 2),
    current_risk_level    ENUM('LOW', 'MODERATE', 'HIGH') NOT NULL DEFAULT 'LOW',
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_mothers_beneficiary UNIQUE (beneficiary_id),
    CONSTRAINT fk_mothers_beneficiary FOREIGN KEY (beneficiary_id)
        REFERENCES beneficiaries (id) ON DELETE CASCADE
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- children
-- -----------------------------------------------------------------------------
CREATE TABLE children (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    beneficiary_id   INT NOT NULL,
    mother_id        INT,
    birth_weight_kg  DECIMAL(5, 2),
    birth_height_cm  DECIMAL(5, 2),
    blood_group      VARCHAR(5),
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                             ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_children_beneficiary UNIQUE (beneficiary_id),
    CONSTRAINT fk_children_beneficiary FOREIGN KEY (beneficiary_id)
        REFERENCES beneficiaries (id) ON DELETE CASCADE,
    CONSTRAINT fk_children_mother FOREIGN KEY (mother_id)
        REFERENCES mothers (id) ON DELETE SET NULL,
    INDEX ix_children_mother_id (mother_id)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- growth_records
-- -----------------------------------------------------------------------------
CREATE TABLE growth_records (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    child_id           INT NOT NULL,
    recorded_by_id     INT,
    measurement_date   DATE NOT NULL,
    weight_kg          DECIMAL(5, 2) NOT NULL,
    height_cm          DECIMAL(5, 2),
    muac_cm            DECIMAL(5, 2),
    nutritional_status ENUM('NORMAL', 'UNDERWEIGHT', 'SEVERE_UNDERWEIGHT',
                            'OVERWEIGHT'),
    notes              TEXT,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_growth_child_date UNIQUE (child_id, measurement_date),
    CONSTRAINT fk_growth_child FOREIGN KEY (child_id)
        REFERENCES children (id) ON DELETE CASCADE,
    CONSTRAINT fk_growth_user FOREIGN KEY (recorded_by_id)
        REFERENCES users (id) ON DELETE SET NULL,
    INDEX ix_growth_records_child_id (child_id),
    INDEX ix_growth_records_measurement_date (measurement_date)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- vaccinations
-- -----------------------------------------------------------------------------
CREATE TABLE vaccinations (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    child_id           INT NOT NULL,
    vaccine_name       VARCHAR(120) NOT NULL,
    dose_number        INT NOT NULL DEFAULT 1,
    scheduled_date     DATE,
    administered_date  DATE,
    status             ENUM('UPCOMING', 'DUE', 'COMPLETED', 'MISSED')
                           NOT NULL DEFAULT 'UPCOMING',
    administered_by_id INT,
    notes              TEXT,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_vaccination_child_vaccine_dose
        UNIQUE (child_id, vaccine_name, dose_number),
    CONSTRAINT fk_vaccinations_child FOREIGN KEY (child_id)
        REFERENCES children (id) ON DELETE CASCADE,
    CONSTRAINT fk_vaccinations_user FOREIGN KEY (administered_by_id)
        REFERENCES users (id) ON DELETE SET NULL,
    INDEX ix_vaccinations_child_id (child_id),
    INDEX ix_vaccinations_status (status),
    INDEX ix_vaccinations_scheduled_date (scheduled_date)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- maternal_health_records
-- -----------------------------------------------------------------------------
CREATE TABLE maternal_health_records (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    mother_id           INT NOT NULL,
    recorded_by_id      INT,
    visit_date          DATE NOT NULL,
    pregnancy_month     INT,
    weight_kg           DECIMAL(5, 2),
    haemoglobin         DECIMAL(4, 1),
    systolic_bp         INT,
    diastolic_bp        INT,
    risk_category       ENUM('LOW', 'MODERATE', 'HIGH') NOT NULL DEFAULT 'LOW',
    next_follow_up_date DATE,
    notes               TEXT,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                 ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_maternal_mother_visit UNIQUE (mother_id, visit_date),
    CONSTRAINT fk_maternal_mother FOREIGN KEY (mother_id)
        REFERENCES mothers (id) ON DELETE CASCADE,
    CONSTRAINT fk_maternal_user FOREIGN KEY (recorded_by_id)
        REFERENCES users (id) ON DELETE SET NULL,
    INDEX ix_maternal_health_records_mother_id (mother_id),
    INDEX ix_maternal_health_records_visit_date (visit_date)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- nutrition_items
-- -----------------------------------------------------------------------------
CREATE TABLE nutrition_items (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    category    VARCHAR(80),
    unit        VARCHAR(30) NOT NULL DEFAULT 'kg',
    description TEXT,
    is_active   TINYINT(1) NOT NULL DEFAULT 1,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                         ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_nutrition_items_name UNIQUE (name)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- inventory (stock position per centre + item)
-- -----------------------------------------------------------------------------
CREATE TABLE inventory (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    centre_id             INT NOT NULL,
    item_id               INT NOT NULL,
    opening_stock         DECIMAL(10, 2) NOT NULL DEFAULT 0,
    received_quantity     DECIMAL(10, 2) NOT NULL DEFAULT 0,
    distributed_quantity  DECIMAL(10, 2) NOT NULL DEFAULT 0,
    minimum_stock         DECIMAL(10, 2) NOT NULL DEFAULT 0,
    unit                  VARCHAR(30) NOT NULL DEFAULT 'kg',
    expiry_date           DATE,
    received_date         DATE,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                   ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_inventory_centre_item UNIQUE (centre_id, item_id),
    CONSTRAINT fk_inventory_centre FOREIGN KEY (centre_id)
        REFERENCES anganwadi_centres (id) ON DELETE CASCADE,
    CONSTRAINT fk_inventory_item FOREIGN KEY (item_id)
        REFERENCES nutrition_items (id) ON DELETE RESTRICT,
    INDEX ix_inventory_centre_id (centre_id),
    INDEX ix_inventory_item_id (item_id)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- nutrition_distributions
-- -----------------------------------------------------------------------------
CREATE TABLE nutrition_distributions (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    beneficiary_id    INT NOT NULL,
    item_id           INT NOT NULL,
    centre_id         INT NOT NULL,
    worker_id         INT,
    quantity          DECIMAL(10, 2) NOT NULL,
    distribution_date DATE NOT NULL,
    notes             TEXT,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                               ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_nutrition_dist_beneficiary FOREIGN KEY (beneficiary_id)
        REFERENCES beneficiaries (id) ON DELETE CASCADE,
    CONSTRAINT fk_nutrition_dist_item FOREIGN KEY (item_id)
        REFERENCES nutrition_items (id) ON DELETE RESTRICT,
    CONSTRAINT fk_nutrition_dist_centre FOREIGN KEY (centre_id)
        REFERENCES anganwadi_centres (id) ON DELETE RESTRICT,
    CONSTRAINT fk_nutrition_dist_worker FOREIGN KEY (worker_id)
        REFERENCES users (id) ON DELETE SET NULL,
    INDEX ix_nutrition_distributions_beneficiary_id (beneficiary_id),
    INDEX ix_nutrition_distributions_item_id (item_id),
    INDEX ix_nutrition_distributions_centre_id (centre_id),
    INDEX ix_nutrition_distributions_worker_id (worker_id),
    INDEX ix_nutrition_distributions_distribution_date (distribution_date)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- attendance
-- -----------------------------------------------------------------------------
CREATE TABLE attendance (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    child_id        INT NOT NULL,
    centre_id       INT NOT NULL,
    attendance_date DATE NOT NULL,
    status          ENUM('PRESENT', 'ABSENT') NOT NULL DEFAULT 'PRESENT',
    note            VARCHAR(255),
    recorded_by_id  INT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                             ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_attendance_child_date UNIQUE (child_id, attendance_date),
    CONSTRAINT fk_attendance_child FOREIGN KEY (child_id)
        REFERENCES children (id) ON DELETE CASCADE,
    CONSTRAINT fk_attendance_centre FOREIGN KEY (centre_id)
        REFERENCES anganwadi_centres (id) ON DELETE RESTRICT,
    CONSTRAINT fk_attendance_user FOREIGN KEY (recorded_by_id)
        REFERENCES users (id) ON DELETE SET NULL,
    INDEX ix_attendance_child_id (child_id),
    INDEX ix_attendance_centre_id (centre_id),
    INDEX ix_attendance_attendance_date (attendance_date)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- welfare_schemes
-- -----------------------------------------------------------------------------
CREATE TABLE welfare_schemes (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    name               VARCHAR(200) NOT NULL,
    category           VARCHAR(80),
    description        TEXT,
    target_group       VARCHAR(150),
    benefits           TEXT,
    eligibility        TEXT,
    required_documents TEXT,
    application_info   TEXT,
    is_active          TINYINT(1) NOT NULL DEFAULT 1,
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_welfare_schemes_name UNIQUE (name)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- beneficiary_schemes
-- -----------------------------------------------------------------------------
CREATE TABLE beneficiary_schemes (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    beneficiary_id INT NOT NULL,
    scheme_id      INT NOT NULL,
    status         ENUM('ELIGIBLE', 'APPLIED', 'ENROLLED', 'REJECTED')
                       NOT NULL DEFAULT 'ELIGIBLE',
    applied_date   DATE,
    notes          TEXT,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_beneficiary_scheme UNIQUE (beneficiary_id, scheme_id),
    CONSTRAINT fk_beneficiary_schemes_beneficiary FOREIGN KEY (beneficiary_id)
        REFERENCES beneficiaries (id) ON DELETE CASCADE,
    CONSTRAINT fk_beneficiary_schemes_scheme FOREIGN KEY (scheme_id)
        REFERENCES welfare_schemes (id) ON DELETE CASCADE,
    INDEX ix_beneficiary_schemes_beneficiary_id (beneficiary_id),
    INDEX ix_beneficiary_schemes_scheme_id (scheme_id)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- home_visits
-- -----------------------------------------------------------------------------
CREATE TABLE home_visits (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    beneficiary_id      INT NOT NULL,
    centre_id           INT NOT NULL,
    visit_type          ENUM('ROUTINE', 'GROWTH', 'VACCINATION', 'MATERNAL',
                             'NUTRITION', 'FOLLOW_UP') NOT NULL DEFAULT 'ROUTINE',
    assigned_worker_id  INT,
    created_by_id       INT,
    scheduled_date      DATE NOT NULL,
    completed_date      DATE,
    status              ENUM('SCHEDULED', 'COMPLETED', 'CANCELLED', 'MISSED')
                            NOT NULL DEFAULT 'SCHEDULED',
    visit_notes         TEXT,
    follow_up_required  TINYINT(1) NOT NULL DEFAULT 0,
    follow_up_date      DATE,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                 ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_home_visits_beneficiary FOREIGN KEY (beneficiary_id)
        REFERENCES beneficiaries (id) ON DELETE CASCADE,
    CONSTRAINT fk_home_visits_centre FOREIGN KEY (centre_id)
        REFERENCES anganwadi_centres (id) ON DELETE RESTRICT,
    CONSTRAINT fk_home_visits_worker FOREIGN KEY (assigned_worker_id)
        REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_home_visits_creator FOREIGN KEY (created_by_id)
        REFERENCES users (id) ON DELETE SET NULL,
    INDEX ix_home_visits_beneficiary_id (beneficiary_id),
    INDEX ix_home_visits_centre_id (centre_id),
    INDEX ix_home_visits_assigned_worker_id (assigned_worker_id),
    INDEX ix_home_visits_scheduled_date (scheduled_date),
    INDEX ix_home_visits_status (status)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- interventions
-- -----------------------------------------------------------------------------
CREATE TABLE interventions (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    home_visit_id     INT,
    beneficiary_id    INT NOT NULL,
    recorded_by_id    INT,
    intervention_type VARCHAR(100) NOT NULL,
    description       TEXT,
    outcome           TEXT,
    intervention_date DATE NOT NULL,
    follow_up_date    DATE,
    created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                               ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_interventions_visit FOREIGN KEY (home_visit_id)
        REFERENCES home_visits (id) ON DELETE CASCADE,
    CONSTRAINT fk_interventions_beneficiary FOREIGN KEY (beneficiary_id)
        REFERENCES beneficiaries (id) ON DELETE CASCADE,
    CONSTRAINT fk_interventions_user FOREIGN KEY (recorded_by_id)
        REFERENCES users (id) ON DELETE SET NULL,
    INDEX ix_interventions_home_visit_id (home_visit_id),
    INDEX ix_interventions_beneficiary_id (beneficiary_id),
    INDEX ix_interventions_intervention_date (intervention_date)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- alerts
-- -----------------------------------------------------------------------------
CREATE TABLE alerts (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    beneficiary_id   INT,
    child_id         INT,
    alert_type       ENUM('GROWTH_FOLLOW_UP', 'VACCINATION_FOLLOW_UP',
                          'MATERNAL_FOLLOW_UP', 'LOW_NUTRITION_STOCK',
                          'ATTENDANCE', 'HOME_VISIT_PENDING', 'GENERAL')
                         NOT NULL,
    severity         ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
                         NOT NULL DEFAULT 'MEDIUM',
    message          TEXT NOT NULL,
    status           ENUM('OPEN', 'IN_PROGRESS', 'RESOLVED', 'DISMISSED')
                         NOT NULL DEFAULT 'OPEN',
    assigned_to_id   INT,
    created_by_id    INT,
    resolved_at      DATETIME,
    resolution_notes TEXT,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_alerts_beneficiary FOREIGN KEY (beneficiary_id)
        REFERENCES beneficiaries (id) ON DELETE CASCADE,
    CONSTRAINT fk_alerts_child FOREIGN KEY (child_id)
        REFERENCES children (id) ON DELETE CASCADE,
    CONSTRAINT fk_alerts_assignee FOREIGN KEY (assigned_to_id)
        REFERENCES users (id) ON DELETE SET NULL,
    CONSTRAINT fk_alerts_creator FOREIGN KEY (created_by_id)
        REFERENCES users (id) ON DELETE SET NULL,
    INDEX ix_alerts_beneficiary_id (beneficiary_id),
    INDEX ix_alerts_child_id (child_id),
    INDEX ix_alerts_alert_type (alert_type),
    INDEX ix_alerts_severity (severity),
    INDEX ix_alerts_status (status),
    INDEX ix_alerts_assigned_to_id (assigned_to_id)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- notifications
-- -----------------------------------------------------------------------------
CREATE TABLE notifications (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    user_id      INT NOT NULL,
    title        VARCHAR(200) NOT NULL,
    message      TEXT,
    category     VARCHAR(80),
    related_type VARCHAR(50),
    related_id   INT,
    is_read      TINYINT(1) NOT NULL DEFAULT 0,
    read_at      DATETIME,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                          ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_notifications_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE,
    INDEX ix_notifications_user_id (user_id),
    INDEX ix_notifications_category (category),
    INDEX ix_notifications_is_read (is_read)
) ENGINE = InnoDB;

-- -----------------------------------------------------------------------------
-- audit_logs
-- -----------------------------------------------------------------------------
CREATE TABLE audit_logs (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT,
    action      VARCHAR(100) NOT NULL,
    entity_type VARCHAR(80),
    entity_id   INT,
    details     TEXT,
    ip_address  VARCHAR(45),
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                         ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_logs_user FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE SET NULL,
    INDEX ix_audit_logs_user_id (user_id),
    INDEX ix_audit_logs_action (action),
    INDEX ix_audit_logs_entity_type (entity_type)
) ENGINE = InnoDB;

-- =============================================================================
-- End of schema — Phase 1
-- =============================================================================

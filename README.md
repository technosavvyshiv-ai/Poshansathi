# PoshanSathi

### Smart Nutrition & Welfare Tracking System for Anganwadi Centres

PoshanSathi is a Flask-based web application designed to digitally manage Anganwadi beneficiary records and monitor child growth, maternal health, vaccination, nutrition, attendance, alerts, home visits, welfare schemes, dashboards, reports, and notifications.

> **Academic prototype using synthetic/demo data.**

## Features

- Role-based authentication: Admin, AWW, Supervisor, Officer
- Beneficiary and child/mother management
- Child growth tracking
- Vaccination tracking
- Maternal health records
- Nutrition inventory and distribution
- Attendance tracking
- Alerts and home visits
- Welfare scheme management
- Role-based dashboards
- Reports and CSV export
- In-app notifications

## Tech Stack

- Python
- Flask
- SQLAlchemy
- MySQL
- HTML/CSS/JavaScript
- Bootstrap 5
- Chart.js
- pytest

## Project Structure

```text
PoshanSathi/
├── app.py
├── config.py
├── requirements.txt
├── .env.example
├── app/
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── templates/
│   ├── static/
│   └── utils/
├── database/
├── tests/
├── PROJECT_PLAN.md
└── README.md
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/technosavvyshiv-ai/Poshansathi
cd PoshanSathi
```

### 2. Create a virtual environment

**Linux/macOS**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure MySQL

Create the database and application user:

```bash
sudo mysql < database/setup_mysql.sql
```

Copy the environment template:

```bash
cp .env.example .env
```

Update the database settings in `.env` if required.

### 5. Initialize and seed the database

```bash
flask --app app.py init-db
flask --app app.py seed-db
```

The seed command creates synthetic demo data and demo accounts.

### 6. Run the application

```bash
flask --app app.py run
```

Open:

```text
http://127.0.0.1:5000
```

## Demo Login

| Username | Role |
|---|---|
| `admin` | Admin |
| `aww1` | AWW |
| `supervisor1` | Supervisor |
| `officer` | Officer |

**Password:** `password123`

## Testing

Run the complete test suite:

```bash
python -m pytest -q
```

Current project status:

```text
428 passed
```

## Scope

This project is an academic prototype and uses synthetic/demo data.

- No real Aadhaar or sensitive government data
- No government API integration
- No real SMS/WhatsApp integration
- No medical diagnosis
- No production deployment
- AI/OpenRouter integration intentionally not included

## Project Status

**Core application completed and tested.**

---

### PoshanSathi
*Digitally empowering Anganwadi Centres for healthier mothers and children.*

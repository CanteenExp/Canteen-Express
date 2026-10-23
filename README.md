<div align="center">

# 🍔 Canteen Express
### Enterprise Django Web Application & Progressive Web App Suite

<p align="center">
  <img src="https://img.shields.io/badge/Django-5.1.5-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PostgreSQL-Supabase-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Tailwind_CSS-3.4-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white" alt="Tailwind CSS">
  <img src="https://img.shields.io/badge/Leaflet-Maps-199900?style=for-the-badge&logo=leaflet&logoColor=white" alt="Leaflet">
  <img src="https://img.shields.io/badge/PWA-Ready-5A0FC8?style=for-the-badge&logo=pwa&logoColor=white" alt="PWA">
</p>

<p align="center">
  <b>Comprehensive Campus Canteen Ordering, Counter POS, Kitchen Display, Digital Queuing, and Real-Time GPS Delivery Suite.</b>
</p>

</div>

---

## 🌟 Executive Summary

**Canteen Express** is a production-grade, multi-role campus dining and delivery platform built for **Palawan State University (PSU Tiniguiban Heights)**. It streamlines the entire campus food service lifecycle—from student/faculty self-service ordering and barcode-based counter POS transactions to kitchen Kanban order fulfillment and live GPS-tracked campus office deliveries.

---

## 📱 Role-Based Progressive Web App (PWA) Ecosystem

Canteen Express provides custom standalone PWA experiences tailored for each stakeholder:

| Role / Portal | Access URL | Primary Interface | Core Capabilities |
| :--- | :--- | :--- | :--- |
| **Student / Walk-in Kiosk** | `/kiosk/` | Dark Glassmorphic Kiosk | Self-service menu browsing, instant cart checkout, automated queue slip & barcode generation. |
| **Faculty / Staff Portal** | `/accounts/dashboard/` | Glass Dashboard / Dual Mode | Institutional authentication (`@psu.palawan.edu.ph`), office delivery dispatch, loyalty points & rewards. |
| **Canteen Staff Counter POS** | `/canteen/staff/` | Counter POS & Board | Barcode & queue slip scanning (`/canteen/api/process-barcode/`), cash confirmation, menu management. |
| **Kitchen Display Board** | `/kitchen/` | Real-Time Kanban Board | Live 3-column order workflow (`pending ➜ preparing ➜ ready ➜ completed`), stock & points automation. |
| **Delivery Personnel Hub** | `/deliveries/dashboard/` | Delivery Personnel Portal & Map | Order dispatch stream, real-time GPS tracking (`watchPosition`), turn-by-turn routing, live chat. |

---

## ⚙️ Core Architecture & Advanced Features

### 1. 🗺️ Campus Geofence Enforcement (`deliveries`)
- **Center Coordinates:** `9.77778, 118.73333` (PSU Tiniguiban Heights).
- **Enforced Radius:** `0.8` km (`deliveries/utils.py`).
- **Behavior:** Out-of-campus delivery destinations or missing coordinates are strictly blocked at checkout with HTTP `422 Unprocessable Entity`.

### 2. 🕒 Operating Hours Schedule (`core_app`)
- **Schedule:** Enforces Monday to Friday, 8:00 AM – 5:00 PM for student/faculty ordering and delivery personnel dispatch.
- **Exemptions:** Canteen staff and admin portals operate **24/7**.
- **Testing Override:** Set `ENFORCE_OPERATING_HOURS=False` in `.env` to bypass time restrictions during night or weekend testing.

### 3. 🚗 Advanced Road-Following Routing (`deliveries/routing.py`)
- Automatically queries OSRM driving routes and Valhalla pedestrian footpaths (for campus areas vehicles cannot access), with seamless fallback to Haversine distance.
- Integrated dark-mode Leaflet maps with custom CSS tile inversion.

### 4. 📊 Sales Analytics & Financial Reporting
- Interactive **Chart.js** analytics dashboards with filter tabs for **Daily (7 Days)**, **Weekly (4 Weeks)**, and **Monthly (6 Months)** sales performance breakdown.

---

## 🚀 Quick Start Guide

### 1. Clone & Setup Workspace
```bash
git clone https://github.com/CanteenExp/Canteen-Express.git
cd Canteen-Express/backend
```

### 2. Create Virtual Environment
```powershell
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables (`backend/.env`)
Create a `.env` file directly inside `backend/`:
```env
SECRET_KEY="your-django-secure-key"
DEBUG=True

# Database Configuration (Leave DB_HOST empty or set USE_SQLITE=True for local SQLite)
DB_NAME="postgres"
DB_USER="postgres"
DB_PASSWORD="your_password"
DB_HOST="aws-0-ap-southeast-1.pooler.supabase.com"
DB_PORT="6543"
USE_SQLITE=False

# Operational Toggles
ENFORCE_GEOFENCE=True
ENFORCE_OPERATING_HOURS=False
```

### 5. Run Migrations & Start Server
```bash
python manage.py migrate
python manage.py runserver
```
Access the application at `http://127.0.0.1:8000/`.

---

## 🧪 Testing & Management Commands

Run Django tests inside `backend/` using `--keepdb` for lightning-fast test execution:
```bash
# Run entire test suite
python manage.py test --keepdb

# Run specific app tests
python manage.py test deliveries customer_portal canteen_menu accounts
```

### Reset Orders & Activity Logs
To clear test orders, feedback, and delivery records while preserving menu items and user accounts:
```bash
python manage.py reset_orders
```

---

## 📦 Project Directory Structure

```text
Canteen-Express/
│
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── config/              # Django settings & URL routing
│   ├── accounts/            # User authentication, roles & faculty dashboard
│   ├── canteen_menu/        # Menu management, Counter POS & barcode API
│   ├── customer_portal/     # Kiosk UI, cart & queue slip generation
│   ├── kitchen_display/     # Kitchen Kanban order fulfillment board
│   ├── deliveries/          # GPS live tracking, road routing & live chat
│   ├── queuing/             # Digital queue slip models
│   ├── analytics_reports/   # Sales charts & financial reporting
│   ├── core_app/            # Operating hours & global schedule enforcement
│   └── templates/           # Global HTML templates & partials
│
├── package.json             # Tailwind CSS build configs
└── README.md
```

---

## 🔒 License & Support
Developed for Palawan State University Canteen Services. All rights reserved.

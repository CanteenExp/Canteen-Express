<div align="center">

# Canteen Express
### Enterprise Django Web Application & Progressive Web App Suite

<p align="center">
  <img src="https://img.shields.io/badge/Django-5.1.5-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PostgreSQL-Supabase-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Tailwind_CSS-3.x-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white" alt="Tailwind CSS">
  <img src="https://img.shields.io/badge/PWA-Enabled-5A0FC8?style=for-the-badge&logo=pwa&logoColor=white" alt="PWA">
</p>

<p align="center">
  <b>Comprehensive Canteen Ordering, Counter POS, Kitchen Display, Digital Queuing, and Campus Delivery Suite.</b>
</p>

</div>

---

## Role-Based Progressive Web App (PWA) Support

Canteen Express is fully optimized as a Progressive Web App across all user tiers, enabling offline caching, standalone app installation, and native-like performance:

| Role | Start URL | Theme | Key Features |
| :--- | :--- | :--- | :--- |
| **Student / Walk-in Kiosk** | `/kiosk/` | Dark (`#121212`, `#f97316`) | Self-service ordering, guest/student ordering, barcode queue slip generation, smart category-based customization. |
| **Faculty / Staff Portal** | `/accounts/dashboard/` | Dark (`#121212`, `#f97316`) | Authenticated faculty/staff ordering (`@psu.palawan.edu.ph`), loyalty points accumulation, order tracking. |
| **Canteen Staff / Admin** | `/canteen/staff/` | Light / Brand (`#f97316`) | Counter POS screen, barcode & queue slip scanning API (`/canteen/api/process-barcode/`), menu management, sales reports. |
| **Delivery Rider Hub** | `/deliveries/dashboard/` | Dark Brand (`#08080b`, `#FF6117`) | Real-time dispatch, accept/update delivery status, live GPS tracking (`watchPosition`), real-time customer chat. |

---

## Core System Modules & Features

- **Kitchen Display Kanban Board (`kitchen_display`)**
  - Real-time 3-column workflow: **Kiosk Accepted** (Walk-in Kiosk), **Delivery** (Campus Delivery), and **Orders Ready** (Ready for pickup/dispatch).
  - AJAX status updates with robust null-safety for walk-in kiosk orders.
- **Campus Geofence Enforcement (`deliveries`)**
  - Official campus center: `9.77778, 118.73333` (PSU Tiniguiban Heights).
  - Strict radius check: `0.8` km (`deliveries/utils.py`). Out-of-campus delivery orders or missing destination coordinates are automatically rejected at checkout with HTTP `422 Unprocessable Entity`.
- **Real-Time Operating Hours Schedule (`core_app`)**
  - Restricts customer ordering, faculty ordering, and delivery dispatches to **Monday to Friday, 8:00 AM to 5:00 PM**.
  - **Canteen Staff and Admin portals operate 24/7** (exempted from time restrictions).
  - Configurable via `ENFORCE_OPERATING_HOURS=True` (or `False` to bypass during night/weekend testing).
- **Advanced Road-Following Routing (`deliveries/routing.py`)**
  - OSRM driving and Valhalla pedestrian routing with fallback to Haversine straight-line distance, fully cached.
- **Sales Reports & Analytics (`analytics_reports`, `admin_dashboard`)**
  - Interactive Chart.js bar graphs with filter tabs for **Daily (7 Days)**, **Weekly (4 Weeks)**, and **Monthly (6 Months)** sales performance and financial breakdown tables.
- **Convenience Fee & Loyalty Points**
  - Automatically calculates convenience fees (**₱15 per ₱300 purchase block**) for campus deliveries and loyalty points for faculty and staff accounts.
- **Dark Map Integration**
  - Leaflet maps use free OpenStreetMap tiles with CSS invert filters on `.leaflet-tile-pane` for seamless dark-mode map rendering without paid API keys.

---

## Prerequisites

Ensure you have the following installed on your system:
- **Python 3.10+** (Recommended: **Python 3.12**)
- **Git**

---

## Quick Start Guide

### 1. Clone the Repository & Navigate to Backend
```bash
git clone https://github.com/CanteenExp/Canteen-Express.git
cd "Canteen-Express/backend"
```

### 2. Create and Activate Virtual Environment
#### Windows - PowerShell
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
#### Mac / Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables (`.env`)
Create a `.env` file directly inside the `backend/` folder alongside `manage.py`:
```env
SECRET_KEY="django-insecure-your-secret-key-here"
DEBUG=True

# Supabase PostgreSQL Database Credentials (leave DB_HOST empty or set USE_SQLITE=True to fall back to local SQLite)
DB_NAME="postgres"
DB_USER="postgres.hchqdkuijbpihraagetz"
DB_PASSWORD="<YOUR_DB_PASSWORD>"
DB_HOST="aws-0-ap-southeast-1.pooler.supabase.com"
DB_PORT="6543"

# Optional Feature Toggles
ENFORCE_GEOFENCE=True
ENFORCE_OPERATING_HOURS=False  # Set to True to enforce Mon-Fri 8am-5pm schedule for customers/riders
```

### 5. Run Database Migrations
```bash
python manage.py migrate
```

### 6. Create Superuser (Optional)
```bash
python manage.py createsuperuser
```

### 7. Run Development Server
```bash
python manage.py runserver
```
Access the application in your browser at: `http://127.0.0.1:8000/`

---

## Testing & Management Commands

Always run Django tests inside the `backend/` directory with `--keepdb` to avoid slow/flaky Supabase PostgreSQL test DB recreation prompts:

```bash
# Run all tests (preserving test database)
python manage.py test --keepdb

# Run specific app tests
python manage.py test deliveries customer_portal
```

### Reset Orders & Feedback Utility
To reset all orders, order items, feedback/ratings, and delivery records while preserving accounts and menu management intact:
```bash
python manage.py reset_orders
```

---

## Key API Endpoints

1. **Barcode & Queue Slip Processing API (`canteen_menu`)**
   - **Endpoint:** `/canteen/api/process-barcode/`
   - **Method:** `POST`
   - **Payload:** `{"queue_slip": "#CE-1001"}`
   - **Purpose:** Converts queue slip status from `unpaid` to `pending` (marks order as paid at the counter POS).
2. **Kitchen Order Status Update API (`kitchen_display`)**
   - **Endpoint:** `/kitchen/order/<int:order_id>/update-status/`
   - **Method:** `POST`
   - **Payload:** `{"status": "ready"}` or `{"status": "completed"}`
   - **Purpose:** Updates order workflow status on the kitchen Kanban board in real time.
3. **Customer Kiosk & Ordering APIs (`customer_portal`)**
   - **Endpoint:** `/kiosk/`
   - **Method:** `GET`, `POST`
   - **Purpose:** Manages kiosk menu items, cart sessions, and order checkout with geofence and operating hours validation.
4. **Delivery & Live Chat APIs (`deliveries`)**
   - **Endpoints:** `/deliveries/...`
   - **Method:** `GET`, `POST`
   - **Purpose:** Rider delivery assignment, GPS coordinate updates (`watchPosition`), and real-time messaging (`DeliveryMessage`).

---

## Project Directory Structure

```text
CANTEEN-EXPRESS/
│
├── backend/
│   ├── manage.py
│   ├── .env
│   ├── requirements.txt
│   ├── static/
│   │   ├── sw.js
│   │   ├── manifest-kiosk.json
│   │   ├── manifest-faculty.json
│   │   ├── manifest-staff.json
│   │   └── manifest-rider.json
│   ├── templates/
│   ├── config/
│   ├── accounts/
│   ├── canteen_menu/
│   ├── customer_portal/
│   ├── kitchen_display/
│   ├── deliveries/
│   ├── queuing/
│   ├── order_management/
│   ├── user_notifications/
│   ├── analytics_reports/
│   ├── admin_dashboard/
│   └── core_app/
│
└── README.md
```

---

## Troubleshooting & Notes

- **Database Fallback:** If the `.env` file is missing or Supabase PostgreSQL is unreachable, the system automatically falls back to local SQLite (`backend/db.sqlite3`) or when `USE_SQLITE=True` is configured in `.env`.
- **Offline / Local Dev:** Set `USE_SQLITE=True` in `backend/.env` to bypass remote PostgreSQL timeout issues during local development.
- **Night Testing Mode:** Set `ENFORCE_OPERATING_HOURS=False` in `backend/.env` to test ordering and delivery features outside of the 8:00 AM – 5:00 PM operating window.

---

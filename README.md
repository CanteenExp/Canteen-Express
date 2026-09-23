<div align="center">

# Canteen Express
### *Enterprise-Grade Django Web Application & Progressive Web App (PWA) Suite*

[![Django](https://img.shields.io/badge/Django-5.1.5-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/Supabase-PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://supabase.com/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.x-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![PWA Ready](https://img.shields.io/badge/PWA-Ready-FF6117?style=for-the-badge&logo=pwa&logoColor=white)](https://web.dev/progressive-web-apps/)

*A comprehensive campus dining, counter POS, kitchen display, digital queuing, and real-time geofenced delivery platform built for Palawan State University (PalSU) Main Canteen.*

</div>

---

## Progressive Web App (PWA) Tiers & Roles

Canteen Express is fully optimized as a Progressive Web App across all user tiers, enabling offline caching, standalone home-screen installation, and native-like performance:

| Role / Tier | Manifest File | Start URL | Core Features |
| :--- | :--- | :--- | :--- |
| **Student / Walk-In Kiosk** | `manifest-kiosk.json` | `/kiosk/` | Self-service kiosk ordering, guest/student ordering, QR/barcode queue slip generation, smart category-based customization. |
| **Faculty / Staff Portal** | `manifest-faculty.json` | `/accounts/dashboard/` | Authenticated institutional ordering (`@psu.palawan.edu.ph`), loyalty points accumulation (1pt per ₱100 spent), and live delivery tracking. |
| **Canteen Staff / Admin** | `manifest-staff.json` | `/canteen/staff/` | Counter POS screen (`counter_pos.html`), barcode scanning API (`/canteen/api/process-barcode/`), menu management, and sales analytics. |
| **Delivery Rider Hub** | `manifest-rider.json` | `/deliveries/dashboard/` | Real-time delivery dispatch, accept/update status, live GPS tracking (`watchPosition`), and real-time customer chat (`DeliveryMessage`). |

---

## Core Modules & Advanced Features

- **Kitchen Display Kanban Board (`kitchen_display`)**
  - Real-time 3-column workflow: **Kiosk Accepted**, **Delivery**, and **Orders Ready**.
  - AJAX status updates (`/kitchen/order/<id>/update-status/`) with robust null-safety for walk-in kiosk orders.
- **Campus Geofence Enforcement (`deliveries`)**
  - Official campus center: `9.77778, 118.73333` (PSU Tiniguiban Heights).
  - Strict radius check: `0.8` km (`deliveries/utils.py`). Out-of-campus delivery orders or missing destination coordinates are automatically rejected at checkout with HTTP `422 Unprocessable Entity`.
- **Smart Rider Timeout & Walk-In Queue Slip Generator**
  - If no rider accepts a campus delivery order within 2 minutes (`SEARCHING` status), a frosted dark glass timeout modal pops up automatically with three options: **Wait (+2 Mins)**, **Convert to Pick-up** (instantly transitions the order to counter pick-up and generates an official Digital Queue Slip with barcode via `JsBarcode`), and **Cancel Order**.
- **Real-Time PWA Auto-Refresh & Chat Polling**
  - Server-Sent Events (SSE) with auto-reconnection and `visibilitychange` resume listeners ensure live updates without requiring manual app reloads. In-chat interfaces feature automatic 2.5-second polling for instantaneous messaging.
- **Sales Reports & Analytics (`analytics_reports`, `admin_dashboard`)**
  - Interactive Chart.js bar graphs with filter tabs for **Daily (7 Days)**, **Weekly (4 Weeks)**, and **Monthly (6 Months)** sales performance and financial breakdown tables.
- **Convenience Fee & Loyalty Points**
  - Automatically calculates convenience fees (**₱15 per ₱300 purchase block**) for campus deliveries and loyalty points for faculty and staff accounts.
- **Dark Map Integration**
  - Leaflet maps use free OpenStreetMap tiles with CSS invert filters on `.leaflet-tile-pane` for seamless dark-mode map rendering without paid API keys.

---

## Prerequisites

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
USE_SQLITE=FALSE

# Supabase PostgreSQL Database Credentials (Transaction Mode Port 6543)
DB_NAME="postgres"
DB_USER="postgres.hchqdkuijbpihraagetz"
DB_PASSWORD="<YOUR_DB_PASSWORD>"
DB_HOST="aws-0-ap-southeast-1.pooler.supabase.com"
DB_PORT="6543"

# Gmail SMTP Real-time Email Settings (SSL Port 465)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=465
EMAIL_USE_SSL=True
EMAIL_HOST_USER=canteenexpress26@gmail.com
EMAIL_HOST_PASSWORD=<YOUR_GMAIL_APP_PASSWORD>
DEFAULT_FROM_EMAIL=Canteen Express <canteenexpress26@gmail.com>

ENFORCE_GEOFENCE=True
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

## Testing & Common Commands

Always run Django tests inside the `backend/` directory with `--keepdb` to avoid slow/flaky Supabase PostgreSQL test DB recreation prompts:

```bash
# Run all tests (preserving test database)
python manage.py test --keepdb

# Run specific app tests
python manage.py test deliveries customer_portal accounts
```

### Reset / Clear All Orders (Testing Utility)
To clear all orders and order items in the database for testing:
1. Open Django interactive shell:
   ```bash
   python manage.py shell
   ```
2. Run:
   ```python
   from customer_portal.models import Order, OrderItem
   OrderItem.objects.all().delete()
   Order.objects.all().delete()
   exit()
   ```

---

## Key API Endpoints

| API Module | Endpoint | Method | Payload / Parameters | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Canteen Menu** | `/canteen/api/process-barcode/` | `POST` | `{"queue_slip": "#CE-1001"}` | Converts queue slip status from `unpaid` to `pending` (marks order as paid at the counter POS). |
| **Kitchen Display** | `/kitchen/order/<id>/update-status/` | `POST` | `{"status": "ready"}` | Updates order workflow status on the kitchen Kanban board in real time. |
| **Customer Kiosk** | `/kiosk/` | `GET`, `POST` | Cart JSON / Form Data | Manages kiosk menu items, cart sessions, and order checkout with geofence validation. |
| **Deliveries** | `/deliveries/api/location/<id>/` | `GET` | — | Returns rider GPS coordinates, speed, distance, and ETA for live Leaflet tracking. |
| **Deliveries** | `/deliveries/api/convert-to-pickup/<id>/` | `POST` | — | Converts delivery order to counter pick-up and generates a digital queue slip. |

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

- **Supabase Connection Limit (`EMAXCONNSESSION`):** Always use Supabase **Transaction Mode** (`DB_PORT=6543`) to prevent connection pool exhaustion during multithreaded development.
- **Windows CP1252 Encoding Error:** Avoid complex Unicode emojis in backend print statements and management commands; use FontAwesome icons in HTML templates instead.
- **Database Fallback:** If the `.env` file is missing or Supabase PostgreSQL is unreachable, the system automatically falls back to local SQLite (`backend/db.sqlite3`).

<div align="center">

**Happy coding, team!**

</div>

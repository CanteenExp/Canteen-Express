# Canteen Express - Django Web Application & PWA Suite

Welcome to the **Canteen Express** project! A comprehensive, enterprise-grade Django web application and Progressive Web App (PWA) suite designed for automated Canteen Ordering, Counter POS, Kitchen Display, Digital Queuing, and Campus Delivery.

---

## 📱 Progressive Web App (PWA) Support by Role

Canteen Express is fully optimized as a Progressive Web App across all user tiers, enabling offline caching, standalone app installation, and native-like performance:

1. **Customer Student / Walk-in Kiosk (`manifest-kiosk.json`)**
   - **Start URL:** `/kiosk/`
   - **Theme:** Dark theme (`#121212`, accent `#f97316`)
   - **Features:** Self-service kiosk ordering, guest/student ordering, QR/barcode queue slip generation, smart category-based customization (e.g., Steamed Rice add-ons exclusively for Rice Meals).
2. **Customer Faculty / Staff (`manifest-faculty.json`)**
   - **Start URL:** `/accounts/dashboard/`
   - **Theme:** Dark theme (`#121212`, accent `#f97316`)
   - **Features:** Authenticated faculty/staff ordering (`@psu.palawan.edu.ph`), loyalty points accumulation, order history, and delivery tracking.
3. **Canteen Staff / Admin Portal (`manifest-staff.json`)**
   - **Start URL:** `/canteen/staff/`
   - **Theme:** Light/Brand dark (`#f97316` theme)
   - **Features:** Counter POS screen (`counter_pos.html`), barcode & queue slip scanning API (`/canteen/api/process-barcode/`), menu item management, delivery rider creation, and comprehensive sales reports.
4. **Delivery Personnel / Rider Hub (`manifest-rider.json`)**
   - **Start URL:** `/deliveries/dashboard/`
   - **Theme:** Dark brand theme (`#08080b`, accent `#FF6117`)
   - **Features:** Real-time delivery dispatch, accept/update delivery status, live GPS tracking (`navigator.geolocation.watchPosition`), and real-time customer chat (`DeliveryMessage`).

---

## 🚀 Core System Modules & Features

- **Kitchen Display Kanban Board (`kitchen_display`)**
  - Real-time 3-column workflow: **Kiosk Accepted** (Walk-in Kiosk), **Delivery** (Campus Delivery), and **Orders Ready** (Ready for pickup/dispatch).
  - AJAX status updates (`/kitchen/order/<id>/update-status/`) with robust null-safety for walk-in kiosk orders.
- **Campus Geofence Enforcement (`deliveries`)**
  - Official campus center: `9.77778, 118.73333` (PSU Tiniguiban Heights).
  - Strict radius check: `0.8` km (`deliveries/utils.py`). Out-of-campus delivery orders or missing destination coordinates are automatically rejected at checkout with HTTP `422 Unprocessable Entity`.
- **Sales Reports & Analytics (`analytics_reports`, `admin_dashboard`)**
  - Interactive Chart.js bar graphs with filter tabs for **Daily (7 Days)**, **Weekly (4 Weeks)**, and **Monthly (6 Months)** sales performance and financial breakdown tables.
- **Convenience Fee & Loyalty Points**
  - Automatically calculates convenience fees (**₱15 per ₱300 purchase block**) for campus deliveries and loyalty points for faculty and staff accounts.
- **Dark Map Integration**
  - Leaflet maps use free OpenStreetMap tiles with CSS invert filters on `.leaflet-tile-pane` for seamless dark-mode map rendering without paid API keys.

---

## 📋 Prerequisites

Ensure you have the following installed on your system:
- **Python 3.10+** (Recommended: **Python 3.12**)
- **Git**

---

## 🛠️ Quick Start Guide

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

# Supabase PostgreSQL Database Credentials (falls back to local SQLite if absent or unreachable)
DB_NAME="postgres"
DB_USER="postgres.hchqdkuijbpihraagetz"
DB_PASSWORD="<YOUR_DB_PASSWORD>"
DB_HOST="aws-0-ap-southeast-1.pooler.supabase.com"
DB_PORT="6543"
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

## 🧪 Testing & Common Commands

Always run Django tests inside the `backend/` directory with `--keepdb` to avoid slow/flaky Supabase PostgreSQL test DB recreation prompts:

```bash
# Run all tests (preserving test database)
python manage.py test --keepdb

# Run specific app tests
python manage.py test deliveries customer_portal
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

## 🔌 Key API Endpoints

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
   - **Purpose:** Manages kiosk menu items, cart sessions, and order checkout with geofence validation.
4. **Delivery & Live Chat APIs (`deliveries`)**
   - **Endpoints:** `/deliveries/...`
   - **Method:** `GET`, `POST`
   - **Purpose:** Rider delivery assignment, GPS coordinate updates (`watchPosition`), and real-time messaging (`DeliveryMessage`).

---

## 📂 Project Directory Structure

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

## 💡 Troubleshooting & Notes

- **Windows CP1252 Encoding Error:** Avoid complex Unicode emojis in backend print statements and management commands; use FontAwesome icons in HTML templates instead.
- **Database Fallback:** If the `.env` file is missing or Supabase PostgreSQL is unreachable, the system automatically falls back to local SQLite (`backend/db.sqlite3`).

**Happy coding, team!**

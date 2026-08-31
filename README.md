# Canteen Express - Django Web Application & Setup Guide

Welcome to the **Canteen Express** project! A comprehensive Django web application designed for Canteen Ordering, Counter POS, Kitchen Display, Digital Queuing, and Campus Delivery.

---

## Latest System Updates & Features
- **Official Favicon Integration:**
  - The official Canteen Express logo is linked as the browser favicon (`<link rel="icon" ... />`) across all web pages and templates in the system.
- **Dark Theme Login Portals:**
  - The **Canteen Staff Portal** and **Delivery Personnel Portal** login pages feature a dark theme (`bg-brand-dark`), matching the exact brand color palette.
- **Kitchen Display Kanban Board & Dashboards:**
  - 3-column workflow: **Kiosk Accepted** (Walk-in Kiosk), **Delivery** (Campus Delivery), and **Orders Ready** (Orders finished and ready for pickup/dispatch).
  - Robust null-safety handling for walk-in kiosk orders without registered customer accounts.
- **Sales Reports & Analytics with Charts:**
  - Interactive Chart.js bar graphs with filter tabs for **Daily (7 Days)**, **Weekly (4 Weeks)**, and **Monthly (6 Months)** sales reports and financial breakdown tables.
- **Convenience Fee & Loyalty Points:**
  - Automatically calculates convenience fees (**₱15 per ₱300 purchase block**) for campus deliveries and loyalty points for faculty and staff.

---

## Prerequisites

Before starting, ensure you have the following installed on your computer:

- **Python 3.10+**  
  - Recommended: **Python 3.12**
- **Git**
- **VS Code** or any code editor

---

## Quick Start

### 1. Clone the Repository & Navigate to Backend

Open your **Terminal / PowerShell** and run:

```bash
git clone https://github.com/CanteenExp/Canteen-Express.git
cd "Canteen-Express/backend"
```

---

### 2. Create and Activate Virtual Environment

#### Windows - PowerShell
```powershell
python -m venv venv
.\venv\Scripts\Activate
```

#### Windows - Command Prompt (CMD)
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

#### Mac / Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Install Dependencies

Install all required packages using:

```bash
pip install -r requirements.txt
```

---

### 4. Setup Environment Variables

Create a `.env` file inside the `backend/` folder alongside `manage.py`:

```env
SECRET_KEY="django-insecure-your-secret-key-here"
DEBUG=True

# Neon Cloud Database Credentials
DB_NAME="neondb"
DB_USER="neondb_owner"
DB_PASSWORD="<YOUR_DB_PASSWORD>"
DB_HOST="ep-shy-heart-ayghwl06-pooler.c-5.us-east-2.aws.neon.tech"
DB_PORT="5432"
```

---

### 5. Run Database Migrations

Ensure database tables are up to date:

```bash
python manage.py migrate
```

---

### 6. Create Admin Account (Optional)

If you need access to the **Django Admin Dashboard**, create a superuser:

```bash
python manage.py createsuperuser
```

---

### 7. Run Development Server

Start the Django development server:

```bash
python manage.py runserver
```

Open in your browser:

```text
http://127.0.0.1:8000/
```

---

## Common Commands & Order Reset

| Command | Purpose |
|---|---|
| `python manage.py runserver` | Start development server |
| `python manage.py makemigrations` | Create migrations from model changes |
| `python manage.py migrate` | Apply migrations |
| `python manage.py createsuperuser` | Create admin account |
| `python manage.py shell` | Open Django interactive shell |
| `pip install -r requirements.txt` | Install project dependencies |

### Reset / Clear All Orders (Testing Command)
To reset or clear all orders in the database for testing:
1. Open the Django shell:
   ```bash
   python manage.py shell
   ```
2. Run the following Python commands:
   ```python
   from customer_portal.models import Order, OrderItem
   OrderItem.objects.all().delete()
   Order.objects.all().delete()
   exit()
   ```

---

## System APIs & Endpoints

The system includes key API endpoints for real-time POS scanning, kitchen board updates, and delivery tracking:

1. **Barcode & Queue Slip Processing API (`canteen_menu`)**
   - **Endpoint:** `/canteen/api/process-barcode/`
   - **Method:** `POST`
   - **Payload:** `{"queue_slip": "#CE-1001"}` (or scanned barcode string)
   - **Purpose:** Searches the database for the kiosk queue slip, converts its status from `unpaid` to `pending` (marked as paid), and confirms counter payment.

2. **Kitchen Order Status Update API (`kitchen_display`)**
   - **Endpoint:** `/kitchen/order/<int:order_id>/update-status/`
   - **Method:** `POST`
   - **Payload:** `{"status": "ready"}` or `{"status": "completed"}`
   - **Purpose:** Real-time AJAX endpoint to update order status on the kitchen board (Kiosk Accepted/Delivery -> Orders Ready -> Completed).

3. **Customer Kiosk & Ordering APIs (`customer_portal`)**
   - **Endpoint:** `/kiosk/` and associated menu/cart endpoints.
   - **Method:** `GET`, `POST`
   - **Purpose:** Retrieves daily menu items, manages carts, and processes new kiosk or delivery orders generating queue slips and QR/barcodes.

4. **Delivery & Live Chat APIs (`deliveries`)**
   - **Endpoints:** `/deliveries/...`
   - **Method:** `GET`, `POST`
   - **Purpose:** Allows delivery riders to accept delivery requests, update GPS/status, and chat in real time with faculty/staff customers.

---

## Backend Structure

```text
CANTEEN EXPRESS/
│
├── backend/
│   ├── manage.py
│   ├── .env
│   ├── requirements.txt
│   ├── static/
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

## Troubleshooting

### `ModuleNotFoundError`
Ensure your virtual environment is activated and dependencies are installed:
```powershell
.\venv\Scripts\Activate
pip install -r requirements.txt
```

### Database Connection Error
Check your `.env` file to ensure `DB_HOST`, `DB_USER`, and `DB_PASSWORD` are correct. If no `.env` is present, it will fall back to local SQLite (`db.sqlite3`).

---

## Ready to Develop!

```text
http://127.0.0.1:8000/
```

**Happy coding, team!**

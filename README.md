# 🍱 Canteen Express - Django Web Application & Setup Guide

Welcome sa **Canteen Express** project! 🎉 Isang kumpletong Django 5 web application para sa Canteen Ordering, Counter POS, Kitchen Display, Digital Queuing, at Campus Delivery.

---

## 🚀 Latest System Updates & Features
- **Official Favicon Integration:**
  - Ang official Canteen Express logo ay naka-link na bilang browser favicon (`<link rel="icon" ... />`) sa lahat ng web pages at templates sa buong sistema.
- **Dark Theme Login Portals:**
  - Ang **Canteen Staff Portal** at **Delivery Personnel Portal** login pages ay naka-dark theme na ngayon (full-screen `bg-brand-dark`), gamit ang eksaktong brand color palette.
- **Kitchen Display Kanban Board & Dashboards:**
  - 3-column workflow: **Kiosk Accepted** (Walk-in Kiosk), **Delivery** (Campus Delivery), at **Orders Ready** (Orders finished and ready for pickup/dispatch).
  - Robust null-safety handling para sa mga walk-in kiosk orders na walang registered customer account.
- **Sales Reports & Analytics with Charts:**
  - Interactive Chart.js bar graph na may filter tabs para sa **Daily (7 Days)**, **Weekly (4 Weeks)**, at **Monthly (6 Months)** sales reports at financial breakdown tables.
- **Convenience Fee & Loyalty Points:**
  - Awtomatikong kinakalkula ang convenience fee na **₱15 per ₱300 purchase block** para sa mga campus deliveries at loyalty points para sa faculty/staff.

---

## 📋 Prerequisites

Bago magsimula, siguraduhing naka-install ang mga sumusunod sa iyong computer:

- **Python 3.10+**  
  - Recommended: **Python 3.12**
- **Git**
- **VS Code** or any code editor

---

# 🚀 Quick Start

## 1. Clone the Repository & Navigate to Backend

Buksan ang **Terminal / PowerShell** at i-run:

```bash
git clone https://github.com/CanteenExp/Canteen-Express.git
cd "CANTEEN EXPRESS/backend"
```

---

## 2. Create and Activate Virtual Environment

### 🪟 Windows - PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate
```

### 🪟 Windows - Command Prompt (CMD)

```cmd
python -m venv venv
venv\Scripts\activate.bat
```

### 🍎 Mac / 🐧 Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Install Dependencies

I-install ang lahat ng required packages gamit ang:

```bash
pip install -r requirements.txt
```

---

## 4. Setup Environment Variables

Gumawa ng `.env` file sa loob ng `backend/` folder kasama ang manage.py:

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

## 5. Run Database Migrations

Siguraduhing updated ang database tables:

```bash
python manage.py migrate
```

---

## 6. Create Admin Account (Optional)

Kung kailangan mo ng access sa **Django Admin Dashboard**, gumawa ng superuser:

```bash
python manage.py createsuperuser
```

---

## 7. Run Development Server

Patakbuhin ang Django development server:

```bash
python manage.py runserver
```

Buksan sa browser:

```text
http://127.0.0.1:8000/
```

---

# 🛠️ Common Commands & Order Reset

| Command | Purpose |
|---|---|
| `python manage.py runserver` | Start development server |
| `python manage.py makemigrations` | Create migrations from model changes |
| `python manage.py migrate` | Apply migrations |
| `python manage.py createsuperuser` | Create admin account |
| `python manage.py shell` | Open Django interactive shell |
| `pip install -r requirements.txt` | Install project dependencies |

### 🔄 Reset / Clear All Orders (Testing Command)
Kung nais i-reset o i-clear ang lahat ng orders sa database para sa pagte-test:
1. Buksan ang Django shell:
   ```bash
   python manage.py shell
   ```
2. I-run ang mga sumusunod na Python commands:
   ```python
   from customer_portal.models import Order, OrderItem
   OrderItem.objects.all().delete()
   Order.objects.all().delete()
   exit()
   ```

---

# 🔌 System APIs & Endpoints

Ang sistema ay naglalaman ng mga sumusunod na pangunahing API endpoints para sa real-time POS scanning, kitchen board updates, at delivery tracking:

1. **Barcode & Queue Slip Processing API (`canteen_menu`)**
   - **Endpoint:** `/canteen/api/process-barcode/`
   - **Method:** `POST`
   - **Payload:** `{"queue_slip": "#CE-1001"}` (or scanned barcode string)
   - **Purpose:** Hinahanap sa database ang kiosk queue slip, kino-convert ang status mula `unpaid` patungong `pending` (mark as paid), at kino-confirm ang pagbabayad sa Counter POS.

2. **Kitchen Order Status Update API (`kitchen_display`)**
   - **Endpoint:** `/kitchen/order/<int:order_id>/update-status/`
   - **Method:** `POST`
   - **Payload:** `{"status": "ready"}` o `{"status": "completed"}`
   - **Purpose:** Real-time AJAX endpoint para i-update ang order status ng kitchen board (Kiosk Accepted/Delivery -> Orders Ready -> Completed).

3. **Customer Kiosk & Ordering APIs (`customer_portal`)**
   - **Endpoint:** `/kiosk/` and associated menu/cart endpoints.
   - **Method:** `GET`, `POST`
   - **Purpose:** Kinukuha ang daily menu items, pinamamahalaan ang cart, at nagp-process ng bagong kiosk o delivery order na may kasamang queue slip at QR/barcode generation.

4. **Delivery & Live Chat APIs (`deliveries`)**
   - **Endpoints:** `/deliveries/...`
   - **Method:** `GET`, `POST`
   - **Purpose:** Nagbibigay-daan sa mga delivery riders na i-accept ang mga delivery requests, mag-update ng GPS location/status, at makipag-chat nang real-time sa faculty/staff customer.

---

# 📁 Backend Structure

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

# ⚠️ Troubleshooting

### `ModuleNotFoundError`
Siguraduhing naka-activate ang virtual environment at naka-install ang dependencies:
```powershell
.\venv\Scripts\Activate
pip install -r requirements.txt
```

### Database Connection Error
Suriin ang `.env` file kung tama ang `DB_HOST`, `DB_USER`, at `DB_PASSWORD`. Kung walang `.env`, gagamitin nito ang lokal na `db.sqlite3` fallback.

---

# 🎯 Ready to Develop!

```text
http://127.0.0.1:8000/
```

**Happy coding, team! 💻**

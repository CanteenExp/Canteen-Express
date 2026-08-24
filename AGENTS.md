# AGENTS.md

## Repository Overview & Working Directory
- **Backend framework:** Django 5.x (Python 3.10+, recommended 3.12)
- **Active working directory:** Django app root is inside `backend/` (`backend/manage.py`). Always run Django commands relative to `backend/` or set `workdir="backend"`.
- **Virtual environment:** Located at `venv/`. Activate using `.\venv\Scripts\Activate.ps1` (Windows PowerShell) or `source venv/bin/activate` (POSIX).

## Essential Commands
All commands run inside `backend/`:
- **Run dev server:** `python manage.py runserver`
- **Apply database migrations:** `python manage.py migrate`
- **Make new migrations:** `python manage.py makemigrations`
- **Run tests:** `python manage.py test`
- **Run specific app test:** `python manage.py test customer_portal`

## Operational Gotchas & Environment Setup
- **Environment variables:** `.env` file must be located directly inside `backend/` alongside `manage.py`. Key keys: `SECRET_KEY`, `DEBUG`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.
- **Database fallback:** `settings.py` defaults to `backend/db.sqlite3` if PostgreSQL/Neon config in `.env` is unpopulated or missing.
- **Media files:** `MEDIA_ROOT` points to `backend/media`. Media URL routes served conditionally when `DEBUG=True`.
- **Windows CP1252 encoding error:** Avoid using complex Unicode emojis (e.g., 📍, 📄, 🔑) in backend print statements (such as in `settings.py` or management commands) because standard Windows PowerShell/CMD terminal runtimes encoding with CP1252 will raise a fatal `UnicodeEncodeError`.

## Architecture & Model Notes
- **App Boundaries:**
  - `customer_portal`: Kiosk UI, guest/student ordering flow, `customer_portal.models.Order` and `OrderItem`.
  - `canteen_menu`: Menu item management, counter POS screen (`counter_pos.html`), and barcode processing endpoints.
  - `kitchen_display`: Kitchen board view for order processing.
  - `order_management`: Secondary order models used for registered/faculty users.
  - `queuing`: Digital queue slip generation and tracking models.
  - `admin_dashboard`: Administrative oversight, staff management, and dashboards.
  - `deliveries`: Order delivery management and tracking.
  - `user_notifications`: User alerting and notification system.
  - `core_app`: Core utilities, shared models, and base logic.
- **System Roles & Core Workflows:**
  - **1. Customers:**
    - *Students / Walk-ins:* Kiosk-style ordering, generates queue slips (`#CE-XXXX`), counter pickup.
    - *Faculty / Staff:* Registered user accounts supporting delivery mode (specifying building/room) or pickup.
  - **2. Canteen Staff / Admin:**
    - *Menu Management:* CRUD categories and daily menu items.
    - *POS & Kitchen Board:* Counter POS barcode scanning & real-time kitchen order processing.
    - *Management Dashboards:* Dashboard Overview, Menu Management, User Management (customers & riders), Feedback & Ratings, and Sales Reports (daily/weekly/monthly/yearly).
  - **3. Delivery Personnel (Riders):**
    - Accepts delivery requests from Faculty/Staff, triggers kitchen board -> pickup from canteen -> communicates with customer -> delivers with photo proof.
    - Remits cash payment to cashier -> canteen staff marks payment as remitted.
- **Queue Slip & POS Scanning Quirks:**
  - Kiosk generates orders with `order_number` formatted as `#CE-XXXX`.
  - POS interface (`canteen_menu/templates/canteen_menu/counter_pos.html`) scans barcodes (Code 128 / Code 39) or accepts manual input.
  - API endpoint `canteen_menu:process_barcode_api` (`/canteen/api/process-barcode/`) is designed to look up and verify kiosk queue slips in the database.

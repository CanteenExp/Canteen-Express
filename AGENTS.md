# AGENTS.md

## Repository Overview & Working Directory
- **Backend framework:** Django 6.0.7 (Python 3.10+, recommended 3.12)
- **Active working directory:** Django app root is inside `backend/` (`backend/manage.py`). Always run Django commands relative to `backend/` or set `workdir="backend"`.
- **Virtual environment:** Located at `venv/`. Activate using `.\venv\Scripts\Activate.ps1` (Windows PowerShell) or `source venv/bin/activate` (POSIX).

## Essential Commands (Run inside `backend/`)
- **Run dev server:** `python manage.py runserver`
- **Apply database migrations:** `python manage.py migrate`
- **Make new migrations:** `python manage.py makemigrations`
- **Run tests:** `python manage.py test` (Use `python manage.py test --keepdb` to avoid Neon DB test DB recreation prompts).
- **Run specific app test:** `python manage.py test customer_portal`
- **Interactive shell:** `python manage.py shell`

## Operational Gotchas & Environment Setup
- **Environment variables:** `.env` file must be located directly inside `backend/` alongside `manage.py`. Key keys: `SECRET_KEY`, `DEBUG`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.
- **Database fallback:** Configured for Neon Cloud PostgreSQL (`sslmode='require'`). Falls back or connects via `.env` credentials.
- **Media files:** `MEDIA_ROOT` points to `backend/media`. Media URL routes served conditionally when `DEBUG=True` via `config/urls.py`.
- **Windows CP1252 encoding error:** Avoid complex Unicode emojis in backend print statements/management commands. Use FontAwesome icons in HTML templates instead.

---

## Role-Based Workflows & Flowcharts

### 1. Customer Flow (Students / Walk-ins vs. Faculty / Staff)
```text
[Landing / Role Selection]
       │
       ├──► [Student / Walk-in (Kiosk)]
       │     ├──► Browse Menu / Cart (/kiosk/)
       │     ├──► Checkout ──► Generates Queue Slip (#CE-XXXX) & Barcode/QR
       │     ├──► Counter Payment & Verification (/canteen/api/process-barcode/)
       │     └──► Kitchen Preparation ──► Counter Pickup
       │
       └──► [Faculty / Staff (Delivery & Account)]
             ├──► Sign In / Up (@psu.palawan.edu.ph) (/accounts/)
             ├──► Delivery Mode & Building/Room Location Specification
             ├──► Cart Checkout (+₱15/₱300 convenience fee, earns loyalty pts: 1pt/₱100)
             └──► Rider Match ──► Live Chat & Tracking ──► Delivery Complete
```

### 2. Canteen Staff & Admin Flow
```text
[Staff / Admin Login]
       │
       ├──► Staff Login (/accounts/staff-login/) or Admin Pin Verify (/kitchen/admin-control/verify/)
       │
       ├──► Counter POS & Barcode Scanning (/canteen/api/process-barcode/)
       │     └──► Scans Queue Slip ──► Converts status from 'unpaid' to 'pending' (paid)
       │
       ├──► Kitchen Display Kanban Board (/kitchen/kitchen-board/)
       │     └──► Workflow: [Kiosk Accepted / Delivery] ──► [Orders Ready] ──► [Completed]
       │
       └──► Management Dashboards (/canteen/ / admin_dashboard/)
             ├──► Menu CRUD & Stock Management (/canteen/)
             └──► Sales Reports & Analytics (Chart.js daily/weekly/monthly)
```

### 3. Delivery Personnel (Rider) Flow
```text
[Rider Login (/accounts/delivery-login/)]
       │
       └──► Delivery Dashboard (/deliveries/dashboard/)
             ├──► Browse & Accept Available Delivery Requests
             ├──► Pickup Order from Canteen
             ├──► Real-Time Live Chat with Faculty Customer (/deliveries/messages/...)
             └──► Mark as Delivered ──► Complete (Earns ₱30 per completed delivery)
```

## App Boundaries & Key Modules
- `customer_portal`: Kiosk UI, guest/student ordering, queue slip & QR generation.
- `canteen_menu`: Menu item management, Counter POS screen (`counter_pos.html`), barcode processing API (`/canteen/api/process-barcode/`).
- `kitchen_display`: Kanban board for order status workflow (`update_order_status`).
- `accounts`: User roles (`STUDENT`, `FACULTY`, `STAFF`, `DELIVERY`), faculty auth (@psu.palawan.edu.ph), staff & rider login portals.
- `deliveries`: Delivery requests, rider assignment, and live chat (`DeliveryMessage`).
- `queuing`: Digital queue slip tracking models.
- `admin_dashboard` & `analytics_reports`: Staff oversight, sales reporting, and analytics.

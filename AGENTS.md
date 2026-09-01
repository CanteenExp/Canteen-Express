# AGENTS.md

## Repository Overview & Working Directory
- **Backend framework:** Django 6.0.7 (Python 3.10+, recommended 3.12)
- **Active working directory:** Django app root is inside `backend/` (`backend/manage.py`). Always run Django commands relative to `backend/` or set `workdir="backend"`.
- **Virtual environment:** Located at `venv/`. Activate using `.\venv\Scripts\Activate.ps1` (Windows PowerShell) or `source venv/bin/activate` (POSIX).

## Essential Commands (Run inside `backend/`)
- **Run dev server:** `python manage.py runserver`
- **Apply database migrations:** `python manage.py migrate`
- **Make new migrations:** `python manage.py makemigrations`
- **Run tests:** `python manage.py test --keepdb` (ALWAYS use `--keepdb` to avoid slow/flaky Neon Cloud PostgreSQL test DB recreation prompts).
- **Run specific app test:** `python manage.py test deliveries customer_portal`
- **Interactive shell:** `python manage.py shell`

## Operational Gotchas & Quirks
- **Environment variables:** `.env` file must be located directly inside `backend/` alongside `manage.py`.
- **Database fallback:** Configured for Neon Cloud PostgreSQL (`sslmode='require'`). Falls back or connects via `.env` credentials.
- **Campus Geofence:** Official center `9.77778, 118.73333` (PSU Tiniguiban Heights), radius `0.8` km (`deliveries/utils.py`). Out-of-campus orders or missing destination coordinates reject checkout with HTTP `422`.
- **Dark Maps:** Leaflet maps use free OSM tiles with CSS invert filter on `.leaflet-tile-pane` for dark mode (no API keys required).
- **Windows CP1252 encoding error:** Avoid complex Unicode emojis in backend print statements/management commands. Use FontAwesome icons in HTML templates instead.

## App Boundaries & Key Modules
- `customer_portal`: Kiosk UI, guest/student ordering, queue slip & QR generation.
- `canteen_menu`: Menu item management, Counter POS screen (`counter_pos.html`), barcode processing API (`/canteen/api/process-barcode/`).
- `kitchen_display`: Kanban board for order status workflow (`update_order_status`).
- `accounts`: User roles (`STUDENT`, `FACULTY`, `STAFF`, `DELIVERY`), faculty auth (@psu.palawan.edu.ph), staff & rider login portals.
- `deliveries`: Delivery requests, rider assignment, real-time live GPS tracking (`watchPosition`), and live chat (`DeliveryMessage`).
- `queuing`: Digital queue slip tracking models.
- `admin_dashboard` & `analytics_reports`: Staff oversight, sales reporting, and analytics.

# AGENTS.md

## Repository Overview & Working Directory
- **Backend framework:** Django 5.1.5 (Python 3.10+, recommended 3.12)
- **Active working directory:** Django app root is inside `backend/` (`backend/manage.py`). Always run Django commands relative to `backend/` or set `workdir="backend"`.
- **Virtual environment:** Located at `backend/venv/` or root `venv/`. Activate using `.\venv\Scripts\Activate.ps1` (Windows PowerShell) or `source venv/bin/activate` (POSIX).

## Essential Commands (Run inside `backend/`)
- **Run dev server:** `python manage.py runserver`
- **Run production server (Gunicorn):** `gunicorn --chdir backend config.wsgi:application` (or `gunicorn config.wsgi:application` when in `backend/`)
- **Collect static files:** `python manage.py collectstatic --noinput`
- **Apply database migrations:** `python manage.py migrate`
- **Make new migrations:** `python manage.py makemigrations`
- **Run tests:** `python manage.py test --keepdb` (ALWAYS use `--keepdb` to avoid slow/flaky Supabase PostgreSQL test DB recreation prompts).
- **Run specific app test:** `python manage.py test deliveries customer_portal`
- **Interactive shell:** `python manage.py shell`
- **Reset orders (testing):** Run in `python manage.py shell`: `from customer_portal.models import Order, OrderItem; OrderItem.objects.all().delete(); Order.objects.all().delete()`
- **Deployment Build Command (Render):** `pip install -r backend/requirements.txt && python backend/manage.py collectstatic --noinput && python backend/manage.py migrate`

## Operational Gotchas & Environment Setup
- **Environment variables:** `.env` file must be located directly inside `backend/` alongside `manage.py`. Key keys: `SECRET_KEY`, `DEBUG`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.
- **Database fallback:** Configured for Supabase PostgreSQL (`sslmode='require'`). Falls back to SQLite (`db.sqlite3`) if `.env` is absent or connection fails.
- **Media files:** `MEDIA_ROOT` points to `backend/media`. Media URL routes served conditionally when `DEBUG=True` via `config/urls.py`.
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

## Order Flow (canonical)
- **Kiosk (pickup):** Customer builds cart -> checkout -> Order created `unpaid` -> queue slip w/ barcode shown and saved to kiosk order history (`localStorage`). Abandoned `unpaid` slips are cancelled at the counter.
- **Counter POS (`/canteen/api/process-barcode/` `confirm_payment`):** Staff scans slip -> confirms payment -> Order flips `unpaid -> pending` and is sent to the Kitchen Board. The kiosk receipt auto-pops when polling sees a non-`unpaid` status.
- **Kitchen Board (`kitchen_display`):** `pending -> preparing -> ready -> completed` for both pickup and delivery orders. Loyalty points credit at completion (`credit_points_for_order` in `update_order_status`); cancelling refunds points and restores stock.
- **Rider (`deliveries`):** Delivery order -> kitchen marks `ready` -> rider dispatch -> `completed` on handoff (live GPS + chat).
- **Rating gate (`submit_feedback_api`):** Orders are rateable only once `status == 'completed'` (pickup after the kitchen finishes, delivery after the rider hands off).

## Delivery Routing (road-following maps)
- `deliveries/routing.py`: `get_road_route(origin, dest)` returns `{'path': [[lat, lng]...], 'distance_km', 'duration_min', 'provider'}` or `None`. Providers are tried in order — OSRM driving (`OSRM_BASE_URL`), then Valhalla pedestrian (`VALHALLA_BASE_URL`) for campus footpaths a car graph cannot reach.
- `get_tracking` (`deliveries/views.py`) embeds `path` + `routing_provider` in its JSON; `remaining_km` uses the **road** distance when available, else haversine. `delivery_tracking.html` and `accounts/dashboard.html` draw `data.path` (solid orange + white casing) and fall back to the dashed straight line when `path` is `null` — so a routing outage degrades instead of breaking tracking.
- **Never fatal:** all provider errors are swallowed, results cached in `cache` (coordinates rounded to 4 decimals ≈ 11 m, `ROUTING_CACHE_SECONDS`), and failures cached for 60s. Set `ROUTING_ENABLED=False` to disable entirely. Routing is force-disabled while the test suite runs (`sys.argv`), so unit tests never touch the network.

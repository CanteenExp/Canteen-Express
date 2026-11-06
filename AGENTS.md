# AGENTS.md

## Layout
- Django 5.1.5 / Python 3.12. The project root is `backend/` (`backend/manage.py`, `backend/config/`). Run every Django command from `backend/`; a template path like `templates/x.html` means `backend/templates/x.html`.
- Repo root is tooling + assets only: `package.json` / `build-css.js` (Tailwind), `render.yaml`, `runserver.bat`, and menu photos (`Ulams/`, `Meryenda/`, `Biscuits & Beverages/`).
- Install from `backend/requirements.txt`. The root `requirements.txt` is a stale duplicate (Django 6.0.7, no gunicorn/whitenoise) — ignore it.
- No pyproject/linter/formatter/CI and no JS bundler. Verification = `manage.py test` + `makemigrations --check`.
- Apps that are basically empty stubs (do not build features there): `admin_dashboard`, `analytics_reports`, `user_notifications`, `queuing` (models only), `order_management`.

## Commands (run in `backend/`)
```bash
python manage.py runserver                 # dev server
python manage.py test --keepdb             # full suite; --keepdb is the habit here
python manage.py test deliveries customer_portal --keepdb
python manage.py test activity_log.tests.ActivityLogAPITestCase --keepdb   # one class
python manage.py reset_orders              # wipes orders/feedback/deliveries/ActivityLog + zeroes loyalty_points
python manage.py makemigrations --check --dry-run
python manage.py update_supabase_images    # also: sync_menu_images, reset_faculty_data
```
- Tailwind CSS: `npm install` (once) then `npm run build:css` at the repo root. Output goes to `backend/static/css/`.
- Windows shortcut: `runserver.bat` starts `runserver` plus a localtunnel on port 8000.
- Prod: `gunicorn --chdir backend config.wsgi:application`; `render.yaml` build = pip install + `collectstatic` + `migrate`. `collectstatic` is optional locally (`WHITENOISE_USE_FINDERS=True`).

## Tests / settings quirks
- When `sys.argv[1] == 'test'` (or `'test' in sys.argv`) settings force in-memory SQLite, MD5 password hashing, `ENFORCE_OPERATING_HOURS=False`, and `deliveries/routing.py` refuses network calls. Tests never touch Supabase; opt in with `TEST_USE_REMOTE_DB=True`.
- Tests live in each app's `tests.py` (Django `TestCase`), no pytest. A suite-wide run logs a deliberate `ERROR activity_log.services` traceback from a "log must never raise" test — that is not a failure.

## Environment / DB
- `.env` must be at `backend/.env` (loaded with `override=True`; a missing file is normal in production). Settings print a diagnostics banner on every command — that noise is expected.
- Database: SQLite when `USE_SQLITE=True` **or `DB_HOST` is empty**, otherwise Supabase Postgres via the retrying backend `config.db_backends.postgresql`. A `sqlite_backup` alias also exists.
- `SystemGateMiddleware` gates only `/kiosk`, `/kiosk/`, `/kiosk/api/checkout/` while the canteen is closed (JSON 423 or redirect to the closed page). Staff/admin always pass, so closed-canteen testing still reaches dashboards.
- Operating hours default Mon–Fri 08:00–17:00 `Asia/Manila`; set `ENFORCE_OPERATING_HOURS=False` for night/weekend work.
- Windows CP1252: avoid emoji/Unicode symbols in Python `print` and management-command output (UnicodeEncodeError); use FontAwesome in templates.

## Two of everything — the main source of wrong-file edits
- **Staff dashboard**: the live one is `canteen_menu.views.staff_dashboard` → `canteen_menu/templates/canteen_menu/staff_dashboard.html` (Alpine tabs + `components/staff_sidebar.html` + `design-system.css`). It demands a per-session token, so `/canteen/dashboard/` always 302s to `/canteen/<session-token>/dashboard/`. `kitchen_display.views.staff_dashboard` → `templates/staff_dashboard.html` is the older dark dashboard served at `/kitchen/dashboard/`.
- **Admin page**: `templates/admin_dashboard.html` (System Administration + the transaction-log table) is rendered by `kitchen_display.admin_governance`, *not* by the `admin_dashboard` app. It requires the PIN gate at `/kitchen/admin-control/verify/` (`ADMIN_PIN`, dev default `CE-1234`, session unlock lasts 2h) and has no nav link.
- **Order**: `customer_portal.models.Order` / `OrderItem` / `OrderFeedback` are canonical (lowercase statuses). `order_management.models.Order` is a dead duplicate with uppercase statuses — never query it.
- **Menu**: `canteen_menu.models.MenuItem` (+ `Category`, has `stock`) is canonical. `customer_portal.models.MenuItem` is legacy and unused by views.

## Order lifecycle
- Kiosk checkout ( `/kiosk/api/checkout/` ) creates `unpaid` + a slip; unpaid slips are auto-cancelled after 1 hour by the lazy sweep `customer_portal.views.expire_stale_unpaid_orders()` (there is no worker/cron — it piggybacks on status polls, barcode scans, history).
- Counter scan (`/canteen/api/process-barcode/` with `action=confirm_payment`) moves `unpaid → ready` directly (not `pending`) and writes an ActivityLog row. Already-paid slips re-issue the receipt instead of erroring.
- Kitchen board (`kitchen_display.views.update_order_status`) enforces `ALLOWED_MOVES`; loyalty points credit on `completed`, and `cancelled` refunds points and restores stock. Log status changes *after* the atomic block commits.
- Revenue/sales aggregates count only `status in ('ready', 'completed')`; keep that convention when adding reports.
- Guest vs account: `order.customer` is null for walk-ins (`student_name`/`guest_*` instead); role filters treat `customer__isnull=True` as Student/Walk-in.

## Roles / auth
- Stored roles: `STUDENT | FACULTY | STAFF | DELIVERY` on `accounts.CustomUser.role`. `RIDER` and `ADMIN` appear in `@role_required` calls but are never stored; admin-level access comes from `is_staff` / `is_superuser`.
- Faculty login is **not** Django auth: it sets `session['faculty_email']` (plus a URL session token for the dashboard), and `accounts/decorators.role_required` special-cases it.
- Faculty OTP signup/reset needs SMTP; Render/Railway free tiers block ports 25/465/587, and the on-screen OTP fallback is DEBUG-only.

## Logs
- `activity_log.ActivityLog` is append-only (no soft delete by design). Write via `activity_log.services.log_activity(...)` / `log_menu_change(...)`; the helper swallows all exceptions on purpose — an audit write must never break a payment. Log after the transaction commits.
- Staff feed: `GET /api/logs/` (STAFF/ADMIN, paginated, filters `category`/`level`/`days`/`q`), polled by the Activity Log tab in the staff dashboard.
- The cross-role "transaction logs" table for students/walk-ins, faculty/staff and delivery personnel is the order table in `templates/admin_dashboard.html`, fed by `kitchen_display.admin_governance` (`role_filter=all|faculty|student|delivery`, `q` search, newest 100).

## Frontend
- Tailwind is precompiled, not CDN-JIT: each `backend/tailwindcss/<group>.config.js` has its own `content` globs and writes `backend/static/css/<group>.css`. New utilities in a template only ship if that template is listed in a config's `content`; then run `npm run build:css`. Otherwise the page renders unstyled classes.
- Page JS is inline `x-data` Alpine + vanilla `fetch`; no build step. Reusable staff UI lives in `backend/templates/components/`.

## Delivery maps and geofence
- `deliveries/routing.py::get_road_route(origin, dest)` returns `{'path', 'distance_km', 'duration_min', 'provider'}` or `None`; providers OSRM (driving) then Valhalla (pedestrian), both key-less, cached ~11 m precision, failures cached 60 s. Every error is swallowed and callers fall back to a dashed straight line — keep it non-fatal, and never let routing break tracking.
- Geofence: center `9.77778, 118.73333`, radius `0.8` km (`deliveries/utils.py`); out-of-campus or missing `dest_lat/dest_lng` is rejected with HTTP 422 when `ENFORCE_GEOFENCE=True`.
- Tracking progress uses `route_total_km` (rider's **first** recorded `RiderLocationPoint` → destination), not `total_distance_km` (jittery breadcrumb length). Do not derive the pickup origin from `CAMPUS_CENTER_*`: real drop-offs sit on that point and would collapse the total to 0.
- `DeliveryRequest.status` is uppercase (`SEARCHING/ACCEPTED/DELIVERED/REJECTED/TIMEOUT`); rider dispatch is a first-to-accept pool (`accept_delivery` guards it atomically), not pre-assignment.

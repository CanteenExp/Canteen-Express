"""Gate the customer ordering surface while the canteen is manually closed.

Deliberately narrow. When staff close the canteen we only want to stop people
*ordering*; everybody must still be able to reach their own tools:

    * customers land on the "closed" notice instead of the kiosk welcome page,
    * an already-issued order (unpaid slip or a delivery already on its way)
      stays trackable -- the order-status API and the ordering pages are the
      two things we do NOT gate, so a customer with food in flight is never
      locked out of their own order,
    * checkout is refused server-side no matter who posts it,
    * staff / admin / kitchen / riders / faculty dashboards are never touched,
      otherwise nobody could reopen the canteen.

Cost when open: one cached dict lookup per gated request, no query. Everything
outside GATED_* short-circuits on a string check, so the other ~99% of traffic
pays nothing at all.
"""

from django.http import JsonResponse
from django.shortcuts import redirect

from .system_status import get_status

# The kiosk welcome page: the public front door for ordering.
GATED_EXACT_PATHS = ('/kiosk', '/kiosk/')

# The rest of the customer ordering surface. Prefixes rather than exact paths
# so every sub-screen (menu, a future cart page, the menu feed) is covered by
# one rule and nothing new can slip through unguarded.
GATED_PREFIXES = (
    '/kiosk/menu',
    '/kiosk/api/menu/',
    '/kiosk/api/checkout/',
)

# ...but these under the gated prefixes must still resolve while closed, because
# they only ever *read* an order the customer already has. Making them 423 would
# strand someone whose food is already being delivered.
ALLOWED_PREFIXES = (
    '/kiosk/api/order-status/',
    '/kiosk/api/submit-feedback/',
)

# Roles that must keep full access so they can reopen the canteen.
STAFF_ROLES = ('STAFF', 'ADMIN')


def _is_staff(request):
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser or user.is_staff:
        return True
    return getattr(user, 'role', '').upper() in STAFF_ROLES


def _wants_json(request):
    if request.path.startswith('/kiosk/api/'):
        return True
    if request.method != 'GET':
        return True
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return True
    return 'application/json' in request.headers.get('accept', '')


class SystemGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        gated = path in GATED_EXACT_PATHS or path.startswith(GATED_PREFIXES)
        if gated and not path.startswith(ALLOWED_PREFIXES):
            status = get_status()
            if not status['is_open'] and not _is_staff(request):
                message = status['message'] or 'The canteen is closed right now. Please come back later.'
                if _wants_json(request):
                    return JsonResponse(
                        {'success': False, 'message': message, 'system_closed': True},
                        status=423,
                    )
                return redirect('core_app:system_closed')

        return self.get_response(request)

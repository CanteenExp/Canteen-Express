"""Gate the customer ordering surface while the canteen is manually closed.

Deliberately narrow. When staff close the canteen we only want to stop people
*ordering*; everybody must still be able to reach their own tools:

    * customers land on the "closed" notice instead of the kiosk welcome page,
    * an already-issued queue slip stays viewable (the menu page still loads),
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

# Checkout is shared by the kiosk AND the faculty dashboard, so refusing it here
# covers both ordering flows at once.
GATED_PREFIXES = ('/kiosk/api/checkout/',)

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

        if path in GATED_EXACT_PATHS or path.startswith(GATED_PREFIXES):
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

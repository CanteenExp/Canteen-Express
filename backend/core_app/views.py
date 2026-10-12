"""Views behind the manual "canteen is open" switch.

Three endpoints live here:

    system_status_api   GET   -- cheap, cache-backed feed the kiosk/faculty
                                 pages poll so a closure shows up live.
    system_toggle_api   POST  -- the actual switch, staff/admin only.
    system_closed       GET   -- the public notice customers land on.
"""

import json
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import role_required
from activity_log.models import ActivityLog
from activity_log.services import log_activity

from .system_status import get_status, is_accepting_orders, set_open

logger = logging.getLogger(__name__)


@require_GET
def system_status_api(request):
    """Live status, read straight from the cache.

    Touches no database on purpose: every kiosk and faculty dashboard may poll
    this, so it must stay as cheap as a dict lookup. The browser is told not to
    cache it either, otherwise a stale "open" would survive a closure.
    """
    status = get_status()
    response = JsonResponse({
        'success': True,
        'is_open': status['is_open'],
        'accepting_orders': is_accepting_orders(),
        'message': status['message'],
        'closed_at': status['closed_at'],
    })
    response['Cache-Control'] = 'no-store'
    return response


@require_POST
@role_required(allowed_roles=['STAFF', 'ADMIN'])
def system_toggle_api(request):
    """Flip the switch. Body: {"is_open": bool, "message": str} (both optional).

    Omitting is_open toggles, which is what the dashboard button sends.
    """
    try:
        data = json.loads(request.body or b'{}')
        if not isinstance(data, dict):
            data = {}
    except (ValueError, TypeError):
        data = {}

    raw = data.get('is_open', None)
    if raw is None:
        open_now = not get_status()['is_open']
    elif isinstance(raw, bool):
        open_now = raw
    else:
        open_now = str(raw).strip().lower() in ('1', 'true', 'yes', 'open', 'on')

    message = str(data.get('message') or '')[:200]
    status = set_open(open_now, message=message, user=request.user)

    log_activity(
        request,
        action=('Reopened the canteen for orders' if open_now
                else 'Closed the canteen for orders'),
        category=ActivityLog.Category.SYSTEM,
        level=ActivityLog.Level.SUCCESS if open_now else ActivityLog.Level.WARNING,
        target='Canteen Express',
        metadata={'message': status['message']} if status['message'] else None,
    )

    return JsonResponse({
        'success': True,
        'is_open': status['is_open'],
        'message': status['message'],
        'closed_at': status['closed_at'],
        'notice': ('Canteen is now OPEN. Customers can order again.' if open_now
                   else 'Canteen is now CLOSED. New orders are blocked.'),
    })


def system_closed(request):
    """Public "we are closed" notice reached by customers while closed."""
    status = get_status()
    response = render(request, 'core_app/system_closed.html', {
        'system_status': status,
        'closed_message': status['message'],
    })
    # Never cache: the page must disappear the moment staff reopen.
    response['Cache-Control'] = 'no-store'
    return response

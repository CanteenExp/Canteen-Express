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

from core_app import utils as core_utils

from .system_status import (
    MODE_AUTO,
    MODE_FORCE_CLOSED,
    MODE_FORCE_OPEN,
    SCHEDULE_REASON_CODE,
    VALID_MODES,
    get_status,
    is_accepting_orders,
    set_mode,
)

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
        'mode': status['mode'],
        'mode_label': status['mode_label'],
        'is_override': status['is_override'],
        'schedule_open': status['schedule_open'],
        'message': status['message'],
        'reason_code': status['reason_code'],
        'reason_label': status['reason_label'],
        'closed_at': status['closed_at'],
        'operating_hours': core_utils.operating_hours_text(),
        'next_opening': '' if status['is_open'] else core_utils.next_opening_text(),
    })
    response['Cache-Control'] = 'no-store'
    return response


@require_POST
@role_required(allowed_roles=['STAFF', 'ADMIN'])
def system_toggle_api(request):
    """Set the canteen state.

    Body: {"mode": "AUTO"|"FORCE_OPEN"|"FORCE_CLOSED", "reason_code": str,
           "message": str}

    `is_open: true/false` is still accepted for compatibility and maps onto
    FORCE_OPEN / FORCE_CLOSED. With neither field the request toggles the
    override, which is what the old one-button control sent. The customer-facing
    text is derived from reason_code so the public notice can never carry an
    internal note.
    """
    try:
        data = json.loads(request.body or b'{}')
        if not isinstance(data, dict):
            data = {}
    except (ValueError, TypeError):
        data = {}

    mode = str(data.get('mode') or '').strip().upper()
    if 'mode' in data and mode not in VALID_MODES:
        return JsonResponse(
            {'success': False,
             'message': f"Unknown mode. Use one of: {', '.join(VALID_MODES)}."},
            status=400,
        )

    if not mode:
        raw = data.get('is_open', None)
        if raw is None:
            open_now = not get_status()['is_open']
        elif isinstance(raw, bool):
            open_now = raw
        else:
            open_now = str(raw).strip().lower() in ('1', 'true', 'yes', 'open', 'on')
        mode = MODE_FORCE_OPEN if open_now else MODE_FORCE_CLOSED

    reason_code = str(data.get('reason_code') or '')[:32]
    message = str(data.get('message') or '')[:200]
    status = set_mode(mode, reason_code=reason_code, message=message, user=request.user)

    if mode == MODE_AUTO:
        action = 'Returned the canteen to its automatic schedule'
        level = ActivityLog.Level.INFO
        notice = (f'Back on the automatic schedule '
                  f'({core_utils.operating_hours_text()}).')
    elif mode == MODE_FORCE_OPEN:
        action = 'Opened the canteen outside the schedule'
        level = ActivityLog.Level.SUCCESS
        notice = 'Canteen is OPEN. Customers can order even outside the schedule.'
    else:
        action = 'Closed the canteen for orders'
        if status['reason_label']:
            action = f"Closed the canteen for orders — {status['reason_label']}"
        level = ActivityLog.Level.WARNING
        notice = 'Canteen is CLOSED. New orders are blocked.'

    log_activity(
        request,
        action=action,
        category=ActivityLog.Category.SYSTEM,
        level=level,
        target='Canteen Express',
        metadata={'mode': mode, 'reason_code': status['reason_code']} if status['reason_code']
        else {'mode': mode},
    )

    return JsonResponse({
        'success': True,
        'is_open': status['is_open'],
        'mode': status['mode'],
        'mode_label': status['mode_label'],
        'schedule_open': status['schedule_open'],
        'message': status['message'],
        'reason_code': status['reason_code'],
        'reason_label': status['reason_label'],
        'closed_at': status['closed_at'],
        'notice': notice,
    })


def system_closed(request):
    """Public "we are closed" notice reached by customers while closed."""
    status = get_status()
    response = render(request, 'core_app/system_closed.html', {
        'system_status': status,
        'closed_message': status['message'],
        'closed_reason_label': status['reason_label'],
        # Distinguishes "the timetable closed us" from "a person closed us", so
        # the page can say when ordering comes back instead of "check shortly".
        'schedule_closed': status['reason_code'] == SCHEDULE_REASON_CODE,
        'next_opening': '' if status['is_open'] else core_utils.next_opening_text(),
    })
    # Never cache: the page must disappear the moment staff reopen.
    response['Cache-Control'] = 'no-store'
    return response

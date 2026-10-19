from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from accounts.decorators import role_required
from .models import ActivityLog
from .services import resolve_actor

PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
# Kept short on purpose: this powers a "live" refresh in the staff dashboard.
# A minute of staleness on an audit panel is fine and keeps the DB load low.
REFRESH_SECONDS = 60


def _parse_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@role_required(allowed_roles=['STAFF', 'ADMIN'])
@require_GET
def activity_log_api(request):
    """Filtered, paginated activity feed.

    Returns JSON for the dashboard's Alpine panel. Kept as an API rather than a
    server-rendered page so the dashboard stays a single-page tab and can poll
    for new rows without a reload.
    """
    queryset = ActivityLog.objects.select_related('actor')

    category = (request.GET.get('category') or '').strip().upper()
    if category and category != 'ALL':
        if category in ActivityLog.Category.values:
            queryset = queryset.filter(category=category)
        else:
            # An unknown category is a client bug, not a 500 -- return empty
            # rather than silently ignoring the filter and showing everything.
            queryset = queryset.none()

    level = (request.GET.get('level') or '').strip().upper()
    if level and level != 'ALL':
        if level in ActivityLog.Level.values:
            queryset = queryset.filter(level=level)
        else:
            queryset = queryset.none()

    search = (request.GET.get('q') or '').strip()
    if search:
        queryset = queryset.filter(
            Q(action__icontains=search)
            | Q(target__icontains=search)
            | Q(actor_label__icontains=search)
        )

    days = _parse_int(request.GET.get('days'))
    if days and days > 0:
        cutoff = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(created_at__gte=cutoff)

    total = queryset.count()

    page_size = _parse_int(request.GET.get('page_size'), PAGE_SIZE) or PAGE_SIZE
    page_size = max(5, min(page_size, MAX_PAGE_SIZE))
    paginator = Paginator(queryset, page_size)
    page = paginator.get_page(_parse_int(request.GET.get('page'), 1))

    actor, actor_label = resolve_actor(request)

    return JsonResponse({
        'success': True,
        'total': total,
        'page': page.number,
        'num_pages': paginator.num_pages,
        'page_size': page_size,
        'has_next': page.has_next(),
        'has_previous': page.has_previous(),
        'refresh_seconds': REFRESH_SECONDS,
        'server_time': timezone.localtime().isoformat(),
        'viewer': actor_label,
        'categories': [
            {'value': value, 'label': label}
            for value, label in ActivityLog.Category.choices
        ],
        'levels': [
            {'value': value, 'label': label}
            for value, label in ActivityLog.Level.choices
        ],
        'results': [
            {
                'id': entry.id,
                'action': entry.action,
                'target': entry.target,
                'category': entry.category,
                'category_label': entry.get_category_display(),
                'level': entry.level,
                'actor': entry.actor_label,
                'actor_id': entry.actor_id,
                'is_guest': entry.is_guest,
                'metadata': entry.metadata or {},
                # ISO with offset so the browser formats it in the staff
                # member's own timezone, not the server's.
                'created_at': timezone.localtime(entry.created_at).isoformat(),
                'created_display': timezone.localtime(entry.created_at).strftime(
                    '%b %d, %Y - %I:%M %p'),
            }
            for entry in page.object_list
        ],
    })

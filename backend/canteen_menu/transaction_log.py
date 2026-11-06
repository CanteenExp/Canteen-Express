"""Server-side data for the staff "Transaction Logs" tab.

A transaction belongs in this ledger once the money has actually been
collected, which is what makes it different from the kitchen board:

* pickup -- the cashier confirms payment and the order leaves ``unpaid``
  (see ``canteen_menu.views.process_barcode_api``); from then on it is paid,
  whether the kitchen has it ``preparing``/``ready`` or already ``completed``;
* delivery -- the rider collects on handoff and
  ``deliveries.views.complete_delivery`` records the order as ``completed``
  with the delivery ``DELIVERED``.

Unpaid slips, cancelled/refunded orders and deliveries still on the road are
excluded on purpose: this is a sales ledger, not a queue board.

The tab lives inside the staff dashboard (``?tab=transactions``) and filters
through plain GET params, so every view of the ledger is linkable, printable
and exportable without any extra JavaScript.
"""

import csv
from datetime import timedelta
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.utils import timezone

from customer_portal.models import Order
from deliveries.models import DeliveryRequest

PAGE_SIZE = 20
SEARCH_MAX = 80

# Who the transaction belongs to. "Delivery personnel" is the delivery channel
# (orders a rider fulfilled), mirroring the System Administration role filter,
# so a faculty delivery order legitimately shows up under both groups.
GROUPS = (
    ('all', 'All transactions'),
    ('student', 'Students & walk-ins'),
    ('faculty', 'Faculty & staff'),
    ('delivery', 'Delivery personnel'),
)
GROUP_KEYS = {key for key, _ in GROUPS}

DATE_RANGES = (
    ('today', 'Today'),
    ('7', 'Last 7 days'),
    ('30', 'Last 30 days'),
    ('all', 'All time'),
)
DATE_RANGE_DAYS = {'today': 1, '7': 7, '30': 30}
DATE_RANGE_KEYS = {key for key, _ in DATE_RANGES}

# Paid pickup orders + handed-off deliveries. Keep this definition in one place:
# the tab, the summary cards and the CSV export must never disagree.
SUCCESSFUL_TRANSACTION_Q = (
    Q(delivery_info__isnull=True,
      status__in=('pending', 'preparing', 'ready', 'completed'))
    | Q(delivery_info__status=DeliveryRequest.RequestStatus.DELIVERED)
)


def successful_transactions():
    """Every order whose payment has been collected (see module docstring)."""
    return Order.objects.filter(SUCCESSFUL_TRANSACTION_Q)


def _apply_group(queryset, group):
    if group == 'student':
        return queryset.filter(Q(customer__isnull=True) | Q(customer__role='STUDENT'))
    if group == 'faculty':
        return queryset.filter(customer__role__in=['FACULTY', 'STAFF'])
    if group == 'delivery':
        return queryset.filter(delivery_info__isnull=False)
    return queryset


def _apply_date_range(queryset, days_key):
    days = DATE_RANGE_DAYS.get(days_key)
    if not days:
        return queryset
    cutoff = timezone.localdate() - timedelta(days=days - 1)
    return queryset.filter(created_at__date__gte=cutoff)


def _apply_search(queryset, search):
    if not search:
        return queryset
    return queryset.filter(
        Q(order_number__icontains=search)
        | Q(guest_name__icontains=search)
        | Q(guest_phone__icontains=search)
        | Q(customer__username__icontains=search)
        | Q(customer__first_name__icontains=search)
        | Q(customer__last_name__icontains=search)
        | Q(customer__email__icontains=search)
        | Q(delivery_info__delivery_location__icontains=search)
        | Q(delivery_info__rider__username__icontains=search)
        | Q(delivery_info__rider__first_name__icontains=search)
        | Q(delivery_info__rider__last_name__icontains=search)
    )


def filtered_transactions(group='all', days='all', search=''):
    """Successful transactions narrowed by the tab's filters, newest first."""
    queryset = successful_transactions()
    queryset = _apply_group(queryset, group)
    queryset = _apply_date_range(queryset, days)
    queryset = _apply_search(queryset, search)
    return (queryset
            .select_related('customer', 'delivery_info', 'delivery_info__rider')
            .prefetch_related('items', 'feedbacks')
            .order_by('-created_at', '-id'))


def parse_transaction_filters(request):
    """Read + sanitise the tab's GET filters. Unknown values fall back safely."""
    params = request.GET

    group = params.get('tx_group') or 'all'
    if group not in GROUP_KEYS:
        group = 'all'

    days = params.get('tx_days') or 'all'
    if days not in DATE_RANGE_KEYS:
        days = 'all'

    search = (params.get('tx_q') or '').strip()[:SEARCH_MAX]
    return group, days, search


def build_transaction_log(request):
    """Context for the Transaction Logs tab (filters + page + totals + links)."""
    group, days, search = parse_transaction_filters(request)

    queryset = filtered_transactions(group, days, search)

    totals = queryset.aggregate(
        subtotal=Sum('total_amount'),
        fees=Sum('delivery_fee'),
    )
    subtotal = float(totals['subtotal'] or 0)
    fees = float(totals['fees'] or 0)

    page_obj = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get('tx_page') or 1)

    def url_for(**overrides):
        query = {'tab': 'transactions', 'tx_group': group, 'tx_days': days}
        if search:
            query['tx_q'] = search
        query.update(overrides)
        return '?' + urlencode({k: v for k, v in query.items() if v})

    group_links = [
        {'key': key, 'label': label, 'url': url_for(tx_group=key, tx_page=1), 'active': key == group}
        for key, label in GROUPS
    ]
    date_links = [
        {'key': key, 'label': label, 'url': url_for(tx_days=key, tx_page=1), 'active': key == days}
        for key, label in DATE_RANGES
    ]

    # The CSV export keeps the filters but drops the tab/page params.
    export_query = {'tx_group': group, 'tx_days': days}
    if search:
        export_query['tx_q'] = search

    return {
        'tx_group': group,
        'tx_days': days,
        'tx_q': search,
        'tx_page_obj': page_obj,
        'tx_total': page_obj.paginator.count,
        'tx_page_size': PAGE_SIZE,
        'tx_summary': {
            'count': page_obj.paginator.count,
            'subtotal': subtotal,
            'fees': fees,
            'collected': subtotal + fees,
        },
        'tx_group_links': group_links,
        'tx_date_links': date_links,
        'tx_prev_url': url_for(tx_page=page_obj.previous_page_number()) if page_obj.has_previous() else '',
        'tx_next_url': url_for(tx_page=page_obj.next_page_number()) if page_obj.has_next() else '',
        'tx_export_query': urlencode(export_query),
        'tx_has_filters': bool(search or group != 'all' or days != 'all'),
        'tx_reset_url': '?tab=transactions',
    }


# --- CSV export -------------------------------------------------------------
# Staff need the ledger in a spreadsheet, so the same filtered queryset is
# flattened into one row per transaction (items joined into a single cell).

def _csv_safe(value):
    """Neutralise spreadsheet-formula injection and embedded newlines."""
    text = str('' if value is None else value).replace('\r', ' ').replace('\n', ' ')
    if text[:1] in ('=', '+', '-', '@'):
        return "'" + text
    return text


def _customer_group_label(order):
    if order.customer is None:
        return 'Walk-in guest'
    if order.customer.role in ('FACULTY', 'STAFF'):
        return 'Faculty / Staff'
    if order.customer.role == 'DELIVERY':
        return 'Delivery personnel'
    return 'Student'


def _customer_name(order):
    if order.customer:
        return order.customer.get_full_name().strip() or order.customer.username
    return order.guest_name or 'Walk-in guest'


def transaction_rows(queryset):
    """Flatten successful transactions into CSV-ready rows."""
    for order in queryset:
        delivery = getattr(order, 'delivery_info', None)
        rider = delivery.rider if delivery and delivery.rider else None
        items = '; '.join(
            f'{item.quantity}x {item.item_name} @ {item.price}'
            for item in order.items.all()
        )
        contact = ''
        if order.customer:
            contact = order.customer.email or order.customer.phone or ''
        else:
            contact = order.guest_phone or ''
        rating = next((fb.rating for fb in order.feedbacks.all()), '')
        yield [
            order.order_number,
            timezone.localtime(order.created_at).strftime('%Y-%m-%d %H:%M'),
            'Delivery' if delivery else 'Counter pickup',
            _customer_group_label(order),
            _customer_name(order),
            contact,
            delivery.delivery_location if delivery else '',
            (rider.get_full_name().strip() or rider.username) if rider else '',
            items,
            f'{float(order.total_amount):.2f}',
            f'{float(order.delivery_fee or 0):.2f}',
            f'{float(order.total_amount) + float(order.delivery_fee or 0):.2f}',
            order.get_status_display(),
            f'{float(order.points_redeemed or 0):.2f}',
            f'{float(order.points_earned or 0):.2f}',
            rating,
        ]


def csv_response(queryset):
    """Download the filtered ledger as a UTF-8 CSV (Excel-safe BOM included)."""
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f'canteen_transactions_{timezone.localdate():%Y%m%d}.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow([
        'Transaction', 'Date', 'Channel', 'Customer group', 'Customer',
        'Contact', 'Delivery location', 'Rider', 'Items', 'Subtotal (PHP)',
        'Delivery fee (PHP)', 'Collected (PHP)', 'Status',
        'Points redeemed', 'Points earned', 'Rating',
    ])
    for row in transaction_rows(queryset):
        writer.writerow([_csv_safe(value) for value in row])
    return response

"""Helpers that turn OrderFeedback rows into a channel-segregated staff view.

Kiosk (counter pick-up) and delivery reviews are graded against different
things -- food/service for the counter, food + rider experience for delivery --
so staff need to see them apart instead of one undifferentiated list.

`build_feedback_context` returns a single dict consumed by
`templates/partials/feedback_ratings_panel.html`, which both staff dashboards
include so the two surfaces can never drift apart.
"""

from customer_portal.models import OrderFeedback

MAX_ITEM_NAMES = 4


def _display_name(fb):
    customer = fb.customer
    if customer is not None:
        return customer.get_full_name() or customer.username
    order = fb.order
    if order is not None and order.guest_name:
        return order.guest_name
    return 'Walk-in Guest'


def _initials(name):
    parts = [p for p in str(name).replace('-', ' ').split() if p]
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][:1].upper()
    return (parts[0][:1] + parts[-1][:1]).upper()


def _decorate(fb, channel):
    """Attach the few template-facing fields the compact review card uses."""
    name = _display_name(fb)
    fb.channel = channel
    fb.display_name = name
    fb.initials = _initials(name)
    fb.stars = [n <= int(fb.rating) for n in range(1, 6)]
    fb.has_comment = bool((fb.comment or '').strip())
    return fb


def _stats(rows, label, icon, accent):
    """Average + 5..1 star distribution for one channel."""
    distribution = {n: 0 for n in range(1, 6)}
    total = 0
    for fb in rows:
        star = min(5, max(1, int(fb.rating)))
        distribution[star] += 1
        total += star

    count = len(rows)
    breakdown = [
        {
            'star': star,
            'count': distribution[star],
            'pct': int(round(distribution[star] * 100.0 / count)) if count else 0,
        }
        for star in range(5, 0, -1)
    ]

    avg = round(total / count, 1) if count else 0.0

    return {
        'label': label,
        'icon': icon,
        'accent': accent,
        'count': count,
        'avg': avg,
        'stars_filled': [n <= round(avg) for n in range(1, 6)],
        'breakdown': breakdown,
        'praised': sum(1 for fb in rows if fb.rating >= 4),
        'detractors': sum(1 for fb in rows if fb.rating <= 2),
        'with_comment': sum(1 for fb in rows if (fb.comment or '').strip()),
    }


def feedback_queryset():
    """Feedback newest-first with the joins the panel needs prefetched."""
    return (
        OrderFeedback.objects
        .select_related('customer', 'order', 'order__delivery_info')
        .order_by('-created_at')
    )


def build_feedback_context():
    """Split feedback into kiosk vs delivery with per-channel stats."""
    rows = list(feedback_queryset())

    kiosk, delivery = [], []
    for fb in rows:
        order = fb.order
        has_delivery = order is not None and hasattr(order, 'delivery_info')
        (delivery if has_delivery else kiosk).append(
            _decorate(fb, 'delivery' if has_delivery else 'kiosk')
        )

    avg_all = round(sum(int(fb.rating) for fb in rows) / len(rows), 1) if rows else 0.0

    return {
        'feedbacks': rows,
        'fb_kiosk': kiosk,
        'fb_delivery': delivery,
        'fb_kiosk_stats': _stats(kiosk, 'Kiosk / Counter Pick-up', 'fa-store', 'orange'),
        'fb_delivery_stats': _stats(delivery, 'Delivery', 'fa-motorcycle', 'sky'),
        'fb_total': len(rows),
        'fb_overall': {'count': len(rows), 'avg': avg_all},
    }

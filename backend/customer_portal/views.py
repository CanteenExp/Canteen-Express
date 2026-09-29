import json
import random
from decimal import Decimal
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.core.cache import cache
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from canteen_menu.models import MenuItem
from .models import Order, OrderItem


# Raised when an order cannot be created (stock, points, unique number) so the
# caller can turn it into a clean 4xx JSON instead of a raw 500.
class CheckoutError(Exception):
    pass


# Helper function to format active DB menu items for Kiosk JSON (with in-memory caching for lightning fast performance)
def _get_formatted_menu():
    cache_key = 'formatted_menu_active_kiosk'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    db_items = MenuItem.objects.select_related('category').filter(is_available=True).order_by('-id')
    formatted_menu = []
    for item in db_items:
        img_url = ''
        if hasattr(item, 'get_image_src'):
            attr = getattr(item, 'get_image_src')
            img_url = attr() if callable(attr) else attr
        elif hasattr(item, 'image') and item.image:
            try:
                img_url = item.image.url
            except ValueError:
                img_url = ''

        category_str = 'General'
        if hasattr(item, 'category') and item.category:
            category_str = item.category.name if hasattr(item.category, 'name') else str(item.category)

        formatted_menu.append({
            'id': item.id,
            'name': item.name,
            'category': category_str,
            'price': float(item.price) if item.price else 0.0,
            'desc': getattr(item, 'description', '') or getattr(item, 'desc', '') or '',
            'badge': getattr(item, 'badge', '') or '',
            'isSiomai': getattr(item, 'is_siomai', False) or getattr(item, 'isSiomai', False),
            'stock': getattr(item, 'stock', None),
            'img': img_url
        })
    cache.set(cache_key, formatted_menu, 60)
    return formatted_menu


# 1. CUSTOMER SIDE - Landing Page
def kiosk_welcome(request):
    return render(request, 'customer_portal/kiosk_welcome.html')


# 2. CUSTOMER SIDE - Main Menu Page
def kiosk_menu(request):
    formatted_menu = _get_formatted_menu()
    context = {
        'menu_data_json': json.dumps(formatted_menu)
    }
    return render(request, 'customer_portal/kiosk_menu.html', context)


# 3. CUSTOMER SIDE - Live Sync API
def get_kiosk_menu_api(request):
    formatted_menu = _get_formatted_menu()
    return JsonResponse({'status': 'success', 'menu': formatted_menu})


# 4. CUSTOMER SIDE - Checkout Endpoint
@require_POST
def process_checkout(request):
    try:
        data = json.loads(request.body)
        cart_items = data.get('cart', [])
        is_delivery = data.get('is_delivery', False)
        delivery_location = data.get('delivery_location', 'Faculty Office Building')

        if not cart_items:
            return JsonResponse({'success': False, 'message': 'Cart is empty.'}, status=400)

        user = request.user if request.user.is_authenticated else None

        # ===== Server-authoritative cart =====================================
        # Every line is validated against the LIVE database: real item id,
        # DB price, DB stock. Client-sent prices/totals are IGNORED, so a
        # tampered payload (price: 0.01) can neither cheapen the order nor farm
        # loyalty points.
        lines = {}  # {menu_item_id: {'menu_item': item, 'qty': qty}}
        for item in cart_items:
            try:
                qty = int(item.get('qty', 0))
            except (TypeError, ValueError):
                return JsonResponse({'success': False, 'message': 'Invalid cart item quantity.'}, status=400)
            if qty <= 0 or qty > 99:
                return JsonResponse({'success': False, 'message': 'Invalid cart item quantity.'}, status=400)

            item_id = item.get('id')
            item_name = str(item.get('name', '')).strip()
            menu_item = None
            if item_id:
                menu_item = MenuItem.objects.filter(id=item_id).first()
            if menu_item is None and item_name:
                menu_item = MenuItem.objects.filter(name__iexact=item_name).first()
            if menu_item is None:
                return JsonResponse({
                    'success': False,
                    'message': f'"{item_name or item_id}" is no longer on the menu. Please refresh and try again.'
                }, status=400)

            if menu_item.id in lines:
                lines[menu_item.id]['qty'] += qty
            else:
                lines[menu_item.id] = {'menu_item': menu_item, 'qty': qty}

        subtotal = round(sum(
            float(line['menu_item'].price) * line['qty']
            for line in lines.values()
        ), 2)
        if subtotal <= 0 or subtotal > 99999999.99:
            return JsonResponse({'success': False, 'message': 'Invalid cart total.'}, status=400)

        # Campus-only scope: validate the delivery destination BEFORE creating
        # anything, same as before.
        if is_delivery:
            from deliveries.utils import is_within_campus
            from django.conf import settings
            enforce_geofence = getattr(settings, 'ENFORCE_GEOFENCE', True)
            if enforce_geofence and not is_within_campus(data.get('dest_lat'), data.get('dest_lng')):
                return JsonResponse({
                    'success': False,
                    'message': 'Delivery is only available within the Palawan State University campus. Please make sure your location is inside the campus and try again.'
                }, status=422)

        from deliveries.utils import delivery_fee_for_order
        delivery_fee = delivery_fee_for_order(subtotal) if is_delivery else 0.0

        # ===== Loyalty points ================================================
        # Redeemed points discount the payable and are deducted AT CHECKOUT
        # (atomically). Earned points are only credited once the order reaches
        # 'completed' (see credit_points_for_order). Cancelling before then
        # refunds the redeemed points via refund_points_for_order.
        points_earned = round(subtotal / 100.0, 2)
        try:
            points_redeemed = float(data.get('points_redeemed', 0) or 0)
        except (TypeError, ValueError):
            points_redeemed = 0.0
        if not user:
            points_redeemed = 0.0
        elif points_redeemed < 0:
            return JsonResponse({'success': False, 'message': 'Invalid loyalty points.'}, status=400)
        elif points_redeemed > float(user.loyalty_points or 0):
            return JsonResponse({'success': False, 'message': 'Insufficient loyalty points.'}, status=400)
        else:
            points_redeemed = min(points_redeemed, subtotal)
        total_amount = round(subtotal - points_redeemed, 2)

        initial_status = 'pending' if is_delivery else 'unpaid'

        # Guest delivery contact info (optional) so riders can reach a guest.
        guest_name = str(data.get('guest_name', '') or '').strip()[:150]
        guest_phone = str(data.get('guest_phone', '') or '').strip()[:30]

        def _create_order_with_unique_number(**order_kwargs):
            """Create the Order with a collision-proof random order number.

            The UNIQUE column can race between check & insert (~1/9000 per
            pair), so we retry on IntegrityError instead of surfacing a 500.
            """
            for _ in range(50):
                candidate = f"#CE-{random.randint(1000, 9999)}"
                try:
                    # Nested atomic = savepoint: an IntegrityError here only
                    # rolls back this attempt, never the outer transaction.
                    with transaction.atomic():
                        return Order.objects.create(order_number=candidate, **order_kwargs)
                except IntegrityError:
                    continue
            raise CheckoutError('Could not allocate a unique order number. Please try again.')

        # Wrap the whole order pipeline in a transaction so a failure anywhere
        # rolls back everything: no orphaned Order, no spent points, no stock
        # deducted for an order that never made it.
        with transaction.atomic():
            order = _create_order_with_unique_number(
                total_amount=total_amount,
                delivery_fee=delivery_fee,
                status=initial_status,
                customer=user,
                points_earned=points_earned,
                points_redeemed=points_redeemed,
                guest_name=guest_name or None,
                guest_phone=guest_phone or None,
            )

            # Spend redeemed points atomically. The conditional filter keeps the
            # balance from ever going negative even under a double-spend race.
            if user and points_redeemed > 0:
                from accounts.models import CustomUser
                spent = CustomUser.objects.filter(
                    pk=user.pk, loyalty_points__gte=points_redeemed
                ).update(loyalty_points=F('loyalty_points') - Decimal(str(points_redeemed)))
                if not spent:
                    raise CheckoutError('Insufficient loyalty points.')

            # Deduct stock row-by-row under an exclusive lock so two concurrent
            # checkouts can never oversell the same item.
            for line in lines.values():
                menu = MenuItem.objects.select_for_update().get(pk=line['menu_item'].pk)
                qty = line['qty']
                if menu.stock is not None and menu.stock < qty:
                    raise CheckoutError(
                        f'Sorry, only {menu.stock} left for "{menu.name}". '
                        'Please reduce the quantity.'
                    )
                if menu.stock is not None:
                    menu.stock -= qty
                    if menu.stock <= 0:
                        menu.is_available = False
                        menu.save(update_fields=['stock', 'is_available'])
                    else:
                        menu.save(update_fields=['stock'])

            # Stock changed -> the kiosk's cached menu (60s TTL) must refresh now.
            cache.delete('formatted_menu_active_kiosk')

            from queuing.models import DigitalQueueSlip
            try:
                DigitalQueueSlip.objects.get_or_create(
                    order=order,
                    defaults={'queue_number': order.order_number}
                )
            except Exception:
                pass

            for menu_item_id, line in lines.items():
                menu = line['menu_item']
                OrderItem.objects.create(
                    order=order,
                    item_name=menu.name,
                    price=float(menu.price),
                    quantity=line['qty'],
                )

            if is_delivery:
                from deliveries.models import DeliveryRequest
                dest_lat = data.get('dest_lat')
                dest_lng = data.get('dest_lng')
                delivery_req = DeliveryRequest.objects.create(
                    order=order,
                    delivery_location=delivery_location,
                    status=DeliveryRequest.RequestStatus.SEARCHING,
                    assigned_to=None,
                    assigned_at=None,
                    dest_lat=dest_lat,
                    dest_lng=dest_lng,
                )

        new_points = 0.0
        if user:
            user.refresh_from_db()
            new_points = float(user.loyalty_points or 0)

        return JsonResponse({
            'success': True,
            'order_number': order.order_number,
            'order_id': order.id,
            'is_delivery': is_delivery,
            'delivery_id': delivery_req.id if is_delivery else None,
            'delivery_fee': float(order.delivery_fee),
            'total_payment': float(order.total_payment),
            'points_earned': points_earned,
            'points_redeemed': points_redeemed,
            'new_points': new_points,
            'expires_at': slip_expires_at(order),
            'expiry_hours': KIOSK_SLIP_EXPIRY_HOURS,
        })

    except CheckoutError as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


# ===== Loyalty + stock life-cycle helpers shared by every app =====
def credit_points_for_order(order):
    """Grant an order's earned loyalty points once it is COMPLETED.

    Called from every place that marks an order 'completed' (rider handoff and
    the counter board). Guards on status so a double-complete never double
    credits.
    """
    if not order or order.status != 'completed' or not order.customer_id:
        return
    if order.points_earned and order.points_earned > 0:
        from accounts.models import CustomUser
        CustomUser.objects.filter(pk=order.customer_id).update(
            loyalty_points=F('loyalty_points') + Decimal(str(order.points_earned))
        )


def refund_points_for_cancel(order):
    """Return redeemed loyalty points when an order is cancelled after paying
    with points (they were only ever deducted at checkout)."""
    if not order or not order.customer_id:
        return
    if order.points_redeemed and order.points_redeemed > 0:
        from accounts.models import CustomUser
        CustomUser.objects.filter(pk=order.customer_id).update(
            loyalty_points=F('loyalty_points') + Decimal(str(order.points_redeemed))
        )


def restore_stock_for_order(order):
    """Return deducted stock to the menu when an order is cancelled before the
    food was made. Items are matched back by name so cancelled orders never
    leak inventory. Callers must only invoke this on a true cancel transition.
    """
    if not order:
        return
    matched_ids = []
    for oi in order.items.all():
        menu = MenuItem.objects.filter(name__iexact=oi.item_name).first()
        qty = oi.quantity or 0
        if menu and qty:
            menu.stock = (menu.stock or 0) + qty
            if menu.stock > 0:
                menu.is_available = True
            menu.save(update_fields=['stock', 'is_available'])
            matched_ids.append(menu.id)
    if matched_ids:
        cache.delete('formatted_menu_active_kiosk')

# How long an unpaid kiosk queue slip stays valid before it is auto-cancelled.
# Mirrors a real canteen ticket window: walk up, pay, or the slip lapses.
KIOSK_SLIP_EXPIRY_HOURS = 1

_KIOSK_EXPIRY_SWEEP_KEY = 'kiosk_unpaid_expiry_sweep'
_KIOSK_EXPIRY_SWEEP_TTL = 60

from datetime import timedelta


def slip_expires_at(order):
    """ISO timestamp when an unpaid slip lapses, or None once paid/cancelled."""
    if order.status != 'unpaid':
        return None
    from datetime import timedelta
    return timezone.localtime(order.created_at + timedelta(hours=KIOSK_SLIP_EXPIRY_HOURS)).isoformat()


def expire_stale_unpaid_orders():
    """Lazily auto-cancel pickup slips never paid within the expiry window.

    Runs from inside request handlers (kiosk status poll, counter scan, order
    history) instead of a cron job: this project has no worker process, so the
    sweep piggybacks on the read traffic the slip itself generates. A short
    cache lock keeps several kiosks on the same counter from sweeping twice in
    the same minute. Cancelling restores stock and refunds redeemed points, and
    records the cancellation in the staff Activity Log.
    """
    if not cache.add(_KIOSK_EXPIRY_SWEEP_KEY, '1', _KIOSK_EXPIRY_SWEEP_TTL):
        return 0
    try:
        cutoff = timezone.now() - timedelta(hours=KIOSK_SLIP_EXPIRY_HOURS)
        stale_ids = list(
            Order.objects.filter(status='unpaid', created_at__lt=cutoff)
            .order_by('created_at')
            .values_list('id', flat=True)[:200]
        )
        count = 0
        for oid in stale_ids:
            with transaction.atomic():
                order = Order.objects.select_for_update() \
                    .filter(pk=oid, status='unpaid').first()
                if not order:
                    continue
                order.status = 'cancelled'
                order.save(update_fields=['status'])
                try:
                    refund_points_for_cancel(order)
                    restore_stock_for_order(order)
                except Exception:
                    pass
                from activity_log.models import ActivityLog
                from activity_log.services import log_activity
                log_activity(
                    None,
                    action=f"Auto-cancelled expired queue slip {order.order_number} "
                           f"(P{float(order.total_amount):.2f})",
                    category=ActivityLog.Category.ORDER,
                    level=ActivityLog.Level.WARNING,
                    target=order.order_number,
                    is_guest=order.customer_id is None,
                    metadata={
                        'order_id': order.id,
                        'expiry_hours': KIOSK_SLIP_EXPIRY_HOURS,
                    },
                )
                count += 1
        return count
    finally:
        cache.delete(_KIOSK_EXPIRY_SWEEP_KEY)


def find_order_by_number(raw):
    """Look an order up by slip number, tolerating every spelling in use.

    Stored numbers keep the hash prefix (``#CE-5151``) but callers send any of
    ``#CE-5151``, ``CE-5151``, ``5151`` or ``Order #CE-5151`` scraped out of the
    UI. Normalising to one canonical set of candidates is what keeps the status
    poll, the barcode scan and the rating form from disagreeing about whether an
    order exists.
    """
    from django.db.models import Q

    raw = str(raw or '').strip()
    # Pull a bare slip number out of a longer label such as
    # "Order Details & Live Tracking (#CE-5151)".
    import re
    match = re.search(r'#?\s*CE-?\s*(\d+)', raw, re.IGNORECASE)
    digits = match.group(1) if match else None
    if digits is None:
        digits = re.sub(r'[^0-9]', '', raw) or None

    numbers = {raw}
    if digits:
        numbers.update({f'#CE-{digits}', f'CE-{digits}', digits})

    query = Q()
    for n in numbers:
        if n:
            query |= Q(order_number__iexact=n)
    return Order.objects.filter(query).first()


def check_order_status_api(request, order_num):
    # Lazy sweep so an abandoned slip reads as cancelled in the history panel.
    expire_stale_unpaid_orders()
    order = find_order_by_number(order_num)
    if order is None:
        return JsonResponse({'exists': False})
    return JsonResponse({
        'exists': True,
        'status': order.status,
        'expires_at': slip_expires_at(order),
        'expired': order.status == 'cancelled',
        'expiry_hours': KIOSK_SLIP_EXPIRY_HOURS,
    })


def _feedback_gate(order):
    """Decide whether an order is rateable, and say why not when it isn't.

    Returns ``(ok, reason)``. A delivery is rateable once the rider has marked it
    DELIVERED *and* attached a proof-of-delivery photo, which is the moment the
    e-receipt becomes final. A counter pickup has no rider, so the order's own
    completed status is the whole gate.
    """
    from deliveries.models import DeliveryRequest

    delivery = DeliveryRequest.objects.filter(order=order).select_related().first()
    if delivery is None:
        if order.status != 'completed':
            return False, 'Rating is only available after the order has been completed.'
        return True, ''

    if delivery.status != DeliveryRequest.RequestStatus.DELIVERED:
        return False, 'Rating opens once the rider marks this delivery as delivered.'
    if not delivery.proof_photo:
        return False, 'Rating opens once the rider attaches the proof-of-delivery photo.'
    return True, ''


@require_POST
def submit_feedback_api(request):
    try:
        data = json.loads(request.body)
        order_number = data.get('order_number')
        rating = int(data.get('rating', 5))
        comment = data.get('comment', '')

        order = find_order_by_number(order_number) if order_number else None
        if order is None:
            return JsonResponse(
                {'success': False, 'message': 'Order not found. Check the order number and try again.'},
                status=404)

        customer = request.user if request.user.is_authenticated else None

        # Only the account that placed the order may rate it. Otherwise any
        # signed-in user could tank an order's score by posting a 1-star against
        # a slip number they guessed or read off someone else's screen.
        if order.customer_id is not None and customer is not None and order.customer_id != customer.pk:
            return JsonResponse(
                {'success': False, 'message': 'You can only rate your own order.'},
                status=403)
        if order.customer_id is not None and customer is None:
            return JsonResponse(
                {'success': False, 'message': 'Please log in to rate this order.'},
                status=403)

        ok, reason = _feedback_gate(order)
        if not ok:
            return JsonResponse({'success': False, 'message': reason}, status=400)

        from .models import OrderFeedback

        # Ratings are one-per-customer-per-order: submitting again updates the
        # original instead of stacking on a pile of duplicates (which could
        # otherwise tank an order's score with 1-star spam).
        rating = max(1, min(5, int(rating or 5)))
        comment = str(comment or '')[:2000]

        if customer is not None:
            feedback = OrderFeedback.objects.filter(order=order, customer=customer).first()
        else:
            feedback = OrderFeedback.objects.filter(order=order, customer__isnull=True).first()

        if feedback:
            feedback.rating = rating
            feedback.comment = comment
            feedback.save(update_fields=['rating', 'comment'])
        else:
            OrderFeedback.objects.create(
                order=order,
                customer=customer,
                rating=rating,
                comment=comment
            )
        return JsonResponse({'success': True, 'message': 'Feedback submitted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

from django.shortcuts import render

def kiosk_menu_view(request):
    # Sinusuri kung faculty/staff (puwedeng delivery) o student (dine-in / pickup lang)
    can_deliver = request.session.get('can_deliver', False)

    # Kung ang user ay ganap na naka-login bilang Staff/Superuser
    if request.user.is_authenticated:
        can_deliver = True

    context = {
        'can_deliver': can_deliver,
    }
    return render(request, 'customer_portal/kiosk_menu.html', context)
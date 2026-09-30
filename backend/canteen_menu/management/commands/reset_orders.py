from django.core.management.base import BaseCommand
from customer_portal.models import Order, OrderItem, OrderFeedback
from deliveries.models import DeliveryRequest, DeliveryMessage, RiderLocationPoint

class Command(BaseCommand):
    help = 'Resets all orders, order items, feedback/ratings, and delivery records while keeping accounts and menu management intact.'

    def handle(self, *args, **options):
        self.stdout.write('Resetting orders, feedback, and delivery records...')
        
        # Delete delivery related records first
        msg_count, _ = DeliveryMessage.objects.all().delete()
        loc_count, _ = RiderLocationPoint.objects.all().delete()
        del_count, _ = DeliveryRequest.objects.all().delete()
        
        # Delete feedback
        fb_count, _ = OrderFeedback.objects.all().delete()
        
        # Delete order items and orders
        item_count, _ = OrderItem.objects.all().delete()
        order_count, _ = Order.objects.all().delete()
        
        self.stdout.write(self.style.SUCCESS(
            f'Successfully reset:\n'
            f' - {order_count} Orders\n'
            f' - {item_count} Order Items\n'
            f' - {fb_count} Feedback/Ratings\n'
            f' - {del_count} Delivery Requests\n'
            f' - {msg_count} Delivery Messages\n'
            f' - {loc_count} Rider Location Points\n'
            f'Accounts and Menu Management were preserved.'
        ))

from django.core.management.base import BaseCommand
from accounts.models import CustomUser
from customer_portal.models import Order, OrderItem, OrderFeedback
from deliveries.models import DeliveryRequest, DeliveryMessage, RiderLocationPoint
from activity_log.models import ActivityLog

class Command(BaseCommand):
    help = 'Resets all orders, order items, feedback/ratings, delivery records, activity logs, and user loyalty points while keeping accounts and menu management intact.'

    def handle(self, *args, **options):
        self.stdout.write('Resetting orders, feedback, delivery records, activity logs, and loyalty points...')
        
        # Delete delivery related records first
        msg_count, _ = DeliveryMessage.objects.all().delete()
        loc_count, _ = RiderLocationPoint.objects.all().delete()
        del_count, _ = DeliveryRequest.objects.all().delete()
        
        # Delete feedback
        fb_count, _ = OrderFeedback.objects.all().delete()
        
        # Delete order items and orders
        item_count, _ = OrderItem.objects.all().delete()
        order_count, _ = Order.objects.all().delete()

        # Delete activity logs
        log_count, _ = ActivityLog.objects.all().delete()

        # Reset loyalty points for all users
        users_count = CustomUser.objects.count()
        CustomUser.objects.all().update(loyalty_points=0.00)
        
        self.stdout.write(self.style.SUCCESS(
            f'Successfully reset:\n'
            f' - {order_count} Orders\n'
            f' - {item_count} Order Items\n'
            f' - {fb_count} Feedback/Ratings\n'
            f' - {del_count} Delivery Requests\n'
            f' - {msg_count} Delivery Messages\n'
            f' - {loc_count} Rider Location Points\n'
            f' - {log_count} Activity Log Entries\n'
            f' - Reset loyalty points to 0.00 for {users_count} users\n'
            f'Accounts and Menu Management were preserved.'
        ))

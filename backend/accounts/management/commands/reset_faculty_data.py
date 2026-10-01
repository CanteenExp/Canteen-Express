from django.core.management.base import BaseCommand
from accounts.models import CustomUser
from customer_portal.models import Order
from order_management.models import Order as OrderMgmt
from activity_log.models import ActivityLog

class Command(BaseCommand):
    help = 'Resets all orders and loyalty points of faculty users, and clears the activity log.'

    def handle(self, *args, **options):
        self.stdout.write('Resetting faculty orders, faculty loyalty points, and activity logs...')

        # 1. Delete faculty orders (customer_portal.models.Order where customer__role='FACULTY')
        faculty_orders = Order.objects.filter(customer__role='FACULTY')
        order_count = faculty_orders.count()
        faculty_orders.delete()

        # Also delete order_management orders if any
        mgmt_faculty_orders = OrderMgmt.objects.filter(customer__role='FACULTY')
        mgmt_count = mgmt_faculty_orders.count()
        mgmt_faculty_orders.delete()

        # 2. Reset faculty points
        faculty_users = CustomUser.objects.filter(role='FACULTY')
        users_count = faculty_users.count()
        faculty_users.update(loyalty_points=0.00)

        # 3. Clear activity log
        log_count, _ = ActivityLog.objects.all().delete()

        self.stdout.write(self.style.SUCCESS(
            f'Successfully reset:\n'
            f' - {order_count} Faculty Portal Orders (and associated items, feedback, deliveries)\n'
            f' - {mgmt_count} Order Management Faculty Orders\n'
            f' - Reset loyalty points to 0.00 for {users_count} Faculty users\n'
            f' - Cleared {log_count} Activity Log entries'
        ))

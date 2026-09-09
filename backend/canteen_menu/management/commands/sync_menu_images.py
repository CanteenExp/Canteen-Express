from django.core.management.base import BaseCommand
from canteen_menu.models import MenuItem
from canteen_menu.views import _auto_sync_menu_image

class Command(BaseCommand):
    help = 'Syncs all menu items with images matching their names from media/menu_items and local folders, saving them to the database.'

    def handle(self, *args, **options):
        items = MenuItem.objects.all()
        count = items.count()
        self.stdout.write(f"Syncing images for {count} menu items...")
        for item in items:
            _auto_sync_menu_image(item)
            self.stdout.write(f" - Synced: {item.name} -> image: {item.image}, image_url: {item.image_url}")
        self.stdout.write(self.style.SUCCESS(f"Successfully synced and saved {count} menu items to the database!"))

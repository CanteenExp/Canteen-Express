from django.core.management.base import BaseCommand
from canteen_menu.models import MenuItem
from canteen_menu.views import _generate_auto_desc

class Command(BaseCommand):
    help = 'Updates all menu items with precise descriptions based on their names and categories.'

    def handle(self, *args, **options):
        items = MenuItem.objects.all()
        count = items.count()
        self.stdout.write(f"Updating descriptions for {count} menu items...")
        for item in items:
            old_desc = item.description
            cat_name = str(item.category) if item.category else ''
            new_desc = _generate_auto_desc(item.name, cat_name)
            item.description = new_desc
            item.save()
            self.stdout.write(f" - Updated '{item.name}': {new_desc}")
        self.stdout.write(self.style.SUCCESS(f"Successfully updated descriptions for {count} menu items!"))

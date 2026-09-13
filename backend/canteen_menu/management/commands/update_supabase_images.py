import os
import urllib.parse
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.text import slugify
from canteen_menu.models import MenuItem

class Command(BaseCommand):
    help = 'Updates all MenuItem image_urls to point to Supabase Storage public URLs.'

    def handle(self, *args, **options):
        supabase_project_ref = "hchqdkuijbpihraagetz"
        bucket_name = "menu-images"
        base_supabase_url = f"https://{supabase_project_ref}.supabase.co/storage/v1/object/public/{bucket_name}"

        items = MenuItem.objects.all()
        count = items.count()
        self.stdout.write(f"Updating image URLs for {count} menu items to Supabase Storage...")

        media_menu_dir = os.path.join(settings.MEDIA_ROOT, 'menu_items')
        extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']

        updated_count = 0
        for item in items:
            slug_name = slugify(item.name)
            clean_name = item.name.lower().replace(' ', '_').replace('-', '_')
            no_space_name = item.name.lower().replace(' ', '')
            raw_name = item.name.lower()

            candidates = [slug_name, clean_name, no_space_name, raw_name, item.name]
            found_filename = None

            # Check if item already has a valid image file or check local files
            if item.image:
                img_name = str(item.image)
                if img_name.startswith('menu_items/'):
                    found_filename = img_name.replace('menu_items/', '')

            if not found_filename and os.path.exists(media_menu_dir):
                for cand in candidates:
                    for ext in extensions:
                        fname = f"{cand}{ext}"
                        if os.path.exists(os.path.join(media_menu_dir, fname)):
                            found_filename = fname
                            break
                    if found_filename:
                        break

            # If still not found, check with exact item name variants
            if not found_filename and os.path.exists(media_menu_dir):
                for fname in os.listdir(media_menu_dir):
                    base_fname = os.path.splitext(fname)[0].lower()
                    if base_fname in [c.lower() for c in candidates]:
                        found_filename = fname
                        break

            if found_filename:
                encoded_filename = urllib.parse.quote(found_filename)
                item.image_url = f"{base_supabase_url}/{encoded_filename}"
                item.image = None  # Clear local image field so it uses image_url
                item.save()
                updated_count += 1
                self.stdout.write(f" - Updated {item.name} -> {item.image_url}")
            else:
                self.stdout.write(self.style.WARNING(f" - No image file found for {item.name}"))

        self.stdout.write(self.style.SUCCESS(f"Successfully updated {updated_count} out of {count} menu items to Supabase Storage URLs!"))

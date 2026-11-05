"""Repoint MenuItem.image_url to the live Supabase Storage bucket.

Background: the menu photos used to live on a Supabase project that is now
restricted (HTTP 402, "exceed_egress_quota"), and the URLs on the live project
were written with the wrong letter case. Supabase Storage object keys are
case-sensitive, so ``turon.jpg`` 400s while ``Turon.jpg`` works.

This command rebuilds every URL from the *actual* filenames in
``MEDIA_ROOT/menu_items`` (local disk keeps the original casing), so the stored
URL matches the object that really exists in the bucket.

Usage::

    python manage.py fix_menu_images             # dry run, prints the diff
    python manage.py fix_menu_images --apply     # writes image_url + clears cache
    python manage.py fix_menu_images --verify    # HTTP-checks every image_url
"""

import os
import re
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand

from canteen_menu.models import MenuItem

PROJECT_REF = "msnznjncchahndkiaqqu"  # live project; NOT the restricted hchqdkuijbpihraagetz
BUCKET = "menu-images"
BASE_URL = f"https://{PROJECT_REF}.supabase.co/storage/v1/object/public/{BUCKET}"

# Items whose display name does not normalise to their photo's filename.
ALIASES = {
    "porksilog with egg": "Pork-Silog.jpeg",
    "bento meal (a)": "ChatGPT_Image_Aug_17_2026_05_47_56_PM.png",
    "bento meal (b)": "Gemini_Generated_Image_dh660bdh660bdh66.jpg",
    "plain rice": "K_A_N_I_N_--_Rice_a_Filipino_Stape.jpg",
}

# Local files that are NOT in the live bucket. Writing their URL would just
# replace one dead link with another, so they are reported and skipped.
MANUAL_UPLOAD = {"kutsinta"}


def _norm(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _status(url, timeout=15):
    """Return the HTTP status for ``url``, or a string like ``TimeoutError``."""
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception as exc:  # noqa: BLE001 - report, never crash the command
        return type(exc).__name__


class Command(BaseCommand):
    help = "Repoint MenuItem.image_url to the live Supabase bucket using exact media filenames."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the changes (default is a dry run).",
        )
        parser.add_argument(
            "--verify",
            action="store_true",
            help="HTTP-check every image_url (needs network access).",
        )
        parser.add_argument(
            "--no-check",
            action="store_true",
            help="Rewrite without probing the current URL first (faster, less safe).",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="With --verify, exit 1 when any image URL is broken (use in CI/cron).",
        )

    def handle(self, *args, **options):
        media_dir = os.path.join(settings.MEDIA_ROOT, "menu_items")
        if not os.path.isdir(media_dir):
            self.stderr.write(self.style.ERROR(f"Media folder not found: {media_dir}"))
            return

        by_name = {}
        for filename in sorted(os.listdir(media_dir)):
            by_name.setdefault(_norm(os.path.splitext(filename)[0]), filename)

        changed = 0
        unchanged = 0
        kept = 0
        skipped = []

        for item in MenuItem.objects.all().order_by("name"):
            key = item.name.strip().lower()
            filename = ALIASES.get(key) or by_name.get(_norm(item.name))

            if not filename:
                skipped.append((item.name, "walang local file"))
                continue
            if _norm(key) in MANUAL_UPLOAD:
                skipped.append((item.name, "wala sa bucket, kailangan ng manual upload"))
                continue

            new_url = f"{BASE_URL}/{urllib.parse.quote(filename, safe='')}"
            if item.image_url == new_url:
                unchanged += 1
                continue

            # Never touch a photo that already loads: the local folder keeps
            # duplicate names for the same picture, so rewriting a live URL can
            # only add risk without fixing anything.
            if not options["no_check"] and item.image_url and _status(item.image_url) == 200:
                kept += 1
                self.stdout.write(f"KEEP  {item.name}: {item.image_url}")
                continue

            changed += 1
            self.stdout.write(f"{item.name}\n    - {item.image_url}\n    + {new_url}")

            if options["apply"]:
                item.image_url = new_url
                item.image = None
                item.save(update_fields=["image_url", "image"])

        for name, reason in skipped:
            self.stdout.write(self.style.WARNING(f"SKIP  {name}: {reason}"))

        if options["apply"]:
            cache.delete("formatted_menu_active_kiosk")
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nUpdated {changed} item(s), {unchanged} already correct, "
                    f"{kept} kept (already loading), {len(skipped)} skipped. "
                    "Menu cache cleared."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"\nDry run: {changed} item(s) would change, {unchanged} already correct, "
                    f"{kept} kept (already loading), {len(skipped)} skipped. "
                    "Re-run with --apply to write."
                )
            )

        if options["verify"]:
            broken = self._verify()
            if options["strict"] and broken:
                raise SystemExit(1)

    def _verify(self):
        total = MenuItem.objects.count()
        bad = 0

        self.stdout.write("\nChecking image URLs...")
        for item in MenuItem.objects.all().order_by("name"):
            if not item.image_url:
                bad += 1
                self.stdout.write(self.style.ERROR(f" - {item.name}: no URL"))
                continue

            status = _status(item.image_url, timeout=20)
            if status != 200:
                bad += 1
                self.stdout.write(self.style.ERROR(f" - {item.name}: {status}  {item.image_url}"))

        summary = f"OK: {total - bad} / {total}"
        style = self.style.SUCCESS if bad == 0 else self.style.WARNING
        self.stdout.write(style(summary))
        return bad

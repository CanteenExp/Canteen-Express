import os
import json
import re
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.serializers import deserialize
from django.db import transaction

print("Reading backup_data.json...")
with open('backup_data.json', encoding='utf-16', errors='ignore') as f:
    content = f.read()

# Find all blocks starting with {"model"
matches = re.findall(r'(\{\s*"model"\s*:\s*".*?\})', content, re.DOTALL)
print(f"Found {len(matches)} serialized model blocks in backup_data.json.")

success = 0
skipped = 0
with transaction.atomic():
    for match in matches:
        try:
            json_item = f"[{match}]"
            for obj in deserialize('json', json_item):
                obj.save()
                success += 1
        except Exception as e:
            skipped += 1

print(f"Successfully restored {success} objects from backup_data.json (Skipped duplicates/errors: {skipped})!")

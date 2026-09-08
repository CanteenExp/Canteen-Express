import os
import json
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.serializers import deserialize

print("Restoring backup_data.json object by object...")
with open('backup_data.json', encoding='utf-16', errors='ignore') as f:
    content = f.read()

idx = content.find('[')
json_str = content[idx:]
last_bracket = json_str.rfind(']')
if last_bracket != -1:
    json_str = json_str[:last_bracket+1]

count = 0
for des_obj in deserialize('json', json_str):
    try:
        des_obj.save()
        count += 1
    except Exception as e:
        pass

print(f"Successfully restored {count} records from backup_data.json into Supabase!")

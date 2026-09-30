from django.utils import timezone
import os

def is_operating_hours():
    """
    Returns True if operating hours are met (Monday-Friday, 8:00 AM to 5:00 PM)
    or if ENFORCE_OPERATING_HOURS is not set to 'true' in .env.
    Canteen Staff and Admin roles are exempt and operate 24/7.
    """
    if os.getenv('ENFORCE_OPERATING_HOURS', 'False').lower() != 'true':
        return True
    now = timezone.localtime()
    # Monday = 0, Friday = 4
    if now.weekday() > 4:
        return False
    # 8:00 AM to 5:00 PM (8 to 17)
    if not (8 <= now.hour < 17):
        return False
    return True

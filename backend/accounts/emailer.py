import json
import os

from django.conf import settings


class EmailSendError(Exception):
    pass


def send_code_email(subject, message, to_email):
    api_key = os.getenv('EMAIL_API_KEY', '')
    if api_key:
        return _send_via_https_api(subject, message, to_email, api_key)
    from django.core.mail import send_mail
    return send_mail(
        subject=subject,
        message=message,
        from_email=None,
        recipient_list=[to_email],
        fail_silently=False,
    )


def _send_via_https_api(subject, message, to_email, api_key):
    from_addr = os.getenv('EMAIL_FROM', '') or 'Canteen Express <onboarding@resend.dev>'
    payload = json.dumps({
        'from': from_addr,
        'to': [to_email],
        'subject': subject,
        'text': message,
    }).encode('utf-8')
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    req = Request(
        'https://api.resend.com/emails',
        data=payload,
        headers={
            'Authorization': 'Bearer ' + api_key,
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    timeout = int(getattr(settings, 'EMAIL_TIMEOUT', 10) or 10)
    try:
        with urlopen(req, timeout=timeout) as resp:
            resp.read()
        return 1
    except HTTPError as e:
        raise EmailSendError('Email API HTTP {}: {}'.format(e.code, e.read().decode('utf-8', 'replace')))
import json
import os

from django.conf import settings


class EmailSendError(Exception):
    pass


def send_code_email(subject, message, to_email):
    sendgrid_key = os.getenv('SENDGRID_API_KEY', '')
    if sendgrid_key:
        _post_json(
            'https://api.sendgrid.com/v3/mail/send',
            {
                'from': _sendgrid_from(),
                'personalizations': [{'to': [{'email': to_email}]}],
                'subject': subject,
                'content': [{'type': 'text/plain', 'value': message}],
            },
            {'Authorization': 'Bearer ' + sendgrid_key},
        )
        return 1
    from django.core.mail import send_mail
    return send_mail(
        subject=subject,
        message=message,
        from_email=None,
        recipient_list=[to_email],
        fail_silently=False,
    )


def _sendgrid_from():
    raw = (os.getenv('EMAIL_FROM', '') or 'Canteen Express <canteenexpress26@gmail.com>').strip()
    if '<' in raw and raw.rstrip().endswith('>'):
        name = raw.split('<')[0].strip()
        email = raw.split('<')[1].rstrip('>').strip()
        return {'email': email, 'name': name} if name else {'email': email}
    return {'email': raw}


def _post_json(url, payload, headers):
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError
    data = json.dumps(payload).encode('utf-8')
    req = Request(
        url,
        data=data,
        headers=dict(headers, **{'Content-Type': 'application/json'}),
        method='POST',
    )
    timeout = int(getattr(settings, 'EMAIL_TIMEOUT', 10) or 10)
    try:
        with urlopen(req, timeout=timeout) as resp:
            resp.read()
    except HTTPError as e:
        raise EmailSendError('Email API HTTP {}: {}'.format(e.code, e.read().decode('utf-8', 'replace')))
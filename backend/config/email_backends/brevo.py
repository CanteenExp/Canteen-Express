"""Brevo (formerly Sendinblue) email backend -- HTTPS on port 443.

Why this exists
---------------
Render's free web-service plan, and Railway's Free/Hobby/Trial plans, BLOCK
outbound TCP on ports 25/465/587. A Django SMTP backend there fails with
``OSError: [Errno 101] Network is unreachable`` no matter how the credentials
are configured, so faculty OTP delivery (signup and password reset) is
impossible over SMTP.

HTTPS to an email provider's REST API rides on port 443, which those plans
allow. This backend is therefore selected automatically as soon as
``BREVO_API_KEY`` is present in the environment:

    EMAIL_BACKEND=config.email_backends.brevo.BrevoBackend
    BREVO_API_KEY=xkeysib-...

With no key set nothing changes and Django keeps using SMTP, so local
development is unaffected.

Brevo's free tier allows 300 emails/day, which is far more than a canteen's
OTP volume. The sender address must be a verified sender in the Brevo console.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

BREVO_API_URL = 'https://api.brevo.com/v3/smtp/email'

# Guard rail in case a caller passes a huge body. The API itself allows 50 MB.
_MAX_BYTES = 5 * 1024 * 1024


class BrevoBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        api_key = (getattr(settings, 'BREVO_API_KEY', '') or '').strip()
        if not api_key:
            # Misconfiguration, not a transient error: fail loudly in the log
            # rather than silently dropping every OTP.
            raise RuntimeError(
                'BREVO_API_KEY is not set but the Brevo backend is selected. '
                'Set BREVO_API_KEY, or switch EMAIL_BACKEND back to the SMTP backend.'
            )

        sent = 0
        for message in email_messages:
            try:
                self._send_one(api_key, message)
                sent += 1
            except Exception as exc:
                # One bad recipient must not abort the whole batch, and must
                # surface as a non-zero count so the caller sees a failure.
                self.connection and self.connection.send(
                    'Brevo send failed: %s: %s' % (type(exc).__name__, exc))
        return sent

    def _send_one(self, api_key, message):
        payload = {
            'sender': {
                # Brevo rejects a sender that is not a verified address, so the
                # from-address is taken from the message and normalised to a
                # bare email (the display name is carried separately).
                'email': self._bare_address(message.from_email or settings.DEFAULT_FROM_EMAIL),
                'name': (getattr(settings, 'BREVO_SENDER_NAME', None)
                         or 'Canteen Express'),
            },
            'to': [{'email': address} for address in message.to],
            'subject': message.subject or '',
            'textContent': message.body or '',
        }
        html_body = getattr(message, 'alternatives', None)
        if html_body:
            for content, mimetype in html_body:
                if mimetype == 'text/html':
                    payload['htmlContent'] = content
                    break

        body = json.dumps(payload).encode('utf-8')
        if len(body) > _MAX_BYTES:
            raise ValueError('Email body exceeds the %d byte limit' % _MAX_BYTES)

        request = urllib.request.Request(
            BREVO_API_URL,
            data=body,
            method='POST',
            headers={
                'api-key': api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                # Brevo rejects requests with no user agent.
                'User-Agent': 'CanteenExpress/1.0',
            },
        )

        timeout = getattr(settings, 'EMAIL_TIMEOUT', 10)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status not in (200, 201):
                    raise RuntimeError('Brevo returned HTTP %s' % response.status)
        except urllib.error.HTTPError as exc:
            # Surface Brevo's own error body: it names the exact problem
            # (unverified sender, bad key, rate limit) instead of a bare 400.
            detail = ''
            try:
                detail = exc.read().decode('utf-8', 'replace')[:500]
            except Exception:
                pass
            raise RuntimeError('Brevo HTTP %s: %s' % (exc.code, detail)) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError('Brevo unreachable: %s' % (exc.reason,)) from exc

    @staticmethod
    def _bare_address(value):
        """Extract a bare email from a 'Name <addr@example.com>' string."""
        value = (value or '').strip()
        if '<' in value and '>' in value:
            return value[value.index('<') + 1:value.index('>')].strip()
        return value

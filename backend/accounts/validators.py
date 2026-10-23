"""Project-wide password policy.

Django's stock validators cover length, common passwords, numeric-only input
and similarity to the account. They do **not** require a mix of character
classes, which is the rule that actually stops ``canteen2026`` or
``psu!psu!psu`` from ever becoming a password here.

Every server-side path that sets a password already funnels through
``django.contrib.auth.password_validation.validate_password`` (faculty signup,
OTP password reset, in-app change password). Registering this validator in
``settings.AUTH_PASSWORD_VALIDATORS`` therefore upgrades all of them at once
without touching each view.

The browser-side mirror lives in ``static/js/password-policy.js``; keep the
two rule sets in sync: at least 8 characters containing an uppercase letter,
a lowercase letter, a number and a special character.
"""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

PASSWORD_MIN_LENGTH = 8
PASSWORD_MIN_UPPERCASE = 1
PASSWORD_MIN_LOWERCASE = 1
PASSWORD_MIN_DIGITS = 1
PASSWORD_MIN_SPECIAL = 1


def _missing_requirements(password):
    """Return the human names of the character classes the password lacks."""
    missing = []
    if not any(char.isupper() for char in password):
        missing.append(_("an uppercase letter"))
    if not any(char.islower() for char in password):
        missing.append(_("a lowercase letter"))
    if not any(char.isdigit() for char in password):
        missing.append(_("a number"))
    if all(char.isalnum() for char in password):
        missing.append(_("a special character"))
    return missing


def _join(parts):
    if len(parts) == 1:
        return parts[0]
    return _("%(head)s and %(last)s") % {
        'head': ', '.join(parts[:-1]),
        'last': parts[-1],
    }


class MixedCharacterPasswordValidator:
    """Require upper, lower, digit and special characters in every password."""

    def validate(self, password, user=None):
        missing = _missing_requirements(password or '')
        if missing:
            raise ValidationError(
                _("Password must include %(missing)s."),
                code='password_mixed_characters',
                params={'missing': _join(missing)},
            )

    def get_help_text(self):
        return _(
            "Your password must contain at least one uppercase letter, one "
            "lowercase letter, one number and one special character."
        )

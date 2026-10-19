"""Canned reasons for closing the canteen, and the text customers see.

Why a fixed list instead of free text: staff close the canteen in a hurry, and
whatever they type is what a hungry customer reads. A short menu of vetted
reasons keeps the message clear, consistent and instantly chooseable, while
`OTHER` still allows a typed one-off.

Each entry carries two separate strings:

    label    -- staff-facing, shown in the dashboard dropdown. Can be
                operations-speak ("Closed for the day -- reopens 8:00 AM").
    message  -- customer-facing, shown on the closed notice and the kiosk
                overlay. Written for someone who just wants lunch.

Adding a reason: append an entry. `code` is what gets stored, so re-wording a
label or message never breaks rows already in the database.
"""

# Reused when a reason somehow reaches the database with no text at all.
DEFAULT_MESSAGE = 'The canteen is closed right now. Please come back later.'

CLOSURE_REASONS = [
    {
        'code': 'SYSTEM_UPDATE',
        'label': 'System update / maintenance window',
        'message': ('The ordering system is being updated right now. '
                    'Please try again in a few minutes.'),
    },
    {
        'code': 'END_OF_DAY',
        'label': 'Closed for the day — reopens 8:00 AM',
        'message': ('We are closed for the day. Regular hours resume at '
                    '8:00 AM (Monday to Friday). See you then!'),
    },
    {
        'code': 'BREAK',
        'label': 'Staff break — back shortly',
        'message': ('We are on a short staff break. Ordering will resume in '
                    'a few minutes.'),
    },
    {
        'code': 'OUT_OF_STOCK',
        'label': 'Out of stock for today',
        'message': ('We have run out of ingredients for today. Sorry about '
                    'that — see you tomorrow!'),
    },
    {
        'code': 'POWER_OUTAGE',
        'label': 'Power or internet interruption',
        'message': ('We are temporarily closed because of a power or '
                    'internet interruption.'),
    },
    {
        'code': 'MAINTENANCE',
        'label': 'Cleaning / maintenance',
        'message': 'The canteen is closed for cleaning and maintenance right now.',
    },
    {
        'code': 'EVENT',
        'label': 'Campus event or holiday',
        'message': 'The canteen is closed today for a campus event or holiday.',
    },
    {
        'code': 'OTHER',
        'label': 'Other — type your own reason',
        'message': '',
    },
]

CLOSURE_REASONS_BY_CODE = {reason['code']: reason for reason in CLOSURE_REASONS}

# Codes the app itself writes that are deliberately NOT offered in the staff
# dropdown. The schedule closes the canteen on its own, and its message is
# computed from the configured window (see core_app.utils), so it needs a label
# for the dashboards but must never be pickable.
NON_SELECTABLE_LABELS = {
    'OPERATING_HOURS': 'Outside operating hours',
}

# Codes whose customer-facing text comes from the operator, not from the list.
CUSTOM_MESSAGE_CODES = {'OTHER'}


def _normalise(code):
    return str(code or '').strip().upper()


def get_reason(code):
    """The preset for `code`, or None when it is unknown/empty."""
    return CLOSURE_REASONS_BY_CODE.get(_normalise(code))


def label_for(code):
    """Staff-facing label for a stored code ('' when unknown)."""
    preset = get_reason(code)
    if preset:
        return preset['label']
    return NON_SELECTABLE_LABELS.get(_normalise(code), '')


def resolve_message(code, custom_message=''):
    """The text customers should see for this reason.

    A known preset wins so the public message stays vetted; `custom_message`
    is the fallback for `OTHER` (and for an unknown/blank code, so the older
    free-text flow keeps working).
    """
    custom_message = str(custom_message or '').strip()[:200]
    preset = get_reason(code)

    if preset and preset['code'] not in CUSTOM_MESSAGE_CODES and preset['message']:
        return preset['message']
    if custom_message:
        return custom_message
    return DEFAULT_MESSAGE

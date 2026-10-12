"""Add the schedule override mode and the closure-reason code.

`is_open` (a plain manual boolean) becomes `mode`, which can also say "follow
the timetable" -- so the canteen can run itself on 8:00 AM - 5:00 PM and have
staff only override when they want to extend or close early.

Rows already closed by hand are migrated to FORCE_CLOSED, so a canteen that was
closed at deploy time does not silently reopen because its row defaulted to
AUTO.
"""

from django.db import migrations, models


def carry_over_manual_closures(apps, schema_editor):
    SystemStatus = apps.get_model('core_app', 'SystemStatus')
    SystemStatus.objects.filter(is_open=False).update(mode='FORCE_CLOSED')


def noop(apps, schema_editor):
    """Nothing to undo: is_open is rebuilt from mode on the way back down."""


class Migration(migrations.Migration):

    dependencies = [
        ('core_app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemstatus',
            name='reason_code',
            field=models.CharField(blank=True, default='', help_text='Preset key from core_app.closure_reasons (e.g. SYSTEM_UPDATE).', max_length=32),
        ),
        migrations.AlterField(
            model_name='systemstatus',
            name='message',
            field=models.CharField(blank=True, default='', help_text='Customer-facing text. Filled in from the chosen reason preset.', max_length=200),
        ),
        migrations.AddField(
            model_name='systemstatus',
            name='mode',
            field=models.CharField(choices=[('AUTO', 'Automatic schedule (Mon-Fri, 8:00 AM - 5:00 PM)'), ('FORCE_OPEN', 'Force open (overrides the schedule)'), ('FORCE_CLOSED', 'Force closed (overrides the schedule)')], default='AUTO', help_text='AUTO follows operating hours; FORCE_OPEN / FORCE_CLOSED override the schedule until staff set it back to AUTO.', max_length=16),
        ),
        migrations.RunPython(carry_over_manual_closures, noop),
        migrations.RemoveField(
            model_name='systemstatus',
            name='is_open',
        ),
    ]

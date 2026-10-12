from django.contrib import admin

from .models import SystemStatus


@admin.register(SystemStatus)
class SystemStatusAdmin(admin.ModelAdmin):
    """Singleton, so the changelist is pointless: go straight to the row."""

    list_display = ('is_open', 'message', 'closed_at', 'reopened_at', 'updated_by', 'updated_at')
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        # Only ever one row (pk=1); it is created on first read if missing.
        return not SystemStatus.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

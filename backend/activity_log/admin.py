from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'actor_label', 'category', 'level', 'action', 'target')
    list_filter = ('category', 'level', 'is_guest', 'created_at')
    search_fields = ('action', 'target', 'actor_label')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    # Append-only from the UI too: the whole point is that the trail cannot be
    # quietly rewritten. Everything is managed through the app, not the admin.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

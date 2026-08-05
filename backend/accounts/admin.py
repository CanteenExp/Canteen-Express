from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'role', 'is_email_verified', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'is_email_verified', 'otp_code', 'otp_created_at')}),
    )

admin.site.register(CustomUser, CustomUserAdmin)
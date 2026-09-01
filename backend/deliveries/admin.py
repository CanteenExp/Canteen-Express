from django.contrib import admin
from .models import DeliveryRequest, DeliveryMessage, RiderLocationPoint


class DeliveryMessageInline(admin.TabularInline):
    model = DeliveryMessage
    extra = 0
    readonly_fields = ('timestamp',)
    can_delete = True


class RiderLocationPointInline(admin.TabularInline):
    model = RiderLocationPoint
    extra = 0
    readonly_fields = ('lat', 'lng', 'speed_kmh', 'timestamp')
    can_delete = True


@admin.register(DeliveryRequest)
class DeliveryRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'rider', 'delivery_location', 'status', 'requested_at', 'accepted_at', 'delivered_at')
    list_filter = ('status', 'requested_at')
    search_fields = ('order__order_number', 'delivery_location', 'rider__username')
    readonly_fields = ('requested_at', 'accepted_at', 'delivered_at', 'location_updated_at')
    inlines = [DeliveryMessageInline, RiderLocationPointInline]


@admin.register(RiderLocationPoint)
class RiderLocationPointAdmin(admin.ModelAdmin):
    list_display = ('delivery', 'rider', 'lat', 'lng', 'speed_kmh', 'timestamp')
    list_filter = ('timestamp',)
    readonly_fields = ('delivery', 'rider', 'lat', 'lng', 'speed_kmh', 'timestamp')


@admin.register(DeliveryMessage)
class DeliveryMessageAdmin(admin.ModelAdmin):
    list_display = ('delivery', 'sender', 'message', 'is_read', 'timestamp')
    list_filter = ('timestamp', 'is_read')
    search_fields = ('message', 'sender__username', 'delivery__order__order_number')
    readonly_fields = ('timestamp',)

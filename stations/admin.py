from django.contrib import admin
from .models import FuelStation, GeocodeCache


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = [
        'opis_truckstop_id', 'truckstop_name', 'city',
        'state', 'retail_price', 'geocode_status',
        'geocode_precision',
    ]
    list_filter = ['state', 'geocode_status', 'geocode_precision']
    search_fields = ['truckstop_name', 'city', 'address']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['state', 'city', 'truckstop_name']


@admin.register(GeocodeCache)
class GeocodeCacheAdmin(admin.ModelAdmin):
    list_display = [
        'address_key', 'latitude', 'longitude',
        'precision', 'last_used_at'
    ]
    search_fields = ['address_key']
    readonly_fields = ['created_at', 'last_used_at']
    ordering = ['-last_used_at']

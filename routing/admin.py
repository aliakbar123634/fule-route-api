
from django.contrib import admin
from .models import Station, GeocodeCache


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "city",
        "state",
        "retail_price",
    )
    list_filter = ("state", "city")
    search_fields = ("name", "city", "truckstop_id")


@admin.register(GeocodeCache)
class GeocodeCacheAdmin(admin.ModelAdmin):
    list_display = ("query", "latitude", "longitude", "created_at")
    search_fields = ("query",)

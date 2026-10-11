
from django.db import models


class Station(models.Model):
    truckstop_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, db_index=True)

    retail_price = models.DecimalField(
        max_digits=10,
        decimal_places=4,
    )

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["retail_price"]
        indexes = [
            models.Index(fields=["state", "city"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.city}, {self.state}"


class GeocodeCache(models.Model):
    query = models.CharField(max_length=500, unique=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.query

from django.contrib.gis.db import models
from django.core.validators import MinValueValidator


class FuelStation(models.Model):
    """Model representing a fuel station with location and pricing data."""

    # Geocode status choices
    GEOCODE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('fallback', 'Fallback to city-level'),
    ]

    # Geocode precision choices
    GEOCODE_PRECISION_CHOICES = [
        ('exact', 'Exact address'),
        ('street', 'Street level'),
        ('city', 'City level'),
        ('unknown', 'Unknown'),
    ]

    opis_truckstop_id = models.IntegerField(
        unique=True,
        db_index=True,
        help_text='OPIS Truckstop ID'
    )
    truckstop_name = models.CharField(
        max_length=255,
        db_index=True,
        help_text='Name of the truck stop'
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        help_text='Street address'
    )
    city = models.CharField(
        max_length=100,
        db_index=True,
        help_text='City name'
    )
    state = models.CharField(
        max_length=2,
        db_index=True,
        help_text='Two-letter state code'
    )
    rack_id = models.IntegerField(
        null=True,
        blank=True,
        help_text='Rack ID'
    )
    retail_price = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        db_index=True,
        help_text='Retail fuel price per gallon'
    )
    location = models.PointField(
        null=True,
        blank=True,
        geography=True,
        spatial_index=True,
        help_text='Geographic coordinates (PostGIS Point)'
    )
    geocode_status = models.CharField(
        max_length=20,
        choices=GEOCODE_STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text='Status of geocoding operation'
    )
    geocode_precision = models.CharField(
        max_length=20,
        choices=GEOCODE_PRECISION_CHOICES,
        default='unknown',
        db_index=True,
        help_text='Precision level of geocoded coordinates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['state', 'retail_price']),
            models.Index(fields=['geocode_status', 'geocode_precision']),
        ]
        verbose_name = 'Fuel Station'
        verbose_name_plural = 'Fuel Stations'

    def __str__(self):
        return f"{self.truckstop_name} - {self.city}, {self.state}"


class GeocodeCache(models.Model):
    """Cache for geocoding results to avoid repeated API calls."""

    address_key = models.CharField(
        max_length=500,
        unique=True,
        db_index=True,
        help_text='Normalized address key for caching'
    )
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        help_text='Latitude coordinate'
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        help_text='Longitude coordinate'
    )
    precision = models.CharField(
        max_length=20,
        choices=FuelStation.GEOCODE_PRECISION_CHOICES,
        default='unknown',
        help_text='Precision level of coordinates'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Geocode Cache'
        verbose_name_plural = 'Geocode Cache'

    def __str__(self):
        return f"{self.address_key} -> ({self.latitude}, {self.longitude})"

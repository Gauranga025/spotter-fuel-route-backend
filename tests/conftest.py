import pytest
from django.contrib.gis.geos import Point
from stations.models import FuelStation, GeocodeCache


@pytest.fixture
def sample_station():
    """Create a sample fuel station for testing."""
    return FuelStation.objects.create(
        opis_truckstop_id=123,
        truckstop_name='Test Truckstop',
        address='123 Test St',
        city='Test City',
        state='TX',
        rack_id=456,
        retail_price=3.50,
        location=Point(-97.5, 32.5),
        geocode_status='success',
        geocode_precision='exact',
    )


@pytest.fixture
def sample_geocode_cache():
    """Create a sample geocode cache entry."""
    return GeocodeCache.objects.create(
        address_key='123 Test St, Test City, TX',
        latitude=32.5,
        longitude=-97.5,
        precision='exact',
    )


@pytest.fixture
def mock_osrm_response():
    """Mock OSRM route response."""
    return {
        'code': 'Ok',
        'routes': [
            {
                'distance': 100000,  # meters
                'duration': 6000,  # seconds
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [
                        [-97.5, 32.5],
                        [-96.5, 33.5],
                        [-95.5, 34.5],
                    ],
                },
            }
        ],
    }


@pytest.fixture
def mock_nominatim_response():
    """Mock Nominatim geocoding response."""
    return [
        {
            'lat': '32.5',
            'lon': '-97.5',
            'address': {
                'house_number': '123',
                'road': 'Test St',
                'city': 'Test City',
                'state': 'Texas',
            },
        }
    ]

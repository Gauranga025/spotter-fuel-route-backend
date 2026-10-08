import logging
from typing import Optional, Dict, Any

import httpx
from django.conf import settings
from django.contrib.gis.geos import Point

logger = logging.getLogger(__name__)


class GeocodingError(Exception):
    """Custom exception for geocoding errors."""
    pass


class GeocodingService:
    """Service for geocoding addresses using Nominatim."""

    def __init__(self):
        self.base_url = settings.NOMINATIM_BASE_URL
        self.timeout = 10.0
        self.user_agent = 'FuelRouteOptimizer/1.0 (assessment)'

    def geocode(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Geocode an address to coordinates.

        Args:
            address: Human-readable address string

        Returns:
            Dictionary with 'latitude', 'longitude', 'precision', 'point'
            or None if geocoding fails
        """
        if not address:
            return None

        try:
            params = {
                'q': address,
                'format': 'json',
                'limit': 1,
                'countrycodes': 'us',  # Restrict to USA
                'addressdetails': 1,
            }

            headers = {
                'User-Agent': self.user_agent
            }

            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f'{self.base_url}/search',
                    params=params,
                    headers=headers
                )
                response.raise_for_status()

                data = response.json()

                if not data:
                    logger.warning(f'No results for address: {address}')
                    return None

                result = data[0]

                # Validate coordinates are within USA bounds
                lat = float(result['lat'])
                lon = float(result['lon'])

                if not self.is_in_usa(lat, lon):
                    logger.warning(
                        f'Coordinates outside USA: {lat}, {lon}'
                    )
                    return None

                # Determine precision
                precision = self.determine_precision(result)

                return {
                    'latitude': lat,
                    'longitude': lon,
                    'precision': precision,
                    'point': Point(lon, lat),
                }

        except httpx.TimeoutException:
            logger.error(f'Geocoding timeout for address: {address}')
            raise GeocodingError(f'Timeout geocoding: {address}')
        except httpx.HTTPStatusError as e:
            logger.error(f'HTTP error geocoding {address}: {e}')
            raise GeocodingError(f'HTTP error: {e}')
        except Exception as e:
            logger.error(f'Error geocoding {address}: {e}')
            raise GeocodingError(f'Geocoding error: {e}')

    def is_in_usa(self, lat: float, lon: float) -> bool:
        """
        Check if coordinates are within approximate USA bounds.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            True if within USA bounds, False otherwise
        """
        # Approximate USA bounds
        USA_BOUNDS = {
            'min_lat': 24.0,
            'max_lat': 49.0,
            'min_lon': -125.0,
            'max_lon': -66.0,
        }

        return (
            USA_BOUNDS['min_lat'] <= lat <= USA_BOUNDS['max_lat'] and
            USA_BOUNDS['min_lon'] <= lon <= USA_BOUNDS['max_lon']
        )

    def determine_precision(self, result: Dict[str, Any]) -> str:
        """
        Determine the precision level of geocoding result.

        Args:
            result: Nominatim response data

        Returns:
            Precision string: 'exact', 'street', 'city', or 'unknown'
        """
        address_data = result.get('address', {})

        # Check if we have house number
        if 'house_number' in address_data:
            return 'exact'

        # Check if we have street name
        if 'road' in address_data:
            return 'street'

        # Check if we have city
        if 'city' in address_data or 'town' in address_data:
            return 'city'

        return 'unknown'

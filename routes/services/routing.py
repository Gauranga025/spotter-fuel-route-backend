import logging
from typing import Dict, Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class RoutingError(Exception):
    """Custom exception for routing errors."""
    pass


class RoutingService:
    """Service for calculating driving routes using OSRM."""

    def __init__(self):
        self.base_url = settings.OSRM_BASE_URL
        self.timeout = 30.0

    def get_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float
    ) -> Dict[str, Any]:
        """
        Get driving route between two points using OSRM.

        Args:
            start_lat: Starting latitude
            start_lon: Starting longitude
            end_lat: Ending latitude
            end_lon: Ending longitude

        Returns:
            Dictionary containing route data:
            - distance_miles: Total distance in miles
            - duration_minutes: Total duration in minutes
            - geometry: GeoJSON LineString geometry

        Raises:
            RoutingError: If routing fails
        """
        try:
            # Build OSRM request URL
            # Format: /route/v1/driving/{lon1},{lat1};{lon2},{lat2}
            coordinates = f'{start_lon},{start_lat};{end_lon},{end_lat}'
            url = f'{self.base_url}/route/v1/driving/{coordinates}'

            params = {
                'overview': 'full',
                'geometries': 'geojson',
            }

            logger.info(f'Requesting route from OSRM: {url}')

            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                # Validate response
                if data.get('code') != 'Ok':
                    raise RoutingError(
                        f'OSRM returned error: {data.get("code")} - '
                        f'{data.get("message")}'
                    )

                if not data.get('routes'):
                    raise RoutingError('No routes found in OSRM response')

                route = data['routes'][0]

                # Extract route data
                distance_meters = route['distance']
                duration_seconds = route['duration']
                geometry = route['geometry']

                # Convert to miles and minutes
                distance_miles = distance_meters / 1609.344
                duration_minutes = duration_seconds / 60.0

                logger.info(
                    f'Route calculated: {distance_miles:.2f} miles, '
                    f'{duration_minutes:.2f} minutes'
                )

                return {
                    'distance_miles': distance_miles,
                    'duration_minutes': duration_minutes,
                    'geometry': geometry,
                }

        except RoutingError:
            raise
        except httpx.TimeoutException:
            logger.error('OSRM request timeout')
            raise RoutingError('Routing service timeout')
        except httpx.HTTPStatusError as e:
            logger.error(f'OSRM HTTP error: {e}')
            raise RoutingError(f'HTTP error from routing service: {e}')
        except Exception as e:
            logger.error(f'Error getting route: {e}')
            raise RoutingError(f'Routing error: {e}')

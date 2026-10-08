import logging
from typing import List, Dict, Any

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import LineString
from django.contrib.gis.measure import D
from django.conf import settings

logger = logging.getLogger(__name__)


class RouteMatchingService:
    """Service for matching fuel stations to route corridors."""

    def __init__(self):
        self.corridor_miles = settings.ROUTE_CORRIDOR_MILES

    def find_stations_in_corridor(
        self,
        route_geometry: Dict[str, Any],
        stations_queryset
    ) -> List[Dict[str, Any]]:
        """
        Find fuel stations within a corridor around the route.

        Args:
            route_geometry: GeoJSON LineString geometry
            stations_queryset: QuerySet of FuelStation objects

        Returns:
            List of candidate stations with projection data
        """
        # Parse route geometry
        route_line = self._parse_route_geometry(route_geometry)

        # Use PostGIS geography-based distance query for corridor filtering
        # This correctly uses geodetic calculations in meters
        corridor_distance = D(mi=self.corridor_miles)
        candidates = stations_queryset.annotate(
            distance_to_route=Distance('location', route_line)
        ).filter(
            distance_to_route__lte=corridor_distance,
            geocode_status__in=['success', 'fallback']
        )

        logger.info(
            f'Found {candidates.count()} stations in corridor'
        )

        # Project stations onto route using geodetic calculations
        projected_stations = []
        for station in candidates:
            projection = self._project_station_onto_route(
                station, route_line
            )
            if projection:
                projected_stations.append(projection)

        # Sort by distance along route
        projected_stations.sort(
            key=lambda x: x['distance_from_start_miles']
        )

        return projected_stations

    def _parse_route_geometry(self, geometry: Dict[str, Any]) -> LineString:
        """Parse GeoJSON geometry to Django GEOS LineString."""
        if geometry['type'] != 'LineString':
            raise ValueError(
                f'Expected LineString, got {geometry["type"]}'
            )

        coordinates = geometry['coordinates']
        # GeoJSON is [lon, lat], GEOS expects [lon, lat]
        return LineString(coordinates, srid=4326)

    def _project_station_onto_route(
        self,
        station,
        route_line: LineString
    ) -> Dict[str, Any]:
        """
        Project a station onto the route and calculate distances using
        geodetic methods.

        Args:
            station: FuelStation instance
            route_line: Route LineString

        Returns:
            Dictionary with projection data or None if projection fails
        """
        try:
            station_point = station.location

            # Use PostGIS for geodetic calculations
            # This gives us accurate meter-based distances on WGS84 ellipsoid
            from django.db import connection

            with connection.cursor() as cursor:
                # Calculate distance along route using ST_LineLocatePoint
                # and ST_Length. This gives us the fraction of total length
                cursor.execute("""
                    SELECT
                        ST_LineLocatePoint(
                            ST_Transform(ST_GeomFromText(%s, 4326), 3857),
                            ST_Transform(ST_GeomFromText(%s, 4326), 3857)
                        ) *
                        ST_Length(
                            ST_Transform(ST_GeomFromText(%s, 4326), 3857)
                        ) as distance_along_meters,
                        ST_DistanceSphere(
                            ST_GeomFromText(%s, 4326),
                            ST_ClosestPoint(
                                ST_GeomFromText(%s, 4326),
                                ST_GeomFromText(%s, 4326)
                            )
                        ) as lateral_distance_meters
                """, [
                    route_line.ewkt,
                    station_point.ewkt,
                    route_line.ewkt,
                    station_point.ewkt,
                    route_line.ewkt,
                    station_point.ewkt
                ])

                result = cursor.fetchone()
                if not result:
                    return None

                distance_along_meters, lateral_distance_meters = result

            # Convert meters to miles
            distance_along_miles = distance_along_meters / 1609.344
            lateral_distance_miles = lateral_distance_meters / 1609.344

            return {
                'station_id': station.id,
                'station': station,
                'latitude': float(station.location.y),
                'longitude': float(station.location.x),
                'price_per_gallon': float(station.retail_price),
                'distance_from_start_miles': distance_along_miles,
                'distance_from_route_miles': lateral_distance_miles,
            }

        except Exception as e:
            logger.error(
                f'Error projecting station {station.id}: {e}'
            )
            return None

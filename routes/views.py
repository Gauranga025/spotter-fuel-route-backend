import logging

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from routes.serializers import FuelPlanRequestSerializer
from routes.services.routing import RoutingService, RoutingError
from stations.services.geocoding import GeocodingService, GeocodingError
from routes.services.route_matching import RouteMatchingService
from routes.services.fuel_optimizer import FuelOptimizer, FuelOptimizerError
from stations.models import FuelStation

logger = logging.getLogger(__name__)


@api_view(['POST'])
def fuel_plan(request):
    """
    Calculate optimal fuel stops for a route between two locations.

    Request body:
    {
        "start": "Dallas, TX",
        "finish": "Denver, CO"
    }

    Returns optimized fuel plan with route geometry and station details.
    """
    serializer = FuelPlanRequestSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            {'errors': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    start_location = serializer.validated_data['start']
    finish_location = serializer.validated_data['finish']

    logger.info(f'Fuel plan request: {start_location} -> {finish_location}')

    try:
        # Geocode start and finish locations
        geocoding_service = GeocodingService()

        logger.info('Geocoding start location')
        start_coords = geocoding_service.geocode(f'{start_location}, USA')
        if not start_coords:
            return Response(
                {'error': 'Could not geocode start location'},
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info('Geocoding finish location')
        finish_coords = geocoding_service.geocode(f'{finish_location}, USA')
        if not finish_coords:
            return Response(
                {'error': 'Could not geocode finish location'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get route from OSRM
        logger.info('Requesting route from OSRM')
        routing_service = RoutingService()
        route_data = routing_service.get_route(
            start_coords['latitude'],
            start_coords['longitude'],
            finish_coords['latitude'],
            finish_coords['longitude']
        )

        # Find candidate stations in route corridor
        logger.info('Finding stations in route corridor')
        route_matching_service = RouteMatchingService()
        stations_queryset = FuelStation.objects.all()
        candidate_stations = route_matching_service.find_stations_in_corridor(
            route_data['geometry'],
            stations_queryset
        )

        # Optimize fuel stops
        logger.info('Optimizing fuel stops')
        optimizer = FuelOptimizer()
        optimization_result = optimizer.optimize_fuel_stops(
            candidate_stations,
            route_data['distance_miles']
        )

        # Build response
        response_data = {
            'status': optimization_result['status'],
            'request': {
                'start': start_location,
                'finish': finish_location,
            },
        }

        if optimization_result['status'] == 'success':
            response_data['route'] = {
                'distance_miles': round(
                    route_data['distance_miles'],
                    2
                ),
                'duration_minutes': round(
                    route_data['duration_minutes'],
                    1
                ),
                'geometry': route_data['geometry'],
            }

            response_data['vehicle'] = {
                'max_range_miles': settings.MAX_RANGE_MILES,
                'mpg': settings.MPG,
                'tank_capacity_gallons': settings.TANK_CAPACITY_GALLONS,
                'initial_fuel_gallons': settings.INITIAL_FUEL_GALLONS,
            }

            response_data['fuel_stops'] = optimization_result['fuel_stops']
            response_data['fuel_summary'] = optimization_result[
                'fuel_summary'
            ]
        else:
            response_data['reason'] = optimization_result['reason']

        logger.info(
            'Fuel plan complete: '
            f'{len(response_data.get("fuel_stops", []))} stops'
        )

        return Response(response_data, status=status.HTTP_200_OK)

    except GeocodingError as e:
        logger.error(f'Geocoding error: {e}')
        return Response(
            {'error': f'Geocoding service error: {str(e)}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except RoutingError as e:
        logger.error(f'Routing error: {e}')
        return Response(
            {'error': f'Routing service error: {str(e)}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except FuelOptimizerError as e:
        logger.error(f'Optimization error: {e}')
        return Response(
            {'error': f'Optimization error: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

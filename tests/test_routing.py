from unittest.mock import Mock, patch
import pytest
import httpx

from routes.services.routing import RoutingService, RoutingError


class TestRoutingService:
    """Tests for RoutingService."""

    def test_successful_route(self, mock_osrm_response):
        """Test successful route calculation."""
        service = RoutingService()

        with patch("httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = mock_osrm_response
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response

            result = service.get_route(32.5, -97.5, 34.5, -95.5)

            assert result is not None
            assert 'distance_miles' in result
            assert 'duration_minutes' in result
            assert 'geometry' in result
            assert result['distance_miles'] > 0
            assert result['duration_minutes'] > 0

    def test_routing_timeout(self):
        """Test routing timeout handling."""
        service = RoutingService()

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.side_effect = (
                httpx.TimeoutException('Timeout')
            )

            with pytest.raises(RoutingError):
                service.get_route(32.5, -97.5, 34.5, -95.5)

    def test_routing_http_error(self):
        """Test routing HTTP error handling."""
        service = RoutingService()

        with patch("httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response = Mock()
            mock_response.raise_for_status.side_effect = (
                httpx.HTTPStatusError(
                    'Error',
                    request=Mock(),
                    response=Mock()
                )
            )
            mock_client.get.return_value = mock_response

            with pytest.raises(RoutingError):
                service.get_route(32.5, -97.5, 34.5, -95.5)

    def test_routing_no_routes(self):
        """Test routing when no routes are returned."""
        service = RoutingService()

        with patch("httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = {
                'code': 'Ok',
                'routes': []
            }
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response

            with pytest.raises(RoutingError):
                service.get_route(32.5, -97.5, 34.5, -95.5)

    def test_routing_error_code(self):
        """Test routing when OSRM returns error code."""
        service = RoutingService()

        with patch("httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = {
                'code': 'Error',
                'message': 'Invalid coordinates'
            }
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response

            with pytest.raises(RoutingError):
                service.get_route(32.5, -97.5, 34.5, -95.5)

from unittest.mock import Mock, patch
import pytest
import httpx

from stations.services.geocoding import (
    GeocodingService,
    GeocodingError
)


class TestGeocodingService:
    """Tests for GeocodingService."""

    def test_successful_geocode(self, mock_nominatim_response):
        """Test successful geocoding."""
        service = GeocodingService()

        with patch("httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = mock_nominatim_response
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response

            result = service.geocode('123 Test St, Test City, TX')

            assert result is not None
            assert result['latitude'] == 32.5
            assert result['longitude'] == -97.5
            assert result['precision'] == 'exact'

    def test_geocode_timeout(self):
        """Test geocoding timeout handling."""
        service = GeocodingService()

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__.side_effect = (
                httpx.TimeoutException('Timeout')
            )

            with pytest.raises(GeocodingError):
                service.geocode('Test Address')

    def test_geocode_http_error(self):
        """Test geocoding HTTP error handling."""
        service = GeocodingService()

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

            with pytest.raises(GeocodingError):
                service.geocode('Test Address')

    def test_geocode_no_results(self):
        """Test geocoding when no results are found."""
        service = GeocodingService()

        with patch("httpx.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response = Mock()
            mock_response.json.return_value = []
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response

            result = service.geocode('Invalid Address')
            assert result is None

    def test_is_in_usa_valid(self):
        """Test USA bounds validation for valid coordinates."""
        service = GeocodingService()
        assert service.is_in_usa(39.8, -98.6) is True  # Kansas

    def test_is_in_usa_invalid(self):
        """Test USA bounds validation for invalid coordinates."""
        service = GeocodingService()
        assert service.is_in_usa(51.5, -0.1) is False  # London
        assert service.is_in_usa(-33.9, 151.2) is False  # Sydney

    def test_determine_precision_exact(self):
        """Test precision determination for exact address."""
        service = GeocodingService()
        result = {'address': {'house_number': '123'}}
        assert service.determine_precision(result) == 'exact'

    def test_determine_precision_street(self):
        """Test precision determination for street level."""
        service = GeocodingService()
        result = {'address': {'road': 'Main St'}}
        assert service.determine_precision(result) == 'street'

    def test_determine_precision_city(self):
        """Test precision determination for city level."""
        service = GeocodingService()
        result = {'address': {'city': 'Dallas'}}
        assert service.determine_precision(result) == 'city'

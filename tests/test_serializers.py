from routes.serializers import FuelPlanRequestSerializer


class TestFuelPlanRequestSerializer:
    """Tests for FuelPlanRequestSerializer."""

    def test_valid_request(self):
        """Test valid request data."""
        data = {
            'start': 'Dallas, TX',
            'finish': 'Denver, CO',
        }
        serializer = FuelPlanRequestSerializer(data=data)
        assert serializer.is_valid()

    def test_missing_start(self):
        """Test validation when start is missing."""
        data = {'finish': 'Denver, CO'}
        serializer = FuelPlanRequestSerializer(data=data)
        assert not serializer.is_valid()
        assert 'start' in serializer.errors

    def test_missing_finish(self):
        """Test validation when finish is missing."""
        data = {'start': 'Dallas, TX'}
        serializer = FuelPlanRequestSerializer(data=data)
        assert not serializer.is_valid()
        assert 'finish' in serializer.errors

    def test_same_start_and_finish(self):
        """Test validation when start and finish are the same."""
        data = {
            'start': 'Dallas, TX',
            'finish': 'Dallas, TX',
        }
        serializer = FuelPlanRequestSerializer(data=data)
        assert not serializer.is_valid()
        assert 'non_field_errors' in serializer.errors

    def test_same_start_and_finish_case_insensitive(self):
        """Test validation is case-insensitive."""
        data = {
            'start': 'dallas, tx',
            'finish': 'DALLAS, TX',
        }
        serializer = FuelPlanRequestSerializer(data=data)
        assert not serializer.is_valid()

    def test_invalid_data_types(self):
        """Test validation with invalid data types."""
        data = {
            'start': 123,
            'finish': 'Denver, CO',
        }
        serializer = FuelPlanRequestSerializer(data=data)
        assert not serializer.is_valid()

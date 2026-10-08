from rest_framework import serializers


class FuelPlanRequestSerializer(serializers.Serializer):
    start = serializers.CharField(
        max_length=255,
        help_text='Starting location (e.g., "Dallas, TX")'
    )
    finish = serializers.CharField(
        max_length=255,
        help_text='Destination location (e.g., "Denver, CO")'
    )

    def to_internal_value(self, data):
        """Validate that start and finish are strings before field coercion."""
        if not isinstance(data, dict):
            data = {}

        errors = {}

        # Check raw data types before CharField coercion
        if 'start' in data and not isinstance(data['start'], str):
            errors['start'] = ['Start must be a string, not a number.']

        if 'finish' in data and not isinstance(data['finish'], str):
            errors['finish'] = ['Finish must be a string, not a number.']

        if errors:
            raise serializers.ValidationError(errors)

        return super().to_internal_value(data)

    def validate(self, attrs):
        start = attrs.get('start')
        finish = attrs.get('finish')

        if start.lower() == finish.lower():
            raise serializers.ValidationError(
                'Start and finish locations cannot be the same'
            )

        return attrs


class FuelStopSerializer(serializers.Serializer):
    station_id = serializers.IntegerField()
    name = serializers.CharField()
    address = serializers.CharField(allow_blank=True)
    city = serializers.CharField()
    state = serializers.CharField(max_length=2)
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    price_per_gallon = serializers.FloatField()
    distance_from_start_miles = serializers.FloatField()
    gallons_purchased = serializers.FloatField()
    fuel_cost = serializers.FloatField()


class FuelSummarySerializer(serializers.Serializer):
    purchased_gallons = serializers.FloatField()
    consumed_gallons = serializers.FloatField()
    total_cost = serializers.FloatField()


class VehicleSerializer(serializers.Serializer):
    max_range_miles = serializers.IntegerField()
    mpg = serializers.FloatField()
    tank_capacity_gallons = serializers.FloatField()
    initial_fuel_gallons = serializers.FloatField()


class RouteSerializer(serializers.Serializer):
    distance_miles = serializers.FloatField()
    duration_minutes = serializers.FloatField()
    geometry = serializers.DictField()


class FuelPlanResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    request = FuelPlanRequestSerializer()
    route = RouteSerializer(required=False)
    vehicle = VehicleSerializer(required=False)
    fuel_stops = FuelStopSerializer(many=True, required=False)
    fuel_summary = FuelSummarySerializer(required=False)
    reason = serializers.CharField(required=False)

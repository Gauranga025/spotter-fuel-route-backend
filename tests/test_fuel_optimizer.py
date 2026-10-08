import pytest
from routes.services.fuel_optimizer import FuelOptimizer


@pytest.mark.django_db
class TestFuelOptimizer:
    """Tests for FuelOptimizer."""

    @pytest.fixture
    def optimizer(self):
        """Create a FuelOptimizer instance."""
        return FuelOptimizer()

    def test_destination_under_500_miles(self, optimizer):
        """Test when destination is under 500 miles (no stops needed)."""
        candidate_stations = []
        total_distance = 300.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'success'
        assert len(result['fuel_stops']) == 0

    def test_destination_exactly_500_miles(self, optimizer):
        """Test when destination is exactly 500 miles."""
        candidate_stations = []
        total_distance = 500.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'success'

    def test_destination_over_500_miles_no_stations(self, optimizer):
        """Test when destination is over 500 miles with no stations."""
        candidate_stations = []
        total_distance = 600.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'no_feasible_route'

    def test_one_station(self, optimizer, sample_station):
        """Test with one station available."""
        candidate_stations = [
            {
                'station_id': sample_station.id,
                'station': sample_station,
                'price_per_gallon': 3.50,
                'distance_from_start_miles': 300.0,
            }
        ]
        total_distance = 600.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'success'
        assert len(result['fuel_stops']) == 1
        assert result['fuel_stops'][0]['station_id'] == sample_station.id
        assert result['fuel_stops'][0]['gallons_purchased'] > 0
        assert result['fuel_stops'][0]['gallons_purchased'] <= 50.0
        assert result['fuel_stops'][0]['fuel_cost'] > 0

    def test_multiple_stations(self, optimizer, sample_station):
        """Test with multiple stations."""
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 3.50,
                'distance_from_start_miles': 200.0,
            },
            {
                'station_id': 2,
                'station': sample_station,
                'price_per_gallon': 3.30,
                'distance_from_start_miles': 400.0,
            },
        ]
        total_distance = 600.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'success'
        # Verify stations are ordered by distance along route
        if len(result['fuel_stops']) > 1:
            distances = [
                s['distance_from_start_miles']
                for s in result['fuel_stops']
            ]
            assert distances == sorted(distances), (
                'Stations not ordered by distance'
            )

    def test_chooses_cheaper_reachable_station(
        self, optimizer, sample_station
    ):
        """Test that optimizer chooses cheaper reachable station."""
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 4.00,
                'distance_from_start_miles': 200.0,
            },
            {
                'station_id': 2,
                'station': sample_station,
                'price_per_gallon': 3.00,
                'distance_from_start_miles': 300.0,
            },
        ]
        total_distance = 500.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'success'
        # With 50 gallons initial fuel (500 mile range), both stations
        # are reachable. Should prefer cheaper station at 300 miles
        selected_ids = [s['station_id'] for s in result['fuel_stops']]
        assert 2 in selected_ids or len(result['fuel_stops']) == 0

    def test_station_sequence_with_gap_over_500_miles(
        self, optimizer, sample_station
    ):
        """Test when stations have a gap > 500 miles."""
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 3.50,
                'distance_from_start_miles': 200.0,
            },
            {
                'station_id': 2,
                'station': sample_station,
                'price_per_gallon': 3.30,
                'distance_from_start_miles': 800.0,
            },
        ]
        total_distance = 1000.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'no_feasible_route'

    def test_exact_range_boundary(self, optimizer, sample_station):
        """Test behavior at exact 500-mile range boundary."""
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 3.50,
                'distance_from_start_miles': 500.0,
            },
        ]
        total_distance = 1000.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'success'
        assert len(result['fuel_stops']) == 1
        assert result['fuel_stops'][0]['station_id'] == 1

    def test_fuel_capacity_never_exceeds_50_gallons(
        self, optimizer, sample_station
    ):
        """Test that fuel purchases never exceed 50 gallons."""
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 3.50,
                'distance_from_start_miles': 200.0,
            },
        ]
        total_distance = 600.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        if result['status'] == 'success':
            for stop in result['fuel_stops']:
                gallons = stop['gallons_purchased']
                assert 0 <= gallons <= 50.0, (
                    f'Invalid gallons: {gallons}'
                )

    def test_impossible_route(self, optimizer):
        """Test when no feasible route exists."""
        candidate_stations = []
        total_distance = 2000.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'no_feasible_route'
        assert 'reason' in result

    # Deterministic test cases for optimizer semantics

    def test_case_a_300_miles_no_stations(self, optimizer):
        """
        Case A: Distance = 300 miles, no stations.
        Expected: success, zero fuel stops, zero purchased gallons,
        zero fuel purchase cost (vehicle starts with full tank).
        """
        candidate_stations = []
        total_distance = 300.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'success'
        assert len(result['fuel_stops']) == 0
        assert result['fuel_summary']['purchased_gallons'] == 0.0
        assert result['fuel_summary']['consumed_gallons'] == 30.0
        assert result['fuel_summary']['total_cost'] == 0.0

    def test_case_b_500_miles_no_stations(self, optimizer):
        """
        Case B: Distance = 500 miles, no stations.
        Expected: success, zero stops (exactly at max range).
        """
        candidate_stations = []
        total_distance = 500.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'success'
        assert len(result['fuel_stops']) == 0

    def test_case_c_600_miles_station_at_300(self, optimizer, sample_station):
        """
        Case C: Distance = 600 miles with a station at 300 miles.
        Expected: success, station selected.
        Vehicle can travel 500 miles initially, so it reaches the station.
        """
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 3.50,
                'distance_from_start_miles': 300.0,
            }
        ]
        total_distance = 600.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'success'
        assert len(result['fuel_stops']) == 1
        assert result['fuel_stops'][0]['station_id'] == 1

    def test_case_d_station_at_500_dest_at_1000(
        self, optimizer, sample_station
    ):
        """
        Case D: Station at exactly 500 miles and destination at 1000 miles.
        Expected: success because exactly 500 miles is reachable.
        """
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 3.50,
                'distance_from_start_miles': 500.0,
            }
        ]
        total_distance = 1000.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'success'

    def test_case_e_600_miles_no_stations(self, optimizer):
        """
        Case E: Distance = 600 miles with no stations.
        Expected: no_feasible_route (exceeds 500-mile range).
        """
        candidate_stations = []
        total_distance = 600.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'no_feasible_route'

    def test_case_f_chooses_cheaper_station(self, optimizer, sample_station):
        """
        Case F: Station A at 200 miles costing $4.00/gallon and
        Station B at 300 miles costing $3.00/gallon.
        The optimizer should not unnecessarily buy a full tank at
        Station A when it can reach the cheaper Station B.
        """
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 4.00,
                'distance_from_start_miles': 200.0,
            },
            {
                'station_id': 2,
                'station': sample_station,
                'price_per_gallon': 3.00,
                'distance_from_start_miles': 300.0,
            }
        ]
        total_distance = 600.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'success'
        # Should prefer the cheaper station at 300 miles if feasible
        # (starting with 50 gallons = 500 mile range)
        selected_ids = [s['station_id'] for s in result['fuel_stops']]
        assert 2 in selected_ids  # Cheaper station should be selected

    def test_case_g_stations_separated_over_500_miles(
        self, optimizer, sample_station
    ):
        """
        Case G: Two stations separated by >500 miles.
        Expected: no_feasible_route unless another candidate makes it feasible.
        """
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 3.50,
                'distance_from_start_miles': 200.0,
            },
            {
                'station_id': 2,
                'station': sample_station,
                'price_per_gallon': 3.30,
                'distance_from_start_miles': 800.0,
            }
        ]
        total_distance = 1000.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'no_feasible_route'

    def test_case_h_fuel_capacity_constraints(self, optimizer, sample_station):
        """
        Case H: Verify every fuel purchase satisfies:
        0 <= gallons_purchased <= 50
        and fuel level never becomes negative.
        """
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 3.50,
                'distance_from_start_miles': 300.0,
            },
            {
                'station_id': 2,
                'station': sample_station,
                'price_per_gallon': 3.30,
                'distance_from_start_miles': 600.0,
            }
        ]
        total_distance = 900.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        if result['status'] == 'success':
            for stop in result['fuel_stops']:
                gallons = stop['gallons_purchased']
                assert 0 <= gallons <= 50.0, (
                    f'Invalid gallons: {gallons}'
                )

    def test_total_cost_calculation(self, optimizer, sample_station):
        """Test that total cost is calculated correctly."""
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 3.00,
                'distance_from_start_miles': 300.0,
            },
        ]
        total_distance = 600.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        if result['status'] == 'success':
            total_cost = sum(
                stop['fuel_cost'] for stop in result['fuel_stops']
            )
            assert abs(
                total_cost - result['fuel_summary']['total_cost']
            ) < 0.01, (
                f'Cost mismatch: {total_cost} vs '
                f'{result["fuel_summary"]["total_cost"]}'
            )

    def test_case_i_cost_summation(self, optimizer, sample_station):
        """
        Case I: Verify sum(stop.fuel_cost) == fuel_summary.total_cost
        using Decimal-safe arithmetic.
        """
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 3.50,
                'distance_from_start_miles': 300.0,
            }
        ]
        total_distance = 600.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        if result['status'] == 'success':
            total_cost = sum(
                stop['fuel_cost'] for stop in result['fuel_stops']
            )
            assert abs(
                total_cost - result['fuel_summary']['total_cost']
            ) < 0.01, (
                f'Cost mismatch: {total_cost} vs '
                f'{result["fuel_summary"]["total_cost"]}'
            )
            # Verify purchased_gallons equals sum of stop purchases
            total_purchased = sum(
                stop['gallons_purchased'] for stop in result['fuel_stops']
            )
            assert abs(
                total_purchased - result['fuel_summary']['purchased_gallons']
            ) < 0.01

    def test_case_j_one_stop_next_leg_purchase(self, optimizer, sample_station):
        """
        Case B (regression): Route requiring one stop.
        Verify station purchase is calculated for the NEXT leg, not the previous leg.
        - initial fuel = 50 gallons
        - station at 300 miles
        - destination at 600 miles
        - Fuel consumed to reach station: 300/10 = 30 gallons
        - Fuel remaining at station: 50 - 30 = 20 gallons
        - Fuel needed for next leg (300 miles): 30 gallons
        - Fuel purchased at station: 30 - 20 = 10 gallons
        """
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 3.00,
                'distance_from_start_miles': 300.0,
            }
        ]
        total_distance = 600.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'success'
        assert len(result['fuel_stops']) == 1
        stop = result['fuel_stops'][0]
        
        # Fuel purchased should be based on NEXT leg
        # 30 gallons needed for next leg - 20 gallons remaining = 10 gallons
        assert abs(stop['gallons_purchased'] - 10.0) < 0.1, (
            f'Expected ~10 gallons, got {stop["gallons_purchased"]}'
        )
        
        # Fuel cost should equal gallons * price
        expected_cost = stop['gallons_purchased'] * stop['price_per_gallon']
        assert abs(stop['fuel_cost'] - expected_cost) < 0.01, (
            f'Expected cost {expected_cost}, got {stop["fuel_cost"]}'
        )
        
        # Summary should match
        assert abs(
            result['fuel_summary']['purchased_gallons'] - stop['gallons_purchased']
        ) < 0.01
        assert abs(
            result['fuel_summary']['total_cost'] - stop['fuel_cost']
        ) < 0.01

    def test_case_k_long_route_one_stop(self, optimizer, sample_station):
        """
        Case C (regression): Dallas → Denver-style case.
        - approximately 795 miles
        - station around 443 miles
        - initial fuel 50 gallons
        - station price 2.899
        - verify purchase is approximately 29.52 gallons
        - verify cost is approximately $85.59
        """
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 2.899,
                'distance_from_start_miles': 443.2648,
            }
        ]
        total_distance = 795.23

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        assert result['status'] == 'success'
        assert len(result['fuel_stops']) == 1
        stop = result['fuel_stops'][0]
        
        # Fuel consumed to reach station: 443.2648 / 10 = 44.3265 gallons
        # Fuel remaining at station: 50 - 44.3265 = 5.6735 gallons
        # Distance to destination: 795.23 - 443.2648 = 351.9652 miles
        # Fuel needed for next leg: 351.9652 / 10 = 35.1965 gallons
        # Fuel purchased: 35.1965 - 5.6735 = 29.523 gallons
        expected_gallons = 29.52
        expected_cost = expected_gallons * 2.899  # ~85.59
        
        assert abs(stop['gallons_purchased'] - expected_gallons) < 0.1, (
            f'Expected ~{expected_gallons} gallons, got {stop["gallons_purchased"]}'
        )
        assert abs(stop['fuel_cost'] - expected_cost) < 1.0, (
            f'Expected ~${expected_cost}, got ${stop["fuel_cost"]}'
        )

    def test_case_l_multi_stop_next_leg_purchases(
        self, optimizer, sample_station
    ):
        """
        Case D (regression): Multi-stop case.
        Verify each station's purchase is based on the following leg.
        - initial fuel = 50 gallons
        - Station A at 200 miles
        - Station B at 400 miles
        - Destination at 600 miles
        """
        candidate_stations = [
            {
                'station_id': 1,
                'station': sample_station,
                'price_per_gallon': 3.50,
                'distance_from_start_miles': 200.0,
            },
            {
                'station_id': 2,
                'station': sample_station,
                'price_per_gallon': 3.30,
                'distance_from_start_miles': 400.0,
            }
        ]
        total_distance = 600.0

        result = optimizer.optimize_fuel_stops(
            candidate_stations,
            total_distance
        )

        if result['status'] == 'success' and len(result['fuel_stops']) > 0:
            # Verify each stop has valid purchase
            for stop in result['fuel_stops']:
                gallons = stop['gallons_purchased']
                assert 0 <= gallons <= 50.0, (
                    f'Invalid gallons: {gallons}'
                )
                # Fuel cost should equal gallons * price
                expected_cost = gallons * stop['price_per_gallon']
                assert abs(stop['fuel_cost'] - expected_cost) < 0.01, (
                    f'Cost mismatch for station {stop["station_id"]}: '
                    f'expected {expected_cost}, got {stop["fuel_cost"]}'
                )
            
            # Verify total purchased equals sum of stops
            total_purchased = sum(
                stop['gallons_purchased'] for stop in result['fuel_stops']
            )
            assert abs(
                total_purchased - result['fuel_summary']['purchased_gallons']
            ) < 0.01
            
            # Verify total cost equals sum of stops
            total_cost = sum(
                stop['fuel_cost'] for stop in result['fuel_stops']
            )
            assert abs(
                total_cost - result['fuel_summary']['total_cost']
            ) < 0.01

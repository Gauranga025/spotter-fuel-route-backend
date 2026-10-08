import logging
from decimal import Decimal
from typing import List, Dict, Any

from django.conf import settings

logger = logging.getLogger(__name__)


class FuelOptimizerError(Exception):
    """Custom exception for fuel optimization errors."""
    pass


class FuelOptimizer:
    """
    Optimizes fuel stops along a route using dynamic programming.

    The optimizer finds the minimum-cost sequence of fuel stops that
    allows the vehicle to complete the route within range constraints.
    """

    def __init__(self):
        self.max_range_miles = settings.MAX_RANGE_MILES
        self.mpg = settings.MPG
        self.tank_capacity_gallons = settings.TANK_CAPACITY_GALLONS
        self.initial_fuel_gallons = settings.INITIAL_FUEL_GALLONS

    def optimize_fuel_stops(
        self,
        candidate_stations: List[Dict[str, Any]],
        total_distance_miles: float
    ) -> Dict[str, Any]:
        """
        Find optimal fuel stops using dynamic programming.

        Args:
            candidate_stations: List of stations with:
                - station_id
                - station (FuelStation object)
                - price_per_gallon
                - distance_from_start_miles
            total_distance_miles: Total route distance

        Returns:
            Dictionary with optimization results or no_feasible_route
        """
        if not candidate_stations:
            # Check if destination is reachable without stops
            if total_distance_miles <= self.max_range_miles:
                return self._build_no_stop_result(total_distance_miles)
            else:
                return self._build_no_feasible_result()

        # Add start and destination as nodes
        nodes = self._build_nodes(
            candidate_stations,
            total_distance_miles
        )

        # Build adjacency graph of feasible transitions
        graph = self._build_graph(nodes)

        # Run dynamic programming to find minimum cost path
        result = self._find_minimum_cost_path(
            nodes,
            graph,
            total_distance_miles
        )

        return result

    def _build_nodes(
        self,
        candidate_stations: List[Dict[str, Any]],
        total_distance_miles: float
    ) -> List[Dict[str, Any]]:
        """Build list of nodes including start and destination."""
        nodes = [
            {
                'type': 'start',
                'distance_from_start': 0.0,
                'price_per_gallon': 0.0,
            }
        ]

        for station_data in candidate_stations:
            nodes.append({
                'type': 'station',
                'station_id': station_data['station_id'],
                'station': station_data['station'],
                'distance_from_start': station_data[
                    'distance_from_start_miles'
                ],
                'price_per_gallon': station_data['price_per_gallon'],
            })

        nodes.append({
            'type': 'destination',
            'distance_from_start': total_distance_miles,
            'price_per_gallon': 0.0,
        })

        return nodes

    def _build_graph(self, nodes: List[Dict[str, Any]]) -> Dict:
        """
        Build graph of feasible transitions between nodes.

        A transition from node A to node B is feasible if:
        - distance(A, B) <= max_range_miles
        """
        graph = {i: [] for i in range(len(nodes))}

        for i, node_a in enumerate(nodes):
            for j, node_b in enumerate(nodes):
                if i >= j:
                    continue  # Only consider forward movement

                distance = node_b['distance_from_start'] - \
                    node_a['distance_from_start']

                if distance <= self.max_range_miles:
                    graph[i].append({
                        'to': j,
                        'distance': distance,
                        'fuel_required': distance / self.mpg,
                    })

        return graph

    def _find_minimum_cost_path(
        self,
        nodes: List[Dict[str, Any]],
        graph: Dict,
        total_distance_miles: float
    ) -> Dict[str, Any]:
        """
        Use dynamic programming to find minimum cost path.

        DP state: dp[i][fuel] = minimum cost to reach node i with fuel gallons
        """
        n = len(nodes)
        destination_idx = n - 1

        # Check if destination is directly reachable from start
        start_to_dest_dist = total_distance_miles
        if start_to_dest_dist <= self.max_range_miles:
            if self.initial_fuel_gallons >= start_to_dest_dist / self.mpg:
                return self._build_no_stop_result(total_distance_miles)

        # Initialize DP
        # dp[i] = (min_cost, fuel_at_node, prev_node)
        dp = [(float('inf'), 0.0, -1) for _ in range(n)]
        dp[0] = (Decimal('0'), self.initial_fuel_gallons, -1)

        # Process nodes in order
        for i in range(n):
            if dp[i][0] == float('inf'):
                continue  # Unreachable

            current_cost, current_fuel, _ = dp[i]

            # Try all feasible transitions
            for edge in graph[i]:
                j = edge['to']
                fuel_required = edge['fuel_required']

                # Calculate fuel needed at node i to reach node j
                fuel_needed = max(0, fuel_required - current_fuel)

                # Check if we can buy enough fuel
                if current_fuel + fuel_needed > self.tank_capacity_gallons:
                    continue  # Not enough tank capacity

                # Calculate cost
                if nodes[i]['type'] == 'start':
                    price = 0.0
                else:
                    price = nodes[i]['price_per_gallon']

                additional_cost = Decimal(str(fuel_needed * price))
                new_cost = current_cost + additional_cost

                # Fuel at node j
                fuel_at_j = current_fuel + fuel_needed - fuel_required

                # Update DP if better
                if new_cost < dp[j][0]:
                    dp[j] = (new_cost, fuel_at_j, i)

        # Check if destination is reachable
        if dp[destination_idx][0] == float('inf'):
            return self._build_no_feasible_result()

        # Reconstruct path
        path = []
        current = destination_idx
        while current != -1:
            path.append(current)
            current = dp[current][2]

        path.reverse()

        # Build result
        fuel_stops = []
        total_gallons = Decimal('0')
        total_cost = dp[destination_idx][0]

        for i, node_idx in enumerate(path):
            node = nodes[node_idx]
            if node['type'] == 'station':
                # Get fuel available when arriving at this station
                fuel_at_station = dp[node_idx][1]

                # Look at the NEXT node in the path
                # Fuel is purchased at the current station for the NEXT leg
                if i + 1 < len(path):
                    next_node_idx = path[i + 1]

                    # Find the edge from current station to next node
                    edge_used = None
                    for edge in graph[node_idx]:
                        if edge['to'] == next_node_idx:
                            edge_used = edge
                            break

                    if edge_used:
                        # Calculate fuel purchased at this station for the NEXT leg
                        fuel_needed = max(
                            0,
                            edge_used['fuel_required'] - fuel_at_station
                        )
                        gallons_purchased = Decimal(str(fuel_needed))
                        fuel_cost = gallons_purchased * Decimal(
                            str(node['price_per_gallon'])
                        )

                        total_gallons += gallons_purchased

                        fuel_stops.append({
                            'station_id': node['station_id'],
                            'name': node['station'].truckstop_name,
                            'address': node['station'].address,
                            'city': node['station'].city,
                            'state': node['station'].state,
                            'latitude': float(node['station'].location.y),
                            'longitude': float(node['station'].location.x),
                            'price_per_gallon': node['price_per_gallon'],
                            'distance_from_start_miles': node[
                                'distance_from_start'
                            ],
                            'gallons_purchased': float(gallons_purchased),
                            'fuel_cost': float(fuel_cost),
                        })

        return {
            'status': 'success',
            'fuel_stops': fuel_stops,
            'fuel_summary': {
                'purchased_gallons': float(total_gallons),
                'consumed_gallons': round(total_distance_miles / self.mpg, 2),
                'total_cost': float(total_cost),
            },
        }

    def _build_no_stop_result(self, total_distance_miles: float) -> Dict:
        """Build result when no stops are needed."""
        fuel_required = total_distance_miles / self.mpg
        # purchased_gallons is always 0 when no stops are made
        # initial fuel covers the entire trip
        purchased_gallons = 0.0

        return {
            'status': 'success',
            'fuel_stops': [],
            'fuel_summary': {
                'purchased_gallons': purchased_gallons,
                'consumed_gallons': round(fuel_required, 2),
                'total_cost': 0.0,
            },
        }

    def _build_no_feasible_result(self) -> Dict:
        """Build result when no feasible route exists."""
        return {
            'status': 'no_feasible_route',
            'reason': (
                'No feasible sequence of fuel stations can cover the '
                'route within the vehicle\'s 500-mile maximum range.'
            ),
        }

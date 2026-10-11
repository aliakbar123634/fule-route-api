

from math import radians, sin, cos, sqrt, atan2, isfinite
from math import (
    radians, sin, cos, sqrt, atan2, isfinite, ceil
)

MAX_RANGE_MILES = 500
FUEL_ECONOMY_MPG = 10
EARTH_RADIUS_MILES = 3958.8


def calculate_distance_miles(lat1, lon1, lat2, lon2):
    """Calculate straight-line distance between two coordinates."""
    values = (lat1, lon1, lat2, lon2)

    if not all(isfinite(value) for value in values):
        raise ValueError("Coordinates must be finite numbers.")

    if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
        raise ValueError("Latitude must be between -90 and 90.")

    if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
        raise ValueError("Longitude must be between -180 and 180.")

    lat1, lon1, lat2, lon2 = map(
        radians, (lat1, lon1, lat2, lon2)
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        sin(dlat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    )

    a = max(0.0, min(1.0, a))

    return 2 * EARTH_RADIUS_MILES * atan2(
        sqrt(a), sqrt(1 - a)
    )


def calculate_fuel_needed(distance_miles):
    """Estimate gallons needed at the configured MPG."""
    if not isfinite(distance_miles) or distance_miles < 0:
        raise ValueError("Distance must be a finite, non-negative number.")

    return distance_miles / FUEL_ECONOMY_MPG


def build_route_distances(route_coordinates):
    """
    Calculate cumulative distances along route geometry.

    GeoJSON coordinates use [longitude, latitude].
    Returns one cumulative distance for each route coordinate.
    """
    if not route_coordinates:
        return []

    cumulative_miles = [0.0]

    for index in range(1, len(route_coordinates)):
        lon1, lat1 = route_coordinates[index - 1]
        lon2, lat2 = route_coordinates[index]

        segment_distance = calculate_distance_miles(
            lat1, lon1, lat2, lon2
        )

        cumulative_miles.append(
            cumulative_miles[-1] + segment_distance
        )

    return cumulative_miles






def filter_stations_near_route(
    stations,
    route_coordinates,
    corridor_miles=5,
):
    """
    Find stations near the route using nearest-segment projection.

    GeoJSON coordinates use [longitude, latitude].
    Route position is an approximation based on geometry segment lengths.
    """
    if (
        not isfinite(corridor_miles)
        or corridor_miles <= 0
    ):
        raise ValueError("corridor_miles must be a positive number.")

    cumulative_miles = build_route_distances(route_coordinates)

    if len(route_coordinates) < 2:
        return []

    selected = []

    for station in stations:
        latitude = station.get("latitude")
        longitude = station.get("longitude")

        if latitude is None or longitude is None:
            continue

        try:
            latitude = float(latitude)
            longitude = float(longitude)

            if not (
                isfinite(latitude)
                and isfinite(longitude)
                and -90 <= latitude <= 90
                and -180 <= longitude <= 180
            ):
                continue

            nearest_distance = float("inf")
            nearest_position = 0.0

            for index in range(1, len(route_coordinates)):
                lon1, lat1 = route_coordinates[index - 1]
                lon2, lat2 = route_coordinates[index]

                # Local planar approximation in miles.
                mean_latitude = radians(
                    (lat1 + lat2 + latitude) / 3
                )

                x_scale = (
                    EARTH_RADIUS_MILES
                    * cos(mean_latitude)
                    * radians(1)
                )
                y_scale = EARTH_RADIUS_MILES * radians(1)

                x1, y1 = lon1 * x_scale, lat1 * y_scale
                x2, y2 = lon2 * x_scale, lat2 * y_scale
                xs, ys = longitude * x_scale, latitude * y_scale

                dx = x2 - x1
                dy = y2 - y1
                segment_squared = dx * dx + dy * dy

                if segment_squared == 0:
                    fraction = 0.0
                else:
                    fraction = (
                        (xs - x1) * dx + (ys - y1) * dy
                    ) / segment_squared
                    fraction = max(0.0, min(1.0, fraction))

                projected_x = x1 + fraction * dx
                projected_y = y1 + fraction * dy

                distance = sqrt(
                    (xs - projected_x) ** 2
                    + (ys - projected_y) ** 2
                )

                if distance < nearest_distance:
                    nearest_distance = distance

                    segment_length = (
                        cumulative_miles[index]
                        - cumulative_miles[index - 1]
                    )

                    nearest_position = (
                        cumulative_miles[index - 1]
                        + fraction * segment_length
                    )

            if nearest_distance <= corridor_miles:
                selected.append({
                    **station,
                    "latitude": latitude,
                    "longitude": longitude,
                    "distance_from_route_miles": round(
                        nearest_distance, 3
                    ),
                    "route_position_miles": round(
                        nearest_position, 3
                    ),
                })

        except (TypeError, ValueError, IndexError):
            continue

    return sorted(
        selected,
        key=lambda station: station["route_position_miles"],
    )




def select_fuel_stops(
    route_distance_miles,
    candidate_stations,
    max_range_miles=MAX_RANGE_MILES,
    fuel_economy_mpg=FUEL_ECONOMY_MPG,
):
    """
    Select fuel-stop candidates using a basic greedy strategy.

    IMPORTANT:
    This is a preliminary selection algorithm, not a complete
    fuel-cost optimizer. It assumes the vehicle starts with enough fuel
    for max_range_miles and does not model tank capacity, initial fuel,
    reserve fuel, or the amount actually purchased at each stop.

    Candidate stations must include:
    - route_position_miles
    - retail_price
    """
    if (
        not isfinite(route_distance_miles)
        or route_distance_miles < 0
    ):
        raise ValueError(
            "Route distance must be a finite, non-negative number."
        )

    if (
        not isfinite(max_range_miles)
        or max_range_miles <= 0
        or not isfinite(fuel_economy_mpg)
        or fuel_economy_mpg <= 0
    ):
        raise ValueError(
            "Range and fuel economy must be positive finite numbers."
        )

    if route_distance_miles <= max_range_miles:
        return {
            "stops": [],
            "estimated_fuel_cost": 0.0,
            "note": (
                "No intermediate stop selected because the route is "
                "within the configured maximum range. Total trip fuel "
                "cost is not calculated by this preliminary algorithm."
            ),
        }

    stations = []

    for station in candidate_stations:
        try:
            position = float(station["route_position_miles"])
            price = float(station["retail_price"])

            if (
                not isfinite(position)
                or not isfinite(price)
                or price <= 0
                or position <= 0
                or position >= route_distance_miles
            ):
                continue

            stations.append({
                **station,
                "route_position_miles": position,
                "retail_price": price,
            })

        except (KeyError, TypeError, ValueError):
            continue

    stations.sort(
        key=lambda station: station["route_position_miles"]
    )

    current_position = 0.0
    stops = []
    total_cost = 0.0

    while route_distance_miles - current_position > max_range_miles:
        reachable_limit = min(
            current_position + max_range_miles,
            route_distance_miles,
        )

        reachable = [
            station
            for station in stations
            if current_position < station["route_position_miles"]
            <= reachable_limit
        ]

        if not reachable:
            raise ValueError(
                "No candidate fuel station within the vehicle's "
                "maximum range. A feasible route cannot be confirmed."
            )

        # Choose the cheapest station reachable before the next range limit.
        chosen = min(
            reachable,
            key=lambda station: station["retail_price"],
        )

        next_position = chosen["route_position_miles"]
        segment_distance = next_position - current_position
        estimated_gallons = segment_distance / fuel_economy_mpg
        estimated_cost = (
            estimated_gallons * chosen["retail_price"]
        )

        stops.append({
            **chosen,
            "segment_distance_miles": round(segment_distance, 2),
            "estimated_gallons": round(estimated_gallons, 2),
            "estimated_cost": round(estimated_cost, 2),
        })

        total_cost += estimated_cost
        current_position = next_position

        stations = [
            station
            for station in stations
            if station["route_position_miles"] > current_position
        ]

    return {
        "stops": stops,
        "estimated_fuel_cost": round(total_cost, 2),
        "note": (
            "Preliminary estimate only. Cost is estimated using the "
            "distance since the previous stop and the selected station's "
            "price. Tank capacity, initial fuel, reserve fuel, and actual "
            "refueling quantities are not modeled."
        ),
    }



def select_fuel_stops(
    route_distance_miles,
    candidate_stations,
    max_range_miles=MAX_RANGE_MILES,
    fuel_economy_mpg=FUEL_ECONOMY_MPG,
):
    """
    Approximate minimum-cost refuelling using dynamic programming.

    Assumptions:
    - Vehicle starts with a full tank.
    - Maximum range is represented in whole-mile units.
    - Fuel remaining is carried between stations.
    - Only fuel purchased during the trip is included in cost.
    - Candidate station prices and route positions must be reliable.

    Fuel prices must be in dollars per gallon.
    """
    if (
        not isfinite(route_distance_miles)
        or route_distance_miles < 0
    ):
        raise ValueError(
            "Route distance must be a finite, non-negative number."
        )

    if (
        not isfinite(max_range_miles)
        or max_range_miles <= 0
        or not isfinite(fuel_economy_mpg)
        or fuel_economy_mpg <= 0
    ):
        raise ValueError(
            "Range and fuel economy must be positive finite numbers."
        )

    if route_distance_miles == 0:
        return {
            "stops": [],
            "estimated_fuel_cost": 0.0,
            "note": "Zero-distance route; no fuel purchase required.",
        }

    # Validate and normalize candidate stations.
    stations = []

    for station in candidate_stations:
        try:
            position = float(station["route_position_miles"])
            price = float(station["retail_price"])

            if (
                not isfinite(position)
                or not isfinite(price)
                or price <= 0
                or position <= 0
                or position >= route_distance_miles
            ):
                continue

            stations.append({
                **station,
                "route_position_miles": position,
                "retail_price": price,
            })

        except (KeyError, TypeError, ValueError):
            continue

    stations.sort(
        key=lambda station: station["route_position_miles"]
    )

    # One state represents one mile of remaining driving range.
    tank_range = int(max_range_miles)

    if tank_range != max_range_miles:
        raise ValueError(
            "This implementation requires an integer maximum range."
        )

    # Each station and the destination is a node in route order.
    nodes = [
        {
            "kind": "start",
            "position": 0.0,
        }
    ]

    # nodes.extend(
    #     {
    #         "kind": "station",
    #         **station,
    #     }
    #     for station in stations
    # )

    nodes.extend(
    {
        "kind": "station",
        "position": station["route_position_miles"],
        **station,
    }
    for station in stations
   )

    nodes.append({
        "kind": "destination",
        "position": float(route_distance_miles),
    })

    node_count = len(nodes)
    infinity = float("inf")

    # arrival[i][fuel] = minimum cost to arrive at node i
    # with the given whole-mile range remaining.
    arrival = [
        [infinity] * (tank_range + 1)
        for _ in range(node_count)
    ]

    # Parent information for reconstructing the selected route.
    previous = [
        [None] * (tank_range + 1)
        for _ in range(node_count)
    ]

    # Vehicle starts with a full tank; initial fuel cost is excluded.
    arrival[0][tank_range] = 0.0

    for i, node in enumerate(nodes[:-1]):
        position = node["position"]

        if node["kind"] == "start":
            departure_cost = [infinity] * (tank_range + 1)
            bought_from = [None] * (tank_range + 1)

            departure_cost[tank_range] = 0.0
            bought_from[tank_range] = tank_range

        else:
            price = node["retail_price"]
            departure_cost = [infinity] * (tank_range + 1)
            bought_from = [None] * (tank_range + 1)

            # Buying target range g costs:
            # (g - remaining_range) / MPG * price.
            best_value = infinity
            best_fuel = None

            for target_range in range(tank_range + 1):
                incoming_cost = arrival[i][target_range]

                if incoming_cost < infinity:
                    value = (
                        incoming_cost
                        - target_range * price / fuel_economy_mpg
                    )

                    if value < best_value:
                        best_value = value
                        best_fuel = target_range

                if best_fuel is not None:
                    departure_cost[target_range] = (
                        best_value
                        + target_range * price / fuel_economy_mpg
                    )
                    bought_from[target_range] = best_fuel

        # Drive to any later node that is reachable with the selected fuel.
        for target_range, cost in enumerate(departure_cost):
            if cost == infinity:
                continue

            for j in range(i + 1, node_count):
                distance = nodes[j]["position"] - position

                # Conservative whole-mile rounding.
                required_range = ceil(distance - 1e-9)

                if required_range > target_range:
                    break

                remaining_range = target_range - required_range

                if cost < arrival[j][remaining_range]:
                    arrival[j][remaining_range] = cost
                    previous[j][remaining_range] = (
                        i,
                        target_range,
                        bought_from[target_range],
                    )

    # Select the cheapest reachable destination state.
    destination_index = node_count - 1
    final_fuel = min(
        range(tank_range + 1),
        key=lambda fuel: arrival[destination_index][fuel],
    )

    minimum_cost = arrival[destination_index][final_fuel]

    if minimum_cost == infinity:
        raise ValueError(
            "No feasible fuel-stop route found. Candidate stations "
            "may be missing, incorrectly located, or too far apart."
        )

    # Reconstruct purchases from destination back to the start.
    selected_stops = []
    current_node = destination_index
    current_fuel = final_fuel

    while current_node != 0:
        parent = previous[current_node][current_fuel]

        if parent is None:
            raise ValueError(
                "Unable to reconstruct the optimized fuel-stop route."
            )

        previous_node, departure_range, incoming_range = parent
        previous_station = nodes[previous_node]

        if (
            previous_station["kind"] == "station"
            and departure_range > incoming_range
        ):
            gallons = (
                departure_range - incoming_range
            ) / fuel_economy_mpg

            purchase_cost = (
                gallons * previous_station["retail_price"]
            )

            selected_stops.append({
                **previous_station,
                "estimated_gallons": round(gallons, 2),
                "estimated_cost": round(purchase_cost, 2),
                "fuel_range_before_purchase_miles": incoming_range,
                "fuel_range_after_purchase_miles": departure_range,
            })

        current_node = previous_node
        current_fuel = incoming_range

    selected_stops.reverse()

    return {
        "stops": selected_stops,
        "estimated_fuel_cost": round(minimum_cost, 2),
        "optimization": "dynamic_programming",
        "fuel_economy_mpg": fuel_economy_mpg,
        "max_range_miles": max_range_miles,
        "assumptions": [
            "Vehicle starts with a full tank.",
            "Initial tank fuel cost is excluded.",
            "Fuel range is discretized in whole-mile increments.",
            "Station prices and route positions are assumed accurate.",
        ],
    }

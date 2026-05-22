from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def solve_vrp(cost_matrix: list[list[float]], duration_matrix: list[list[float]], delay_threshold: float, delay_penalty_cost: float, num_vehicles: int, starts: list[int], ends: list[int], vehicle_allowed_customers: list[list[int]] = None):
    """
    Solves the VRP using OR-Tools and returns a list of routes for all vehicles.
    Since OR-Tools requires integer weights, we scale the float cost matrix.
    """
    SCALE_FACTOR = 1000000  # Increased for precision
    
    # Scale cost matrix
    int_cost_matrix = [
        [int(cost * SCALE_FACTOR) for cost in row]
        for row in cost_matrix
    ]
    
    # Enforce all active vehicles (starts) to go to their respective duplicated target Shop immediately
    # Partner s (Node s) must visit Shop Copy s (Node len(starts) + s) as their first stop.
    shop_start_idx = len(starts)
    for s in starts:
        target_shop_copy = shop_start_idx + s
        if len(int_cost_matrix) > target_shop_copy:
            for i in range(len(int_cost_matrix[s])):
                if i != target_shop_copy:
                    int_cost_matrix[s][i] = 2000000000  # Prohibitively high cost
            # Model open VRP by making all return transitions to the start node costless
            for i in range(len(int_cost_matrix)):
                int_cost_matrix[i][s] = 0

    
    # Create the routing index manager.
    manager = pywrapcp.RoutingIndexManager(
        len(int_cost_matrix), num_vehicles, starts, ends
    )
    
    # Create Routing Model.
    routing = pywrapcp.RoutingModel(manager)
    
    # Register a vehicle-dependent distance callback for each vehicle to prevent cross-shop and cross-customer visits
    for vehicle_id in range(num_vehicles):
        def make_distance_callback(v_id):
            allowed_custs = vehicle_allowed_customers[v_id] if vehicle_allowed_customers else None
            
            def cb(from_index, to_index):
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                
                shop_start = len(starts)
                if shop_start <= to_node < shop_start + len(starts):
                    if to_node != shop_start + v_id:
                        return 2000000000
                if shop_start <= from_node < shop_start + len(starts):
                    if from_node != shop_start + v_id:
                        return 2000000000
                
                # Restrict customer nodes (node index >= 2 * len(starts))
                customer_start = 2 * len(starts)
                if allowed_custs is not None:
                    if to_node >= customer_start and to_node not in allowed_custs:
                        return 2000000000
                    if from_node >= customer_start and from_node not in allowed_custs:
                        return 2000000000
                
                return int_cost_matrix[from_node][to_node]
            return cb
            
        cb_index = routing.RegisterTransitCallback(make_distance_callback(vehicle_id))
        routing.SetArcCostEvaluatorOfVehicle(cb_index, vehicle_id)

    # Make shop copies optional via disjunctions with 0 penalty so inactive drivers don't have to visit them
    shop_start_idx = len(starts)
    for s in starts:
        target_shop_copy = shop_start_idx + s
        if target_shop_copy < len(int_cost_matrix):
            routing.AddDisjunction([manager.NodeToIndex(target_shop_copy)], 0)
    
    # Native Time Dimension for Delay Penalties
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        if to_node in starts:
            return 0
        return int(duration_matrix[from_node][to_node] * 100)

    time_callback_index = routing.RegisterTransitCallback(time_callback)
    
    routing.AddDimension(
        time_callback_index,
        0,  # no waiting time slack allowed
        30000000,  # vehicle maximum time
        True,  # start cumul to zero
        'Time'
    )
    
    time_dimension = routing.GetDimensionOrDie('Time')
    int_threshold = int(delay_threshold * 100)
    int_penalty = int(delay_penalty_cost * SCALE_FACTOR / 100)
    
    for i in range(len(cost_matrix)):
        index = manager.NodeToIndex(i)
        time_dimension.SetCumulVarSoftUpperBound(index, int_threshold, int_penalty)
    
    # Setting first solution heuristic.
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    
    # Solve the problem.
    solution = routing.SolveWithParameters(search_parameters)
    
    if not solution:
        return None
        
    routes = []
    for vehicle_id in range(num_vehicles):
        route = []
        index = routing.Start(vehicle_id)
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))
        routes.append(route)
        
    return routes

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def solve_vrp(cost_matrix: list[list[float]], duration_matrix: list[list[float]], delay_threshold: float, delay_penalty_cost: float, num_vehicles: int, starts: list[int], ends: list[int]):
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
    
    # Enforce Partner (Node 0) to go to Shop (Node 1) immediately
    # by making all other outgoing edges from Node 0 extremely expensive.
    if len(int_cost_matrix) > 1:
        for i in range(len(int_cost_matrix[0])):
            if i != 1:
                int_cost_matrix[0][i] = 2000000000  # Prohibitively high cost

    
    # Create the routing index manager.
    manager = pywrapcp.RoutingIndexManager(
        len(int_cost_matrix), num_vehicles, starts, ends
    )
    
    # Create Routing Model.
    routing = pywrapcp.RoutingModel(manager)
    
    # Create and register a transit callback.
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int_cost_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    
    # Define cost of each arc.
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    # Native Time Dimension for Delay Penalties
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
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

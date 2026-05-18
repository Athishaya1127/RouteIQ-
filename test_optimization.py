from backend.services.cost_engine import build_cost_matrix
from backend.services.optimizer import solve_vrp

# Mock distance matrix (km)
dist_matrix = [
    [0.0, 5.0, 10.0],
    [5.0, 0.0, 6.0],
    [10.0, 6.0, 0.0]
]

# Mock duration matrix (mins) with heavy traffic on edge 0->1
dur_matrix = [
    [0.0, 45.0, 20.0], # 0->1 takes 45 mins (heavy traffic), 0->2 takes 20 mins
    [45.0, 0.0, 12.0],
    [20.0, 12.0, 0.0]
]

cost_matrix, fuel_matrix, cr = build_cost_matrix(
    distance_matrix=dist_matrix,
    duration_matrix=dur_matrix,
    avg_speed=30.0,
    delay_threshold=45.0,
    delay_penalty=50.0
)

print("Cost Matrix:", cost_matrix)
print("Congestion Ratios:", cr)

best_route = solve_vrp(cost_matrix, num_vehicles=2)
print("Best Route:", best_route)

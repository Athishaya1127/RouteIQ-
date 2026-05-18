def calculate_delay_penalty(arrival_time: float, threshold: float, penalty: float) -> float:
    """
    Cumulative delay penalty calculation.
    If arrival_time > threshold: delay_penalty += penalty
    """
    if arrival_time > threshold:
        return penalty
    return 0.0

def build_delay_matrix(duration_matrix: list[list[float]], threshold: float, penalty: float) -> list[list[float]]:
    """
    Approximates delay penalty per edge assuming cumulative delay could happen.
    For more complex VRP, OR-Tools Time Dimension should handle this,
    but we provide this matrix to guide the cost engine.
    """
    num_nodes = len(duration_matrix)
    delay_matrix = [[0.0 for _ in range(num_nodes)] for _ in range(num_nodes)]
    
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i != j:
                # Simplistic edge-based penalty estimation for cost matrix setup
                delay_matrix[i][j] = calculate_delay_penalty(duration_matrix[i][j], threshold, penalty)
    
    return delay_matrix
